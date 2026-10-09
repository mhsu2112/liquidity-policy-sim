"""Episode replays with Jev support checks (M3.5; Clarification 31 B8).

    python -m analysis.m3.replay [RAW_FOLDER] [RESULTS_FOLDER]

For each scenario, the "median run" is the (bank, run) whose policy-A outcome at the tuning cell (stigma 0.35,
neutral) is the middle one when sorted by end day, then peak uncovered amount, then row. That one row is re-run
alone (with its own draws; one row alone equals the same row in a batch) under A, B, C, C' and E, keeping every
half-day's record. Code writes a log line and plain-English sentences from the same numbers; Jev is then asked, per
sentence, whether the half-day's log lines support it. Flags are reported as they come out, never fixed silently.

Jev answers are cached in signals/replay_checks.csv (by a hash of the log lines and the question), so rebuilding
the results reuses them instead of asking again. Jev never runs inside the simulation: it reads finished logs only.
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import yaml

from analysis.m3.raw import Raw
from analysis.m3.run import RAW, SCENARIOS, configure, load_settings
from engine.banks import generate_banks
from engine.episode import END_NAMES, RUNNING, draw_noise, episode_step, load_yaml, start_episode
from engine.funding import load_funding_settings
from engine.information import draw_info_randoms
from engine.policies import draw_policy_randoms, load_policies, policy_setup

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "results"
CACHE = ROOT / "signals" / "replay_checks.csv"
CACHE_FIELDS = ["key", "p_yes", "model"]
HALF = {0: "morning", 1: "afternoon"}
ROUTE_NAMES = {"leak": "leak of named borrowing", "announcement": "bank announcement (8-K)",
               "weekly_aggregate": "Fed weekly aggregate report", "supervisory": "supervisory reporting"}


def median_row(raw, scen, cfg):
    """The (row) whose A outcome at the tuning cell is the middle one (Clarification 31 B8)."""
    cell = cfg["replay"]["tuning_cell"]
    b = raw.batch(scen, "A", cell["stigma"], cell["supervision"])
    order = np.lexsort((b["row"], b["uncovered"], b["end_day"]))
    return int(b["row"][order[(len(order) - 1) // 2]])


def replay_row(row, runs, scen, policy, cfg):
    """Re-run one row under one policy; returns (state, records up to the row's end)."""
    conf = configure("-", "-", cfg)
    banks = generate_banks()
    n = len(banks["bank_id"])
    rows = {k: (np.repeat(v, runs)[[row]] if isinstance(v, np.ndarray) else v) for k, v in banks.items()}
    seed = cfg["seeds"][scen]
    steps = 2 * load_funding_settings()["time"]["days"]
    noise = draw_noise(seed, n * runs, steps, load_yaml("agents.yaml"))[[row]]
    rnd = {k: v[[row]] for k, v in draw_info_randoms(seed, n * runs).items()}
    opt = np.repeat(draw_policy_randoms(load_policies()["seed"], n)["opt_in_u"], runs)[[row]]
    setup = policy_setup(rows, policy, conf["pol"], {"test_u": rnd["test_u"], "opt_in_u": opt}, conf["fs"], conf["lcr"],
                         conf["info"])
    cell = cfg["replay"]["tuning_cell"]
    st = start_episode(setup["banks"], yaml.safe_load(SCENARIOS.read_text())[scen], noise, funding=conf["fs"],
                       behavior=conf["behavior"], info=conf["info"], stigma=cell["stigma"], supervision=cell["supervision"],
                       info_randoms=rnd, setup=setup)
    recs, delivered = [], []
    for _ in range(steps):
        before = {k: bool(v[0]) for k, v in st["delivered"].items()}
        r = episode_step(st)
        delivered.append([k for k, v in st["delivered"].items() if bool(v[0]) and not before[k]])
        recs.append(r)
        if st["end_state"][0] != RUNNING:
            break
    return st, setup, recs, delivered


def _f(x):
    return float(np.asarray(x).reshape(-1)[0])


def write_day(t, r, routes, st, last):
    """(log lines, sentences) for one half-day. Each sentence states only numbers in its own log line."""
    day, half = t // 2 + 1, HALF[t % 2]
    tag = f"day {day} {half}"
    out = []

    def add(actor, kind, route, log, text):
        out.append((actor, kind, route, f"{tag} | {log}", text))

    fast, slow, ins = _f(r["fast_out"]), _f(r["slow_out"]), _f(r["insured_out"])
    conf = _f(r["confidence"])
    if fast + slow + ins > 0.005 or t == 0:
        add("Depositors", "did", "", f"depositor confidence={conf:.2f}; withdrawals fast={fast:.2f} slow={slow:.2f} "
            f"insured={ins:.2f} $bn",
            f"Depositor confidence stood at {conf:.2f} (1 = calm); fast uninsured depositors withdrew ${fast:.2f}bn, slow "
            f"uninsured depositors ${slow:.2f}bn and insured depositors ${ins:.2f}bn.")
    for route in routes:
        add("Market", "saw", ROUTE_NAMES.get(route, route), f"information delivered via {route}",
            f"News of the bank's window borrowing reached observers through the {ROUTE_NAMES.get(route, route)}.")
    if _f(r["stwf_refused"]) + _f(r["repo_refused"]) > 0.005:
        add("Wholesale lenders", "did", "", f"refused to roll: wholesale={_f(r['stwf_refused']):.2f} repo={_f(r['repo_refused']):.2f} $bn",
            f"Wholesale lenders refused to roll ${_f(r['stwf_refused']):.2f}bn of funding and repo lenders "
            f"${_f(r['repo_refused']):.2f}bn.")
    pf, sc, sup = _f(r["decision_p_fail"]), _f(r["decision_stigma_cost"]), _f(r["decision_sup_cost"])
    borrow = bool(np.asarray(r["decision_borrow"]).reshape(-1)[0])
    if pf > 0.005 or borrow:
        add("Bank treasurer", "why", "", f"decision: p_fail={pf:.2f} stigma_cost={sc:.3f} supervisory_cost={sup:.3f} "
            f"borrow={'yes' if borrow else 'no'}",
            f"The treasurer put the chance of failing without the window at {pf:.0%}, against an expected stigma cost of "
            f"{sc:.3f} plus a supervisory cost of {sup:.3f}, so the bank {'decided to borrow' if borrow else 'did not borrow'}.")
    used = {"reserves": _f(r["used_reserves"]),
            "repo": sum(_f(r[k]) for k in r if k.startswith("used_repo_")),
            "Home Loan Bank": _f(r["used_fhlb_line"]) + _f(r["used_fhlb_above_line"]),
            "securities sales": _f(r["used_sale_level1"]) + _f(r["used_sale_level2a"]),
            "discount window": _f(r["dw_drawn"])}
    if sum(used.values()) > 0.005:
        parts = [f"{k} ${v:.2f}bn" for k, v in used.items() if v > 0.005]
        add("Bank", "did", "", "sources: " + " ".join(f"{k.replace(' ', '_')}={v:.2f}" for k, v in used.items()) + " $bn",
            "The bank raised cash from " + ", ".join(parts) + ".")
    owed = _f(r["unpaid_end"])
    if owed > 0.005:
        add("Bank", "did", "", f"unpaid at end of half-day={owed:.2f} $bn; uncovered={_f(r['shortfall']):.2f} $bn",
            f"At the end of the half-day the bank still owed ${owed:.2f}bn, of which ${_f(r['shortfall']):.2f}bn no "
            "source could cover.")
    if last:
        state = END_NAMES[int(st["end_state"][0])]
        add("Outcome", "did", "", f"episode ended: {state}",
            {"failed": "The bank failed at this point under the strict failure rule.",
             "stabilized": "The run calmed and the episode ended with the bank stabilized.",
             "reached the last day": "The bank reached day 30 without failing."}[state])
    return out


def build_replay(row, runs, scen, policy, cfg):
    st, setup, recs, delivered = replay_row(row, runs, scen, policy, cfg)
    banks = generate_banks()
    bank, run = row // runs, row % runs
    log, days = [], {}
    for t, (r, routes) in enumerate(zip(recs, delivered)):
        for actor, kind, route, line, text in write_day(t, r, routes, st, t == len(recs) - 1):
            log.append({"line": len(log) + 1, "text": line})
            days.setdefault(t // 2 + 1, []).append({"half": HALF[t % 2], "actor": actor, "kind": kind, "route": route,
                                                    "text": text, "log_line": len(log), "support_check": None})
    return {"scenario": scen, "policy": policy, "bank_id": str(banks["bank_id"][bank]), "run": int(run),
            "selection": "median run under A at the tuning cell (stigma 0.35, neutral), by end day then peak uncovered",
            "placeholder": False, "days": [{"day": d, "entries": e} for d, e in sorted(days.items())], "log": log}


