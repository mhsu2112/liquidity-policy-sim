"""Diagnostics from the v0.1 outputs (session v0.1-D). Diagnostic, not scored: nothing here changes a result.

    python -m analysis.m3.diagnostics            (or: make diagnostics)

Reads the saved raw runs (outputs/raw, from `make results`). One approved exception: "largest amount still owed"
was never saved, so the S1 main grid is re-run with the run's own batch function, unchanged, capturing that one extra
field; every field already saved must come out identical first, or the script stops.

Writes outputs/v0.1/diagnostics/: one CSV per item and diagnostics.html (v0.1 banner and disclosure on the page).
    1 grace       survival under the strict rule and counting grace runs as survivors (upper bound); B vs A and
                  C vs A labels on grace survival ("sensitivity, upper bound")
    2 s0          C vs A and B vs C labels with no routine-borrowing effect (s = 0; 9 mid-range cells only)
    3 hesitation  hesitation gap by policy and bank type; share of runs borrowing a day or more late
    4 owed        S1 shortfall as "largest amount still owed" beside the scored uncovered amount ("alternative
                  definition, not the scored one")
"""

import csv
import json
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import yaml

import analysis.m3.run as R
from analysis.m3.build import Builder, fmt
from analysis.m3.stats import label, paired_interval
from analysis.report.build import load_layout
from analysis.report.html import e, page
from engine.policies import load_policies
from engine.run_plan import load_run_plan

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "outputs" / "raw"
RAW_OWED = ROOT / "outputs" / "raw_owed"
OUT = ROOT / "outputs" / "v0.1" / "diagnostics"
META = ROOT / "outputs" / "v0.1" / "results" / "meta.json"
POLICIES = ["A", "B", "E", "C", "C_prime"]
NAMES = {"A": "A", "B": "B", "B_prime": "B′", "C": "C", "C_prime": "C′", "E": "E"}
LABELS = ["x_leads", "y_leads", "tie", "trade_off"]

STRICT = lambda b: 1.0 - b["failed"]
GRACE = lambda b: 1.0 - (b["failed"] & ~b["grace"])          # Amendment 6 count treated as survival: upper bound
UNCOVERED = lambda b: b["uncovered"]
OWED = lambda b: b["owed"]


# ---------- the approved S1 rerun ----------

def _owed_batch(args):
    """The run's own run_batch, unchanged; the engine's outcomes are read once more for peak_owed_bn."""
    task, runs, cfg = args
    seen = {}
    original = R.episode_outcomes

    def grab(st):
        o = original(st)
        seen["owed"] = o["peak_owed_bn"]
        return o
    R.episode_outcomes = grab
    try:
        res = R.run_batch(task, runs, cfg)
    finally:
        R.episode_outcomes = original
    res["owed"] = seen["owed"].astype(np.float32)
    return task, res


def rerun_owed(raw=RAW, out=RAW_OWED, workers=None, log=print):
    cfg, plan = R.load_settings(), load_run_plan()
    info = json.loads((Path(raw) / "run_info.json").read_text())
    todo = [t for t in R.tasks(plan, load_policies()) if t[0] == "main" and t[3] == "S1"]
    with Pool(workers or cfg["workers"]) as pool:
        results = dict(pool.imap_unordered(_owed_batch, [(t, info["runs_per_cell"], cfg) for t in todo]))
    # Proof first: every field already saved must be identical (Session v0.1-D plan, Step 3).
    saved = np.load(Path(raw) / f"{R.group_name(todo[0])}.npz")
    for t, res in results.items():
        for k, v in res.items():
            if k == "owed":
                continue
            if not np.array_equal(saved[f"{t[4]}|{t[5]}|{t[6]}|{k}"], v, equal_nan=v.dtype.kind == "f"):
                raise SystemExit(f"STOP: rerun differs from the saved run in {t} field {k}; nothing written.")
    R.save(results, Path(out))
    (Path(out) / "run_info.json").write_text(json.dumps({**info, "batches": len(todo), "note": "S1 main grid only, "
                                                         "re-run for peak_owed_bn (session v0.1-D)"}, indent=1) + "\n")
    log(f"S1 rerun: {len(todo)} batches; every saved field identical; peak_owed_bn added in {out}")
    return results


