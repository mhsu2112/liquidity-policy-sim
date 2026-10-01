"""The four out-of-sample checks (session M1.11; Clarification 16). Run with `make validate`.

All under policy A at the tuning cell (Clarification 15 item 2), with the frozen
settings. Nothing is adjusted to make a check pass: the criteria and every choice
are in config/validation/checks.yaml, fixed before the first check ran.

    1. Signature-like bank, S1                     2. First Republic-like bank, S1 + $30bn on day 5
    3. False alarm (S2) on all 40 banks            4. No shock on all 40 banks

Writes outputs/validation_results.json; validation/validation_report.py turns it into HTML.
Outcomes are read at each run's end half-day: nothing after a run ends counts (Clarification 10).
"""

import json
from pathlib import Path

import numpy as np
import yaml

from engine.banks import generate_banks
from engine.episode import FAILED, STABILIZED, draw_noise, episode_step, load_yaml, start_episode
from engine.frozen import frozen_fingerprint
from engine.information import draw_info_randoms
from engine.outcomes import episode_outcomes
from engine.policies import policy_setup
from engine.write_banks import ROOT
from validation.banks import midpoint_bank, remove_from_window
from validation.tune import load_tuning

CHECKS_PATH = ROOT / "config" / "validation" / "checks.yaml"
SCENARIOS_PATH = ROOT / "config" / "scenarios" / "scenarios.yaml"
OUT = ROOT / "outputs" / "validation_results.json"


def load(path):
    with open(path) as f:
        return yaml.safe_load(f)


def run(banks, shock, seed, steps, adjust_setup=None, inject=None):
    """Policy-A episodes at the tuning cell. Returns (state, deposit outflow per half-day counted to each end)."""
    n = len(banks["bank_id"])
    cell = load_tuning()["tuning_cell"]
    rnd = draw_info_randoms(seed, n)
    setup = policy_setup(banks, "A", randoms={"test_u": rnd["test_u"]})   # the status quo, as in every A run
    if adjust_setup:
        setup["placement"] = adjust_setup(setup["placement"], setup["banks"])
    st = start_episode(setup["banks"], shock, draw_noise(seed, n, steps, load_yaml("agents.yaml")), info_randoms=rnd,
                       stigma=cell["stigma"], supervision=cell["supervision"], strength_s=cell["strength_s"],
                       distress_shock=cell["distress_hit"], setup=setup)
    deposits_start = st["insured_deposits_bn"] + st["uninsured_deposits_bn"]
    out = []
    for t in range(steps):
        if inject:
            inject(st, t)
        r = episode_step(st)
        out.append(r["fast_out"] + r["slow_out"] + r["insured_out"])
    dep = np.stack(out, axis=1)
    counted = np.arange(steps)[None, :] <= st["end_step"][:, None]     # nothing after a run's end counts
    return st, np.where(counted, dep, 0.0), deposits_start


