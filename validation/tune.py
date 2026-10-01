"""Tune the five behavioral settings on the SVB validation bank (session M1.10; Clarification 15).

Policy A only, the SVB validation bank only, scenario S1 only (news shock 0.50 on day 1), at
the tuning cell of Clarification 15 item 2. Nothing else is run: no S2, no 40-bank sample, no
other policy.

Method (plain English, fixed before the first run; see the M1.10 plan):
1. Each setting is run 200 times with the SAME random draws, for days 1-2 (4 half-days).
2. Measured: D1 = deposits withdrawn on day 1; C2 = withdrawals requested through day 2;
   P = share of runs that fail by the end of day 2.
3. Fit score = ((D1 - 42)/42)^2 + ((C2 - 140)/140)^2 + (1 - P)^2 (0 = perfect).
4. Stage 1 coarse grid; stage 2 finer grid around the best point.
5. A setting whose whole grid range moves the score by less than 0.01 (others at the best fit)
   is "not identified" and keeps its pre-tuning value.
6. "Almost as well": both outflow targets within +/-10% and P >= 90%.

Run with `make tune`. Writes outputs/tuning_grid.csv and outputs/tuning_result.json.
"""

import copy
import itertools
import json
import time
from pathlib import Path

import numpy as np
import yaml

from engine.episode import RUNNING, FAILED, draw_noise, load_yaml, run_episode   # noqa: F401
from engine.funding import load_funding_settings
from engine.information import draw_info_randoms
from engine.write_banks import ROOT, write_csv
from validation.svb_bank import build_svb

TUNING_PATH = ROOT / "config" / "validation" / "tuning.yaml"
OUT_GRID = ROOT / "outputs" / "tuning_grid.csv"
OUT_RESULT = ROOT / "outputs" / "tuning_result.json"
NAMES = ("a", "theta", "c", "roll", "lag", "impact")   # impact: multiple of the Clarification 5 starting values
VECTOR = ("a", "theta", "c", "roll")                   # these can differ row by row in one batch
CHUNK_ROWS = 60_000                                     # keeps memory near 200 MB
BEHAVIOR_FILE = "params_frozen.yaml"                    # the engine's behavior settings file (structure only)