# ---------- helpers ----------

def cell_label(b, scen, x, y, cell, rows, surv, short, sx=("-", "-"), sy=("-", "-")):
    return label(b.diff(scen, x, y, [cell], surv, rows, sx, sy), b.diff(scen, x, y, [cell], short, rows, sx, sy))


def counts(labs):
    c = Counter(labs)
    return [c[k] for k in LABELS]


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def level(b, scen, p, cells, fn, rows):
    return float(np.nanmean(b.raw.per_row(scen, p, cells, fn, rows=rows)))


# ---------- the four diagnostics ----------

def grace(b):
    surv, labs = [], []
    for s, t, p in ((s, t, p) for s in ("S1", "S2") for t in b.types for p in POLICIES):
        r = b.raw.type_rows(t)
        surv.append([s, t, p, fmt(level(b, s, p, b.main, STRICT, r)), fmt(level(b, s, p, b.main, GRACE, r))])
    for s, t, (x, y) in ((s, t, c) for s in ("S1", "S2") for t in b.types for c in (("B", "A"), ("C", "A"))):
        r = b.raw.type_rows(t)
        scored = counts([cell_label(b, s, x, y, c, r, STRICT, UNCOVERED) for c in b.main])
        upper = counts([cell_label(b, s, x, y, c, r, GRACE, UNCOVERED) for c in b.main])
        labs.append([f"{x}_vs_{y}", s, t, *scored, *upper])
    return surv, labs


def s0(b):
    out, key = [], ("routine_borrowing_strength_s", "0.0")
    for s, t, (x, y) in ((s, t, c) for s in ("S1", "S2") for t in b.types for c in (("C", "A"), ("B", "C"))):
        r = b.raw.type_rows(t)
        default = counts([cell_label(b, s, x, y, c, r, STRICT, UNCOVERED) for c in b.mid])
        zero = counts([cell_label(b, s, x, y, c, r, STRICT, UNCOVERED, key, key) for c in b.mid])
        out.append([f"{x}_vs_{y}", s, t, *default, *zero])
    return out


def hesitation(b):
    out = []
    for s, t, p in ((s, t, p) for s in ("S1", "S2") for t in b.types for p in POLICIES):
        r = b.raw.type_rows(t)
        vals = np.concatenate([bt["hesitation"][np.isin(bt["row"], r)]
                               for bt in (b.raw.batch(s, p, x, u) for x, u in b.main)])
        vals = vals[~np.isnan(vals)]
        n = len(vals)
        out.append([s, t, p, n, fmt(vals.mean() / 2) if n else "", fmt(np.mean(vals >= 2)) if n else "",
                    fmt(np.mean(vals >= 1)) if n else ""])
    return out


def owed(bo):
    levels, labs = [], []
    for t, p in ((t, p) for t in bo.types for p in ("A", "B", "B_prime", "C", "C_prime", "E")):
        r = bo.raw.type_rows(t)
        row = [t, p]
        for fn in (UNCOVERED, OWED):
            row.append(fmt(level(bo, "S1", p, bo.main, fn, r)))
            row += [""] * 3 if p == "A" else [fmt(v) for v in bo.diff("S1", p, "A", bo.main, fn, r)]
        levels.append(row)
    for t, (x, y) in ((t, c) for t in bo.types for c in (("B", "A"), ("C", "A"), ("B", "C"), ("E", "A"))):
        r = bo.raw.type_rows(t)
        scored = counts([cell_label(bo, "S1", x, y, c, r, STRICT, UNCOVERED) for c in bo.main])
        alt = counts([cell_label(bo, "S1", x, y, c, r, STRICT, OWED) for c in bo.main])
        labs.append([f"{x}_vs_{y}", "S1", t, *scored, *alt])
    return levels, labs


