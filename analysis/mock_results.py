"""Mock result files for laying out the M3 report (session M3.0; Clarification 28).

MOCK DATA — LAYOUT ONLY — NOT RESULTS.

Every number here is a random draw with a fixed seed, so the report pages can be designed before any
policy comparison exists. Three rules keep the mock from leaking or pre-judging an answer:

1. It never imports the engine (or agents, validation, signals, cost) and never runs an episode.
2. It never reads anything in outputs/. It reads only config files, for the names of policies, cells
   and bank types, and for the stamp. It writes only to outputs/mock/ (git-ignored).
3. Every policy's numbers come from the same random distributions, and every lead / tie / trade-off
   label is drawn uniformly, so no policy is favoured. tests/test_report_shells.py checks rules 1 and 2.

The one fixed value is A's annual cost of zero: costs are measured relative to A by construction
(contract 6; H6), which is a definition, not a result.

Run with `make mock-report`.
"""

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from analysis.results_schema import (COMPARISONS, FEATURES, HYPOTHESIS_PARTS, LABELS, METRICS, OPTION_C_DEFAULTS,
                                     OPTION_C_POLICIES, OUTCOMES, RELEASED, SCHEMA_VERSION, TIMING_BANDS, UPTAKE,
                                     COLUMNS, metric_applies, vocabulary)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "mock"
SEED = 20261005          # M3.0 session date; any fixed number would do
CELLS_PER_GRID = 35      # contract 5: 7 stigma x 5 supervision
BANKS_PER_TYPE = 10      # contract 1

# Ranges for the random draws. Wide and the same for every policy: they only need to look like the
# kind of number each column will hold, so the layout can be judged.
RANGES = {
    "survival_rate": (0.0, 1.0), "liquidity_shortfall_bn": (0, 30), "support_peak_bn": (0, 60),
    "support_total_bn": (0, 150), "annual_cost_m": (-80, 80), "buffer_gap_pp": (0, 20),
    "effective_stigma": (0, 0.9), "routine_borrowing_per_quarter": (0, 3), "hesitation_gap_days": (0, 5),
    "false_comfort": (0, 0.3), "needless_borrowing_bn": (0, 5),
}
DIFF_SCALE = {"survival_rate": 0.15, "liquidity_shortfall_bn": 8, "support_peak_bn": 15, "support_total_bn": 30,
              "annual_cost_m": 60, "buffer_gap_pp": 8, "effective_stigma": 0.2, "routine_borrowing_per_quarter": 1.5,
              "hesitation_gap_days": 2, "false_comfort": 0.1, "needless_borrowing_bn": 2}


