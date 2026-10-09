"""Why SVB-like S1 survival on the grace count is lower under B than A (session v0.1-E; diagnostic, not scored).

    python -m analysis.m3.grace_causes        (or: make grace-causes; needs make results first)

Takes the paired runs (same bank, run and cell) where A survives on the grace count (Amendment 6: failed only for
timing, cash arriving by the next morning) and B fails on it. Re-runs only those rows, with the engine unchanged and
the run's own draws (analysis/m3/run.py), after checking each one against the saved run. Then counts them by cause,
first match, in the owner's order:
    1 non-timing failure       every pair, by construction: B failing on the grace count means its failure was not
                               covered by cash arriving by the next morning
    2 known draw               under B, a window draw became known and was read as distress before the failure
    3 Home Loan Bank collateral B's setup moved loans pledged to the Home Loan Bank to the Fed for that bank
    4 other
Because category 1 takes every pair, it also prints the overlap of 2 and 3, the failure days, and one worked example
(bank SVB-08, run 6, at the tuning cell), A and B half-day by half-day. Writes outputs/v0.1/diagnostics/5_grace_causes.csv.
"""

import csv
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

import analysis.m3.run as R
from analysis.m3 import replay
from analysis.m3.raw import Raw
from engine.episode import FAILED, RUNNING, episode_step, start_episode
from engine.information import NEVER
from engine.policies import policy_setup

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "v0.1" / "diagnostics" / "5_grace_causes.csv"
EXAMPLE = {"row": 1406, "runs": 200}          # SVB-08, run 6: chosen as the first "other" pair at the tuning cell


def _rerun(policy, x, u, idx, ctx):
    """Re-run the given rows under one policy in one cell; returns (state, setup)."""
    conf, rows_all, noise, rnd, opt, shock = ctx
    rows = {k: (v[idx] if isinstance(v, np.ndarray) else v) for k, v in rows_all.items()}
    rr = {k: v[idx] for k, v in rnd.items()}
    setup = policy_setup(rows, policy, conf["pol"], {"test_u": rr["test_u"], "opt_in_u": opt[idx]}, conf["fs"],
                         conf["lcr"], conf["info"])
    st = start_episode(setup["banks"], shock, noise[idx], funding=conf["fs"], behavior=conf["behavior"],
                       info=conf["info"], stigma=x, supervision=u, info_randoms=rr, setup=setup)
    for _ in range(noise.shape[1]):
        episode_step(st)
        if (st["end_state"] != RUNNING).all():
            break
    return st, setup


def pairs(raw_folder=R.RAW, scen="S1", bank_type="svb_like"):
    """One record per pair, after checking each re-run row against the saved run."""
    cfg, raw = R.load_settings(), Raw(raw_folder)
    conf = R.configure("-", "-", cfg)
    rows_all, _ = R._rows(raw.runs, conf)
    noise, rnd, opt = R._draws(scen, raw.runs, cfg)
    ctx = (conf, rows_all, noise, rnd, opt, yaml.safe_load(R.SCENARIOS.read_text())[scen])
    keep = raw.type_rows(bank_type)
    plan = R.load_run_plan()["cells"]["main"]
    out = []
    for x in plan["stigma"]:
        for u in plan["supervision"]:
            a, b = raw.batch(scen, "A", x, u), raw.batch(scen, "B", x, u)
            sel = np.isin(a["row"], keep) & ~(a["failed"] & ~a["grace"]) & (b["failed"] & ~b["grace"])
            idx = a["row"][sel]
            if not len(idx):
                continue
            sa, _ = _rerun("A", x, u, idx, ctx)
            sb, pb = _rerun("B", x, u, idx, ctx)
            for st, saved in ((sa, a), (sb, b)):
                if not (np.array_equal(st["end_state"] == FAILED, saved["failed"][sel])
                        and np.array_equal(st["end_step"] // 2 + 1, saved["end_day"][sel])):
                    raise SystemExit(f"STOP: re-run differs from the saved run at stigma {x}, {u}")
            moved = pb["placement"]["fed_loans_from_fhlb_bn"] > 1e-9
            for i, row in enumerate(idx):
                out.append({"stigma": x, "supervision": u, "row": int(row),
                            "a_day": int(sa["end_step"][i] // 2 + 1), "b_day": int(sb["end_step"][i] // 2 + 1),
                            "known": bool(sb["distress_from"][i] != NEVER and sb["distress_from"][i] <= sb["end_step"][i]),
                            "a_known": bool(sa["distress_from"][i] != NEVER and sa["distress_from"][i] <= sa["end_step"][i]),
                            "moved": bool(moved[i])})
    return out


def cause(p):
    """First match after category 1 (which every pair meets): the cause behind the non-timing failure."""
    return "known draw" if p["known"] else "Home Loan Bank collateral moved" if p["moved"] else "other"


def counts(ps):
    c = Counter(cause(p) for p in ps)
    return [("1 non-timing failure (all, by construction)", len(ps)), ("2 known draw deepened the run", c["known draw"]),
            ("3 collateral moved away from the Home Loan Bank", c["Home Loan Bank collateral moved"]),
            ("4 other", c["other"])]


def example(cfg=None):
    cfg = cfg or R.load_settings()
    return {p: replay.build_replay(EXAMPLE["row"], EXAMPLE["runs"], "S1", p, cfg)["log"] for p in ("A", "B")}


def main(raw_folder=R.RAW, out=OUT):
    ps = pairs(raw_folder)
    rows = counts(ps)
    for k, v in rows:
        print(f"{k:52s} {v:6,d}")
    print("overlap (known draw, collateral moved):", dict(Counter((p["known"], p["moved"]) for p in ps)))
    print("A known before its failure:", sum(p["a_known"] for p in ps))
    print("A failure day:", dict(sorted(Counter(p["a_day"] for p in ps).items())),
          "| B failure day:", dict(sorted(Counter(p["b_day"] for p in ps).items())))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cause (first match; diagnostic, not scored)", "pairs"])
        w.writerows(rows)
    if R.load_run_plan()["runs_per_cell"] == EXAMPLE["runs"]:
        for p, log in example().items():
            print(f"\nWorked example under {p} (SVB-08, run 6, stigma 0.35, neutral):")
            for line in log:
                print("  ", line["text"])
    print(f"\nwrote {out}")
    return ps


if __name__ == "__main__":
    main()