# ---------- the page ----------

def table(header, rows):
    head = "".join(f"<th>{e(h)}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td class=l>{e(NAMES.get(c, c))}</td>" if i < 3 else f"<td>{e(c)}</td>"
                                    for i, c in enumerate(row)) + "</tr>" for row in rows)
    return f'<div class="scroll"><table><tr>{head}</tr>{body}</table></div>'


def run(raw=RAW, raw_owed=RAW_OWED, out=OUT, rerun=True):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if rerun:
        rerun_owed(raw, raw_owed)
    b, bo = Builder(raw), Builder(raw_owed)
    lab_h = [f"{w}: {k}" for w in ("scored", "diagnostic") for k in ("X leads", "Y leads", "tie", "trade-off")]
    files = {}
    gs, gl = grace(b)
    files["1_grace_survival.csv"] = (["scenario", "bank_type", "policy", "survival_strict", "survival_grace_upper_bound"], gs)
    files["1_grace_labels.csv"] = (["comparison", "scenario", "bank_type", *lab_h], gl)
    files["2_s0_labels.csv"] = (["comparison", "scenario", "bank_type", *[h.replace("scored", "s=0.3 default").replace(
        "diagnostic", "s=0") for h in lab_h]], s0(b))
    files["3_hesitation.csv"] = (["scenario", "bank_type", "policy", "runs_with_gap", "mean_gap_days",
                                  "share_a_day_or_more_late", "share_any_delay"], hesitation(b))
    ol, oa = owed(bo)
    files["4_owed_levels_S1.csv"] = (["bank_type", "policy", "uncovered_bn (scored)", "diff_vs_A", "lo", "hi",
                                      "largest_owed_bn (alternative)", "diff_vs_A", "lo", "hi"], ol)
    files["4_owed_labels_S1.csv"] = (["comparison", "scenario", "bank_type", *[h.replace("diagnostic", "owed") for h in lab_h]], oa)
    for name, (h, rows) in files.items():
        write_csv(out / name, h, rows)
    titles = {"1_grace_survival.csv": "1. Grace counterfactual — survival (sensitivity, upper bound)",
              "1_grace_labels.csv": "1. Grace counterfactual — label counts over 35 cells (sensitivity, upper bound)",
              "2_s0_labels.csv": "2. No routine-borrowing effect (s = 0) — label counts over the 9 mid-range cells",
              "3_hesitation.csv": "3. Hesitation gap (pooled over 35 cells; runs that both saw a shortfall and borrowed)",
              "4_owed_levels_S1.csv": "4. S1 shortfall, two definitions (alternative definition, not the scored one)",
              "4_owed_labels_S1.csv": "4. S1 label counts with largest amount still owed (alternative definition, not the scored one)"}
    meta = json.loads(META.read_text())
    body = ['<p class="note">Diagnostic, not scored. Computed from the saved v0.1 runs; no result, parameter or '
            'published page changes. Item 4 uses a re-run of the S1 main grid that reproduced every saved field exactly '
            'and added "largest amount still owed" (Clarification 10 item 8). Item 2 covers only the 9 mid-range cells, '
            'the grid the s sensitivity was run on (Clarification 14). Labels follow the scored rule (Clarification 31 B1).</p>']
    for name, (h, rows) in files.items():
        body.append(f"<h2>{e(titles[name])}</h2><p class=note><a href='{name}'>{name}</a></p>{table(h, rows)}")
    (out / "diagnostics.html").write_text(page(load_layout(), meta, "diagnostics", "v0.1 diagnostics", "\n".join(body)))
    return out, files


if __name__ == "__main__":
    print(f"wrote {run()[0]}")