def load_tuning(path=TUNING_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


def behavior_for(base, a, theta, c, roll, lag):
    """The behavior settings dict the engine reads, with per-row arrays for a, theta, c and roll."""
    b = copy.deepcopy(base)
    b["depositor_sensitivity"]["value"] = a
    b["depositor_sensitivity"]["tolerance_theta"]["value"] = theta
    b["coordination_strength"]["value"] = c
    b["wholesale_roll_threshold"]["value"] = roll
    b["slow_depositor_lag_steps"]["value"] = int(lag)
    return b


def funding_for(fs, impact, start_impact):
    f = copy.deepcopy(fs)
    f["securities"]["price_impact_per_bn"] = {k: v * impact for k, v in start_impact.items()}
    return f


def evaluate(settings, cfg, base_behavior, fs, start_impact):
    """Run every setting (a list of dicts) and return D1, C2, P and the half-day outflow means for each."""
    runs, steps = cfg["runs_per_setting"], cfg["half_days"]
    agents = load_yaml("agents.yaml")
    noise1 = draw_noise(cfg["seed"], runs, steps, agents)       # the same draws for every setting
    rnd1 = draw_info_randoms(cfg["seed"], runs)
    cell = cfg["tuning_cell"]
    out = [None] * len(settings)
    groups = {}
    for i, s in enumerate(settings):                             # lag and impact are fixed per batch
        groups.setdefault((s["lag"], s["impact"]), []).append(i)
    per_chunk = max(CHUNK_ROWS // runs, 1)
    for (lag, impact), idx in groups.items():
        f = funding_for(fs, impact, start_impact)
        for k in range(0, len(idx), per_chunk):
            part = idx[k:k + per_chunk]
            m = len(part)
            rows = m * runs
            col = lambda name: np.repeat([settings[i][name] for i in part], runs)   # noqa: E731
            beh = behavior_for(base_behavior, col("a"), col("theta"), col("c"), col("roll"), lag)
            banks, svb = build_svb(rows)
            st, recs = run_episode(
                banks, cfg["s1_shock"], np.tile(noise1, (m, 1)), funding=f, behavior=beh,
                info_randoms={key: np.tile(v, m) for key, v in rnd1.items()},
                tested=np.full(rows, svb["tested"]), stigma=cell["stigma"], supervision=cell["supervision"],
                strength_s=cell["strength_s"], distress_shock=cell["distress_hit"])
            dep = np.stack([r["fast_out"] + r["slow_out"] + r["insured_out"] for r in recs], axis=1)
            dep = dep.reshape(m, runs, steps)
            failed = ((st["end_state"] == FAILED) & (st["end_step"] < steps)).reshape(m, runs)
            for j, i in enumerate(part):
                d = dep[j].mean(axis=0)                           # mean outflow per half-day
                out[i] = {"D1": float(d[:2].sum()), "C2": float(d[:4].sum()), "P": float(failed[j].mean()),
                          "half_day_bn": [float(x) for x in d]}
    return out


def score(r, t):
    return ((r["D1"] - t["day1_outflow_bn"]) / t["day1_outflow_bn"]) ** 2 \
        + ((r["C2"] - t["day2_cumulative_bn"]) / t["day2_cumulative_bn"]) ** 2 + (1 - r["P"]) ** 2


def near(r, t, tol):
    return (abs(r["D1"] / t["day1_outflow_bn"] - 1) <= tol["outflow_rel"]
            and abs(r["C2"] / t["day2_cumulative_bn"] - 1) <= tol["outflow_rel"] and r["P"] >= tol["min_fail_share"])


def grid_settings(grid):
    return [dict(zip(NAMES, v)) for v in itertools.product(*(grid[n] for n in NAMES))]


def neighbours(values, best, points):
    """Stage 2: `points` evenly spaced values between the best value's neighbours on the coarse grid."""
    v = sorted(values)
    i = v.index(best)
    lo, hi = v[max(i - 1, 0)], v[min(i + 1, len(v) - 1)]
    return sorted(set(np.round(np.linspace(lo, hi, points), 6).tolist()))


def main():
    cfg = load_tuning()
    t, tol = cfg["targets"], cfg["near_fit"]
    base_behavior = load_yaml(BEHAVIOR_FILE)   # structure only: every tuned value is replaced below
    fs = load_funding_settings()
    start_impact = cfg["start_impact_per_bn"]
    t0 = time.perf_counter()

    # Stage 1: the coarse grid.
    stage1 = grid_settings(cfg["stage1_grid"])
    res1 = evaluate(stage1, cfg, base_behavior, fs, start_impact)
    best1 = min(range(len(stage1)), key=lambda i: score(res1[i], t))
    print(f"Stage 1: {len(stage1):,} settings, best score {score(res1[best1], t):.4f} at {stage1[best1]}")

    # Stage 2: finer grid around the stage-1 best.
    g2 = {}
    for n in NAMES:
        if n == "lag":
            b = stage1[best1]["lag"]
            g2[n] = sorted({max(1, b - 1), b, b + 1})
        else:
            g2[n] = neighbours(cfg["stage1_grid"][n], stage1[best1][n], cfg["stage2_points"])
    stage2 = grid_settings(g2)
    res2 = evaluate(stage2, cfg, base_behavior, fs, start_impact)
    allset, allres = stage1 + stage2, res1 + res2
    stage = [1] * len(stage1) + [2] * len(stage2)
    best = min(range(len(allset)), key=lambda i: score(allres[i], t))
    print(f"Stage 2: {len(stage2):,} settings, best score {score(allres[best], t):.4f} at {allset[best]}")

    # Identification: move one setting across its whole coarse grid, the others at the best.
    ident, profiles = {}, {}
    for n in NAMES:
        trial = [{**allset[best], n: v} for v in cfg["stage1_grid"][n]]
        r = evaluate(trial, cfg, base_behavior, fs, start_impact)
        sc = [score(x, t) for x in r]
        profiles[n] = {"values": cfg["stage1_grid"][n], "scores": sc}
        ident[n] = (max(sc) - min(sc)) >= cfg["identified_min_score_range"]
    frozen = {n: (allset[best][n] if ident[n] else cfg["pre_tuning"][n]) for n in NAMES}
    final = evaluate([frozen], cfg, base_behavior, fs, start_impact)[0]
    print(f"Identified: {ident}. Frozen: {frozen}. Final: D1 {final['D1']:.1f}, C2 {final['C2']:.1f}, "
          f"P {final['P']:.2f}, score {score(final, t):.4f}")

    near_idx = [i for i in range(len(allset)) if near(allres[i], t, tol)]
    ranges = {n: [min(allset[i][n] for i in near_idx), max(allset[i][n] for i in near_idx)] if near_idx else None
              for n in NAMES}
    print(f"Almost as well: {len(near_idx):,} of {len(allset):,} settings. Ranges: {ranges}")

    cols = {n: np.array([s[n] for s in allset]) for n in NAMES}
    cols.update(stage=np.array(stage), D1_bn=np.array([r["D1"] for r in allres]),
                C2_bn=np.array([r["C2"] for r in allres]), fail_by_day2=np.array([r["P"] for r in allres]),
                score=np.array([score(r, t) for r in allres]),
                near_fit=np.array(["yes" if near(r, t, tol) else "no" for r in allres]))
    write_csv(cols, OUT_GRID)
    result = {"best_searched": allset[best], "best_searched_result": allres[best],
              "best_searched_score": score(allres[best], t), "identified": ident, "profiles": profiles,
              "frozen": frozen, "final": final, "final_score": score(final, t),
              "near_fit_count": len(near_idx), "settings_evaluated": len(allset), "near_fit_ranges": ranges,
              "start_impact_per_bn": start_impact, "seconds": time.perf_counter() - t0}
    OUT_RESULT.write_text(json.dumps(result, indent=2))
    print(f"Wrote {OUT_GRID.relative_to(ROOT)} and {OUT_RESULT.relative_to(ROOT)} "
          f"({result['seconds']:.0f} s).")


if __name__ == "__main__":
    main()
