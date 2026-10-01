"""Speed and repeatability under policy A only (run with `make benchmark`; session M1.9).

10,000 episodes at once (the 40 banks x 250 runs), spread over all 35 stigma x
supervision cells so every part of the engine is used. Policy A only (project
Rule 2): no other policy is run. The shock is a PLACEHOLDER for S1 (M1.10 sets
the real one); timing runs all 60 half-days, so it does not depend on the shock.

Prints the time, "identical: yes" after the same seed twice (every output,
compared through a fingerprint of every number), that a different seed changes
results, peak memory, and the M3 run plan with its projected time. Writes
outputs/benchmark.txt and outputs/run_plan.csv.
"""

import hashlib
import resource
import sys
import time

import numpy as np

from engine.banks import SETTINGS_PATH, generate_banks
from engine.episode import draw_noise, load_yaml, run_episode
from engine.information import INFO_SETTINGS_PATH, draw_info_randoms
from engine.outcomes import episode_outcomes
from engine.policies import POLICY_SETTINGS_PATH, load_policies
from engine.run_plan import RUN_PLAN_PATH, count_runs, load_run_plan, totals
from engine.write_banks import ROOT, stamps, write_csv

OUT_TXT = ROOT / "outputs" / "benchmark.txt"
OUT_PLAN = ROOT / "outputs" / "run_plan.csv"


def fingerprint(x, h=None):
    """A SHA-256 fingerprint of every number in an output (arrays, nested dicts, lists).

    Two runs with the same fingerprint have the same value in every cell of every array.
    """
    h = h or hashlib.sha256()
    if isinstance(x, np.ndarray):
        h.update(str((x.dtype, x.shape)).encode())
        h.update(np.ascontiguousarray(x).tobytes() if x.dtype != object else repr(x.tolist()).encode())
    elif isinstance(x, dict):
        for k in sorted(x, key=str):
            h.update(str(k).encode())
            fingerprint(x[k], h)
    elif isinstance(x, (list, tuple)):
        for v in x:
            fingerprint(v, h)
    elif isinstance(x, set):
        h.update(repr(sorted(x, key=str)).encode())
    else:
        h.update(repr(x).encode())
    return h


def benchmark_rows(plan, banks):
    """The 40 banks repeated, and each row's stigma x supervision cell (all 35, cycling)."""
    m = plan["benchmark"]["runs_per_bank"]
    rows = {k: (np.tile(v, m) if isinstance(v, np.ndarray) else v) for k, v in banks.items()}
    g = plan["cells"]["main"]
    cells = [(s, v) for s in g["stigma"] for v in g["supervision"]]
    n = len(rows["bank_id"])
    pick = np.arange(n) % len(cells)
    stigma = np.array([cells[i][0] for i in pick])
    supervision = np.array([cells[i][1] for i in pick], dtype=object)
    return rows, stigma, supervision


def run_batch(rows, stigma, supervision, shock, seed, steps, agents, early_stop=False):
    """One batch of policy-A episodes. Returns (final state, records, outcomes, seconds)."""
    n = len(rows["bank_id"])
    noise, randoms = draw_noise(seed, n, steps, agents), draw_info_randoms(seed, n)
    t0 = time.perf_counter()
    st, recs = run_episode(rows, shock, noise, info_randoms=randoms, stigma=stigma, supervision=supervision,
                           stop_when_all_ended=early_stop)
    seconds = time.perf_counter() - t0
    return st, recs, episode_outcomes(st), seconds


def peak_memory_mb():
    # macOS reports bytes, Linux kilobytes.
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 1e6 if sys.platform == "darwin" else peak / 1e3


def main():
    plan, pol_cfg, agents = load_run_plan(), load_policies(), load_yaml("agents.yaml")
    bm = plan["benchmark"]
    fs_time = load_yaml("funding.yaml")["time"]
    steps = fs_time["steps_per_day"] * fs_time["days"]
    rows, stigma, supervision = benchmark_rows(plan, generate_banks())
    n = len(rows["bank_id"])
    lines = []
    say = lambda s="": (print(s), lines.append(s))   # noqa: E731

    say(f"Benchmark, policy A only: {n:,} episodes at once ({n // 40} per bank), all {steps} half-days.")
    say(f"Shock {bm['shock']} is a PLACEHOLDER for S1 (set in M1.10). Behavior settings are M1.10 placeholders.")
    st, recs, out1, t1 = run_batch(rows, stigma, supervision, bm["shock"], bm["seed"], steps, agents)
    first = fingerprint([st, recs, out1]).hexdigest()
    del st, recs
    st, recs, out2, t2 = run_batch(rows, stigma, supervision, bm["shock"], bm["seed"], steps, agents)
    second = fingerprint([st, recs, out2]).hexdigest()
    del st, recs
    per_run = min(t1, t2) / n
    say(f"Time: {t1:.2f} s and {t2:.2f} s for the two runs; {per_run * 1e6:.0f} microseconds per episode.")
    say(f"Same seed twice, every output compared: identical: {'yes' if first == second else 'NO'}")

    _, _, out3, _ = run_batch(rows, stigma, supervision, bm["shock"], bm["other_seed"], steps, agents)
    differ = np.zeros(n, bool)
    for k, v in out1.items():
        differ |= ~((v == out3[k]) | (np.isnan(v) & np.isnan(out3[k])) if v.dtype.kind == "f" else v == out3[k])
    say(f"Different seed: results differ: {'yes' if differ.any() else 'NO'} ({differ.sum():,} of {n:,} episodes differ)")
    _, recs_e, _, t4 = run_batch(rows, stigma, supervision, bm["shock"], bm["seed"], steps, agents, early_stop=True)
    say(f"With early stopping (every row ended): {t4:.2f} s ({len(recs_e)} of {steps} half-days).")
    say(f"Peak memory: {peak_memory_mb():,.0f} MB (one {n:,}-episode batch with every half-day record kept).")

    rows_plan = count_runs(plan, pol_cfg)
    tot = totals(rows_plan)
    hours = tot["total"] * per_run / 3600
    say()
    say("M3 run plan (config/run_plan.yaml; Clarification 14):")
    for block, setting, points, pol, sc, b, cells, runs in rows_plan:
        say(f"  {block:17s} {setting:30s} {points} pt x {pol} pol x {sc} sc x {b} banks x {cells} cells: {runs:>12,}")
    say(f"  {'total':17s} {'':30s} {'':>52s}  {tot['total']:>12,}")
    say(f"Projected time: {hours * 60:.0f} minutes at the measured rate; {hours * plan['timing']['margin']:.1f} hours "
        f"with a {plan['timing']['margin']}x margin. Limit: {plan['timing']['limit_hours']} hours.")

    paths = (SETTINGS_PATH, POLICY_SETTINGS_PATH, INFO_SETTINGS_PATH, RUN_PLAN_PATH)
    stamp = {k: v[0] for k, v in stamps(1, *paths).items()}
    OUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    OUT_TXT.write_text("\n".join(lines + ["", " | ".join(f"{k}: {v}" for k, v in stamp.items())]) + "\n")
    cols = {k: np.array([r[i] for r in rows_plan]) for i, k in
            enumerate(["block", "setting", "points", "policies", "scenarios", "banks", "cells", "runs"])}
    cols["runs_per_cell"] = np.full(len(rows_plan), plan["runs_per_cell"])
    cols.update(stamps(len(rows_plan), *paths))
    write_csv(cols, OUT_PLAN)
    print(f"Wrote {OUT_TXT.relative_to(ROOT)} and {OUT_PLAN.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