# ---------- Jev support checks ----------

def _load_cache():
    if not CACHE.exists():
        return {}
    with open(CACHE, newline="") as f:
        return {r["key"]: r for r in csv.DictReader(f)}


def check(replays, cfg, ask=None):
    """Fill every support_check: one Noul question per sentence; state = that half-day's log lines."""
    if ask is None:
        from signals.jev_client import ask as jev_ask, noul
        ask = lambda state, qs: jev_ask(state, {k: noul(v) for k, v in qs.items()}, mock=False, tag=cfg["replay"]["tag"])
    cache = _load_cache()
    for rp in replays:
        lines = {x["line"]: x["text"] for x in rp["log"]}
        for day in rp["days"]:
            by_half = {}
            for en in day["entries"]:
                by_half.setdefault(en["half"], []).append(en)
            for half, entries in by_half.items():
                state = {"log_lines": [lines[en["log_line"]] for en in entries]}
                qs = {f"s{i}": f'{cfg["replay"]["question"]} Sentence: "{en["text"]}"' for i, en in enumerate(entries)}
                keys = {k: hashlib.sha256(json.dumps([state, q], sort_keys=True).encode()).hexdigest() for k, q in qs.items()}
                todo = {k: q for k, q in qs.items() if keys[k] not in cache}
                if todo:
                    res = ask(state, todo)
                    for k in todo:
                        cache[keys[k]] = {"key": keys[k], "p_yes": f"{float(res['answers'][k]['value']):.6f}", "model": res["model"]}
                    _save_cache(cache)
                for i, en in enumerate(entries):
                    p = float(cache[keys[f"s{i}"]]["p_yes"])
                    en["support_check"] = "flagged" if p < cfg["replay"]["flag_below"] else "supported"
                    en["p_supported"] = round(p, 4)
    return replays


def _save_cache(cache):
    with open(CACHE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CACHE_FIELDS)
        w.writeheader()
        w.writerows(sorted(cache.values(), key=lambda r: r["key"]))


def run(raw_folder=RAW, out=OUT, ask=None):
    cfg = load_settings()
    raw = Raw(raw_folder)
    reps = []
    for scen in ("S1", "S2"):
        row = median_row(raw, scen, cfg)
        for p in cfg["replay"]["policies"]:
            reps.append(build_replay(row, raw.runs, scen, p, cfg))
    check(reps, cfg, ask)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "replay.json").write_text(json.dumps(reps, indent=1, ensure_ascii=False) + "\n")
    return reps


if __name__ == "__main__":
    reps = run(*(Path(x) for x in sys.argv[1:]))
    flags = sum(en["support_check"] == "flagged" for rp in reps for d in rp["days"] for en in d["entries"])
    print(f"wrote {len(reps)} replays; {flags} sentence(s) flagged by Jev")