def check_signature(cfg, seed, runs, steps, shock):
    c = cfg["signature"]
    banks = midpoint_bank("SIG-VAL", c["archetype"], c["total_assets_bn"], c["uninsured_share_of_deposits"], runs)
    st, dep, d0 = run(banks, shock, seed, steps,
                      adjust_setup=lambda p, b: remove_from_window(p, b, c["capital_call_loans_bn"]))
    p = c["pass"]
    spd = 2
    failed_by = (st["end_state"] == FAILED) & (st["end_step"] < p["fail_by_day"] * spd)
    day1 = np.median(dep[:, :spd].sum(axis=1) / d0)
    lo, hi = p["day1_outflow_share_of_deposits"]
    return {"fail_by_day3_share": float(failed_by.mean()), "median_day1_outflow_share": float(day1),
            "median_day1_outflow_bn": float(np.median(dep[:, :spd].sum(axis=1))), "deposits_bn": float(d0[0]),
            "median_end_day": float(np.median(st["end_step"] // spd + 1)),
            "criteria": {"fail_by_day3": failed_by.mean() >= p["min_fail_share"], "day1_outflow": lo <= day1 <= hi},
            "pass": bool(failed_by.mean() >= p["min_fail_share"] and lo <= day1 <= hi)}


def check_first_republic(cfg, seed, runs, steps, shock):
    c = cfg["first_republic"]
    banks = midpoint_bank("FRC-VAL", c["archetype"], c["total_assets_bn"], c["uninsured_share_of_deposits"], runs)
    arrive = (c["consortium_day"] - 1) * 2      # the morning of day 5

    def consortium(st, t):
        # The March 16 consortium deposits: cash in, held as uninsured deposits that never run.
        if t == arrive:
            st["uninsured_deposits_bn"] += c["consortium_deposit_bn"]
            st["reserves_bn"] += c["consortium_deposit_bn"]
            st["total_assets_bn"] += c["consortium_deposit_bn"]

    st, dep, d0 = run(banks, shock, seed, steps, inject=consortium)
    o, p = episode_outcomes(st), c["pass"]
    survived = ~((st["end_state"] == FAILED) & (st["end_step"] < p["survive_past_day"] * 2))
    support = (o["official_support_bn"] + o["fhlb_peak_bn"]) / st["assets_start_bn"]
    outflow = dep[:, :p["outflow_by_day"] * 2].sum(axis=1)
    lo, hi = p["outflow_band_bn"]
    crit = {"survive_past_day5": survived.mean() >= p["min_survive_share"],
            "support_above_25pct": np.median(support) > p["min_support_share_of_assets"],
            "outflow_by_day10_in_band": lo <= np.median(outflow) <= hi}
    return {"survive_past_day5_share": float(survived.mean()), "median_support_share": float(np.median(support)),
            "median_support_bn": float(np.median(o["official_support_bn"] + o["fhlb_peak_bn"])),
            "median_window_bn": float(np.median(o["official_support_bn"])),
            "median_fhlb_bn": float(np.median(o["fhlb_peak_bn"])),
            "median_outflow_day10_bn": float(np.median(outflow)),
            "fail_within_30_share": float((st["end_state"] == FAILED).mean()),
            "criteria": {k: bool(v) for k, v in crit.items()}, "pass": bool(all(crit.values()))}


def forty(seed, runs, steps, shock):
    banks = generate_banks()
    rows = {k: (np.repeat(v, runs) if isinstance(v, np.ndarray) else v) for k, v in banks.items()}
    st, dep, _ = run(rows, shock, seed, steps)
    return banks, st, dep, episode_outcomes(st)


def check_false_alarm(cfg, seed, runs, steps, shock):
    c = cfg["false_alarm"]
    banks, st, dep, o = forty(seed, runs, steps, shock)
    n = len(banks["bank_id"])
    ok = (st["end_state"] != FAILED) & (o["peak_owed_bn"] <= 1e-9)    # survives with nothing ever owed
    support = o["official_support_bn"] / st["assets_start_bn"]
    by_bank = ok.reshape(n, runs).mean(axis=1)
    per_type = {}
    for a in dict.fromkeys(banks["archetype"]):
        m = np.repeat(banks["archetype"] == a, runs)
        per_type[a] = {"survive_share": float((st["end_state"][m] != FAILED).mean()),
                       "no_shortfall_share": float((o["peak_owed_bn"][m] <= 1e-9).mean()),
                       "median_support_share": float(np.median(support[m])),
                       "borrowed_share": float((o["official_support_bn"][m] > 0).mean()),
                       "median_outflow_share": float(np.median(dep[m].sum(axis=1)
                                                               / np.repeat(banks["insured_deposits_bn"]
                                                                           + banks["uninsured_deposits_bn"], runs)[m])),
                       "scored": a in c["scored_archetypes"]}
    scored = np.isin(banks["archetype"], c["scored_archetypes"])
    scored_runs = np.repeat(scored, runs)
    bank_pass = by_bank[scored] > 0.5
    med_support = float(np.median(support[scored_runs]))
    crit = {"banks_surviving_no_shortfall": bank_pass.mean() >= c["pass"]["min_bank_share"],
            "median_support_below_5pct": med_support < c["pass"]["max_median_support_share_of_assets"]}
    return {"scored_banks": int(scored.sum()), "scored_banks_passing": int(bank_pass.sum()),
            "scored_bank_share": float(bank_pass.mean()), "pooled_run_share": float(ok[scored_runs].mean()),
            "median_support_share_scored": med_support, "by_archetype": per_type,
            "failing_banks": [str(b) for b in banks["bank_id"][scored][~bank_pass]],
            "criteria": {k: bool(v) for k, v in crit.items()}, "pass": bool(all(crit.values()))}


def check_no_shock(cfg, seed, runs, steps):
    banks, st, dep, o = forty(seed, runs, steps, 0.0)
    n = len(banks["bank_id"])
    stable = (st["end_state"] == STABILIZED) & (dep.sum(axis=1) == 0)
    by_bank = stable.reshape(n, runs).all(axis=1)
    return {"banks_stable": int(by_bank.sum()), "runs_stable_share": float(stable.mean()),
            "max_outflow_bn": float(dep.sum(axis=1).max()),
            "median_stabilized_day": float(np.median(st["end_step"] // 2 + 1)),
            "criteria": {"all_40_stable_no_outflow": bool(by_bank.all())}, "pass": bool(by_bank.all())}


def main():
    cfg, sc = load(CHECKS_PATH), load(SCENARIOS_PATH)
    fs = load_yaml("funding.yaml")["time"]
    steps = fs["steps_per_day"] * fs["days"]
    seed, runs = cfg["seed"], cfg["runs"]
    results = {"fingerprint": frozen_fingerprint(), "runs": runs, "seed": seed, "shocks": sc,
               "signature": check_signature(cfg, seed, runs, steps, sc["S1"]),
               "first_republic": check_first_republic(cfg, seed, runs, steps, sc["S1"]),
               "false_alarm": check_false_alarm(cfg, seed, runs, steps, sc["S2"]),
               "no_shock": check_no_shock(cfg, seed, runs, steps)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2, default=bool))
    for k in ("signature", "first_republic", "false_alarm", "no_shock"):
        print(f"{k:15s} {'PASS' if results[k]['pass'] else 'FAIL'}  {results[k]['criteria']}")
    print(f"Frozen fingerprint: {results['fingerprint']}. Wrote {Path(OUT).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