def stamp():
    """Commit, settings hash and frozen-settings fingerprint, computed from config without the engine."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    commit = (git("rev-parse", "--short=12", "HEAD") or "unknown") + ("-dirty" if git("status", "--porcelain") else "")
    digest = hashlib.sha256()
    for p in sorted((ROOT / "config").rglob("*.yaml")):
        digest.update(p.read_bytes())
    # Same recipe as engine/frozen.py (a test checks they agree), repeated so the mock never imports the engine.
    frozen = yaml.safe_load((ROOT / "config" / "params_frozen.yaml").read_text())
    fingerprint = hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()[:16]
    jev_cfg = ROOT / "config" / "jev.yaml"
    jev_model = (yaml.safe_load(jev_cfg.read_text())["model"] if jev_cfg.exists()
                 else "not recorded: config/jev.yaml is not on this branch")
    return {"git_commit": commit, "config_hash": digest.hexdigest()[:16], "params_fingerprint": fingerprint,
            "jev_estimate_version": "none (mock)", "jev_model": jev_model}


def estimate_with_interval(rng, centre_scale):
    """A random paired difference and a random, possibly lopsided, 90% interval around it."""
    d = rng.uniform(-centre_scale, centre_scale)
    return d, d - rng.uniform(0.1, 0.6) * centre_scale, d + rng.uniform(0.1, 0.6) * centre_scale


def fmt(x):
    return "" if x is None else f"{x:.6g}"


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS[path.name])
        w.writeheader()
        w.writerows(rows)


def scorecard(rng, v, runs_per_cell):
    rows, bands = [], []
    n_runs = runs_per_cell * CELLS_PER_GRID * BANKS_PER_TYPE
    for p in v["policies"]:
        for s in v["scenarios"]:
            for b in v["bank_types"]:
                survival = None
                for m in METRICS:
                    if not metric_applies(m, p, s):
                        continue
                    row = {"policy": p, "scenario": s, "bank_type": b, "metric": m, "n_runs": n_runs}
                    if m == "timing_only_upper_bound":
                        failures = round(n_runs * (1 - survival))
                        row["value"] = int(rng.integers(0, failures + 1))
                    else:
                        lo, hi = RANGES[m]
                        value = 0.0 if (m == "annual_cost_m" and p == "A") else rng.uniform(lo, hi)
                        row["value"] = fmt(value)
                        if p != "A":
                            row["diff_vs_a"], row["diff_lo"], row["diff_hi"] = map(fmt, estimate_with_interval(rng, DIFF_SCALE[m]))
                        survival = value if m == "survival_rate" else survival
                    rows.append(row)
                failures = round(n_runs * (1 - survival))
                split = rng.multinomial(failures, rng.dirichlet(np.ones(len(TIMING_BANDS))))
                for band, k in zip(TIMING_BANDS, split):
                    bands.append({"policy": p, "scenario": s, "bank_type": b, "band": band, "failures": int(k),
                                  "share": fmt(k / failures) if failures else ""})
    return rows, bands


def tradeoff(rng, v):
    rows = []
    for c in COMPARISONS:
        for s in v["scenarios"]:
            for b in v["bank_types"]:
                for x in v["stigma"]:
                    for u in v["supervision"]:
                        sd, sl, sh = estimate_with_interval(rng, 0.15)
                        fd, fl, fh = estimate_with_interval(rng, 8)
                        rows.append({"comparison": c, "scenario": s, "bank_type": b, "stigma": str(x),
                                     "supervision": u, "label": rng.choice(LABELS),
                                     "cost_diff_m": fmt(rng.uniform(-80, 80)),
                                     "survival_diff": fmt(sd), "survival_lo": fmt(sl), "survival_hi": fmt(sh),
                                     "shortfall_diff_bn": fmt(fd), "shortfall_lo": fmt(fl), "shortfall_hi": fmt(fh)})
    return rows


def reversal(rng, v, marker):
    rows = []
    for c in COMPARISONS:
        for s in v["scenarios"]:
            for b in v["bank_types"]:
                for u in v["supervision"]:
                    row = {"comparison": c, "scenario": s, "bank_type": b, "supervision": u,
                           "label_at_marker": rng.choice(LABELS)}
                    for side, points in (("down", [x for x in v["stigma"] if x < marker]),
                                         ("up", [x for x in v["stigma"] if x > marker])):
                        # Half the time the label never changes on that side of the grid.
                        hit = points and rng.random() < 0.5
                        row[f"{side}_distance"] = fmt(abs(rng.choice(points) - marker)) if hit else ""
                        others = [x for x in LABELS if x != row["label_at_marker"]]
                        row[f"{side}_label"] = rng.choice(others) if hit else ""
                    rows.append(row)
    return rows


def frontier(rng, v):
    rows = []
    for p in v["policies"]:
        for s in v["scenarios"]:
            for b in v["bank_types"]:
                cost = 0.0 if p == "A" else rng.uniform(-80, 80)
                surv, short = rng.uniform(0.05, 0.95), rng.uniform(1, 25)
                rows.append({"policy": p, "scenario": s, "bank_type": b,
                             "cost_m": fmt(cost), "cost_lo": fmt(cost - rng.uniform(0, 20)), "cost_hi": fmt(cost + rng.uniform(0, 20)),
                             "survival": fmt(surv), "survival_lo": fmt(surv - rng.uniform(0, 0.05)), "survival_hi": fmt(surv + rng.uniform(0, 0.05)),
                             "shortfall_bn": fmt(short), "shortfall_lo": fmt(short - rng.uniform(0, 1)), "shortfall_hi": fmt(short + rng.uniform(0, 1))})
    return rows


def option_c(rng, v):
    rows = []
    for p in OPTION_C_POLICIES:
        for s in v["scenarios"]:
            for b in v["bank_types"]:
                for up in UPTAKE:
                    for rel in RELEASED:
                        run = up == OPTION_C_DEFAULTS["uptake"] or rel == OPTION_C_DEFAULTS["hqla_released"]
                        d, lo, hi = estimate_with_interval(rng, 0.15) if run else (None, None, None)
                        rows.append({"policy": p, "scenario": s, "bank_type": b, "uptake": str(up), "hqla_released": str(rel),
                                     "run": "true" if run else "false", "survival_diff": fmt(d), "survival_lo": fmt(lo),
                                     "survival_hi": fmt(hi), "cost_m": fmt(rng.uniform(-80, 80)) if run else ""})
    return rows


def attribution(rng, v):
    rows = []
    for f in FEATURES:
        for s in v["scenarios"]:
            for b in v["bank_types"]:
                for o in OUTCOMES:
                    c, lo, hi = estimate_with_interval(rng, 0.1 if o == "survival_rate" else 5)
                    rows.append({"feature": f, "scenario": s, "bank_type": b, "outcome": o,
                                 "contribution": fmt(c), "lo": fmt(lo), "hi": fmt(hi)})
    return rows


def replay(rng, v):
    """Three days of obviously fake placeholder text, for one randomly chosen scenario and policy."""
    log, days = [], []
    for day in (1, 2, 3):
        entries = []
        for half, actor, kind, route, text in [
            ("morning", "Fast uninsured depositors", "saw", "leak of named borrowing",
             f"[PLACEHOLDER day {day}] Fast depositors saw a made-up headline about Lorem Bank."),
            ("morning", "Fast uninsured depositors", "did", "",
             f"[PLACEHOLDER day {day}] They withdrew an invented amount, $X bn."),
            ("afternoon", "Bank treasurer", "why", "",
             f"[PLACEHOLDER day {day}] The treasurer compared two fake numbers and chose not to borrow, because ipsum."),
            ("afternoon", "Supervisor", "did", "Fed weekly aggregate report",
             f"[PLACEHOLDER day {day}] The supervisor read a pretend weekly report and said nothing."),
        ]:
            log.append({"line": len(log) + 1, "text": f"PLACEHOLDER LOG d{day} {half} {actor.lower().replace(' ', '_')} value=0.00"})
            entries.append({"half": half, "actor": actor, "kind": kind, "route": route, "text": text,
                            "log_line": len(log), "support_check": None})
        days.append({"day": day, "entries": entries})
    return {"scenario": str(rng.choice(v["scenarios"])), "policy": str(rng.choice(v["policies"])),
            "bank_id": "MOCK-00", "run": 0, "selection": "placeholder (M3.5 replays the median run)",
            "placeholder": True, "days": days, "log": log}


def write(folder, marker=True, seed=SEED):
    """Write one complete mock results folder. marker=False previews the case where M2.4 fails."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    v = vocabulary()
    runs_per_cell = yaml.safe_load((ROOT / "config" / "run_plan.yaml").read_text())["runs_per_cell"]
    marker_at = round(float(rng.uniform(0.05, 0.85)), 3)
    meta = {"schema_version": SCHEMA_VERSION, "mock": True,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stamp": stamp(),
            "jev_marker": {"available": marker, "stigma": marker_at if marker else None,
                           "label": "mock marker" if marker else ""},
            "scorecard_scope": "MOCK: pooled over all 35 stigma x supervision cells at contract defaults "
                               "(placeholder wording; M3.2 fixes the real scope)",
            "runs_per_cell": runs_per_cell}
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))
    sc, bands = scorecard(rng, v, runs_per_cell)
    write_csv(folder / "scorecard.csv", sc)
    write_csv(folder / "timing_bands.csv", bands)
    write_csv(folder / "tradeoff.csv", tradeoff(rng, v))
    write_csv(folder / "frontier.csv", frontier(rng, v))
    write_csv(folder / "option_c.csv", option_c(rng, v))
    write_csv(folder / "attribution.csv", attribution(rng, v))
    (folder / "replay.json").write_text(json.dumps([replay(rng, v)], indent=2))   # schema 1.1: a list
    hyps = [{"id": h, "parts": [{"part": p, "result": "pending", "verdict": "pending"} for p in parts]}
            for h, parts in HYPOTHESIS_PARTS.items()]
    (folder / "hypotheses.json").write_text(json.dumps(hyps, indent=2))
    # Last, so the marker and no-marker folders share every other number.
    write_csv(folder / "reversal.csv", reversal(rng, v, marker_at) if marker else [])
    # Schema 1.1 files (Clarification 31), from their own random stream so nothing above changes.
    extra = np.random.default_rng(seed + 1)
    write_csv(folder / "implied_s.csv", [{"policy": p, "marker": fmt(extra.uniform(0.05, 0.85)), "spread_low": "",
                                          "spread_high": "", "r": "", "implied_s": "", "note": "mock"} for p in v["policies"]])
    for name in ("sensitivity.csv", "sensitivity_labels.csv", "scorecard_extra.csv"):
        write_csv(folder / name, [])
    return folder


def main(out=OUT):
    out = Path(out)
    write(out / "results", marker=True)
    write(out / "results_no_marker", marker=False)
    print(f"Wrote mock results (NOT RESULTS) to {out}/results and {out}/results_no_marker")


if __name__ == "__main__":
    main()
