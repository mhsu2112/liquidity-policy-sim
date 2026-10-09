"""The M3 results schema, as code (session M3.0; Clarification 28).

analysis/results_schema.md describes the files in words; this module holds the same rules so they can be
checked. The report reads only folders that pass validate(). Mock files (M3.0) and real files (M3) must
both pass, which is what lets `make results` swap one for the other with no layout change.

This module reads two settings files and nothing else: config/run_plan.yaml (policies, scenarios and the
stigma x supervision grid, binding under Clarification 14) and config/banks/archetypes.yaml (bank types).
It never imports the engine and never reads outputs/ except the folder it is asked to check.
"""

import csv
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RUN_PLAN = ROOT / "config" / "run_plan.yaml"
ARCHETYPES = ROOT / "config" / "banks" / "archetypes.yaml"
SCHEMA_VERSION = "1.1"   # Clarification 31: replay list, untestable for any hypothesis, four new files


def vocabulary():
    """The names every results file must use, read from the run plan and the bank file."""
    plan = yaml.safe_load(RUN_PLAN.read_text())
    banks = yaml.safe_load(ARCHETYPES.read_text())
    return {
        "policies": plan["policies"],
        "scenarios": plan["scenarios"],
        "stigma": plan["cells"]["main"]["stigma"],
        "supervision": plan["cells"]["main"]["supervision"],
        "bank_types": list(banks["archetypes"]),
        "bank_labels": {k: v["label"] for k, v in banks["archetypes"].items()},
    }


# Scorecard metrics: key -> (which policies, which scenarios, has a paired interval). None = all.
METRICS = {
    "survival_rate": (None, None, True),
    "liquidity_shortfall_bn": (None, None, True),
    "support_peak_bn": (None, None, True),
    "support_total_bn": (None, None, True),
    "annual_cost_m": (None, None, True),
    "buffer_gap_pp": (["C", "C_prime"], None, True),        # PRD: buffer gap, C only (C′ shares C's credit)
    "effective_stigma": (None, None, True),                  # contract 3a
    "routine_borrowing_per_quarter": (None, None, True),     # contract 3a
    "hesitation_gap_days": (None, None, True),
    "false_comfort": (None, None, True),                     # H5
    "needless_borrowing_bn": (None, ["S2"], True),           # PRD: false-alarm scenario only
    "timing_only_upper_bound": (None, None, False),          # Amendment 6: reported, not scored
}
TIMING_BANDS = ["pure timing", "partly covered", "not covered", "equity below zero"]   # Clarification 18
COMPARISONS = ["B_vs_C", "B_vs_E", "C_vs_A", "B_vs_A", "E_vs_A", "C_prime_vs_C", "B_prime_vs_B"]
LABELS = ["x_leads", "y_leads", "tie", "trade_off"]          # contract 4
FEATURES = ["prepositioning_mandate", "testing_mandate", "five_day_ratio", "lcr_credit"]   # contract 2a
OUTCOMES = ["survival_rate", "liquidity_shortfall_bn"]
OPTION_C_POLICIES = ["C", "C_prime"]
UPTAKE = [0.50, 0.75, 1.00]                                  # contract 2d (R1-6)
RELEASED = [0.0, 0.50, 1.00]                                 # contract 2d (R1-5)
OPTION_C_DEFAULTS = {"uptake": 0.75, "hqla_released": 1.00}  # contract 2d defaults
HYPOTHESIS_PARTS = {"H1": ["main"], "H2": ["main"], "H3": ["main", "strong_form"], "H4": ["a", "b", "c"],
                    "H5": ["main"], "H6": ["main"], "H7": ["main"], "H8": ["main"]}
VERDICTS = ["pending", "supported", "not supported", "untestable"]   # Clarification 31 B7: untestable for any
EXTRA_VERDICTS = {"H2": ["reported"]}                        # H2 has no prediction
REPLAY_KINDS = ["saw", "did", "why"]
SUPPORT_CHECKS = [None, "supported", "flagged"]

COLUMNS = {
    "scorecard.csv": ["policy", "scenario", "bank_type", "metric", "value", "diff_vs_a", "diff_lo", "diff_hi",
                      "n_runs"],
    "timing_bands.csv": ["policy", "scenario", "bank_type", "band", "failures", "share"],
    "tradeoff.csv": ["comparison", "scenario", "bank_type", "stigma", "supervision", "label", "cost_diff_m",
                     "survival_diff", "survival_lo", "survival_hi", "shortfall_diff_bn", "shortfall_lo",
                     "shortfall_hi"],
    "reversal.csv": ["comparison", "scenario", "bank_type", "supervision", "label_at_marker", "down_distance",
                     "down_label", "up_distance", "up_label"],
    "frontier.csv": ["policy", "scenario", "bank_type", "cost_m", "cost_lo", "cost_hi", "survival",
                     "survival_lo", "survival_hi", "shortfall_bn", "shortfall_lo", "shortfall_hi"],
    "option_c.csv": ["policy", "scenario", "bank_type", "uptake", "hqla_released", "run", "survival_diff",
                     "survival_lo", "survival_hi", "cost_m"],
    "attribution.csv": ["feature", "scenario", "bank_type", "outcome", "contribution", "lo", "hi"],
    # Schema 1.1 (Clarification 31): the implied-s side table, the sensitivity page, the Home Loan Bank column.
    "implied_s.csv": ["policy", "marker", "spread_low", "spread_high", "r", "implied_s", "note"],
    "sensitivity.csv": ["sensitivity", "point", "policy", "scenario", "bank_type", "survival", "survival_diff",
                        "survival_lo", "survival_hi", "shortfall_bn", "shortfall_diff", "shortfall_lo", "shortfall_hi"],
    "sensitivity_labels.csv": ["sensitivity", "point", "comparison", "scenario", "bank_type", "cells", "cells_changed"],
    "scorecard_extra.csv": ["policy", "scenario", "bank_type", "metric", "value", "diff_vs_a", "diff_lo", "diff_hi"],
}
MAY_BE_BLANK = {"hesitation_gap_days"}   # Clarification 31 B4: defined only for runs that both saw a shortfall and borrowed
STAMP_FIELDS = ["git_commit", "config_hash", "params_fingerprint", "jev_estimate_version", "jev_model"]


def metric_applies(metric, policy, scenario):
    policies, scenarios, _ = METRICS[metric]
    return (policies is None or policy in policies) and (scenarios is None or scenario in scenarios)


def comparison_sides(comparison):
    """'C_prime_vs_C' -> ('C_prime', 'C')."""
    x, y = comparison.split("_vs_")
    return x, y


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def num(text):
    """A CSV field as a number, or None if blank."""
    return None if text in ("", None) else float(text)


def load(folder):
    """Every file in a results folder, parsed. Assumes validate() has passed."""
    folder = Path(folder)
    data = {name: read_csv(folder / name) for name in COLUMNS}
    for name in ("meta.json", "replay.json", "hypotheses.json"):
        data[name] = json.loads((folder / name).read_text())
    return data


# ---------- checks ----------

def _interval(problems, where, est, lo, hi):
    """lo <= est <= hi, all numbers, or all blank."""
    vals = [num(est), num(lo), num(hi)]
    if all(v is None for v in vals):
        return
    if any(v is None for v in vals):
        problems.append(f"{where}: estimate and interval must be all filled or all blank")
    elif not vals[1] <= vals[0] <= vals[2]:
        problems.append(f"{where}: interval [{lo}, {hi}] does not contain {est}")


def _coverage(problems, name, rows, keys, expected):
    seen = [tuple(r[k] for k in keys) for r in rows]
    if len(seen) != len(set(seen)):
        problems.append(f"{name}: duplicate rows")
    missing, extra = set(expected) - set(seen), set(seen) - set(expected)
    if missing:
        problems.append(f"{name}: {len(missing)} expected rows missing, e.g. {sorted(missing)[0]}")
    if extra:
        problems.append(f"{name}: {len(extra)} unexpected rows, e.g. {sorted(extra)[0]}")


def _check_meta(problems, meta):
    if meta.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"meta.json: schema_version must be {SCHEMA_VERSION}")
    if not isinstance(meta.get("mock"), bool):
        problems.append("meta.json: mock must be true or false")
    for f in STAMP_FIELDS:
        if not meta.get("stamp", {}).get(f):
            problems.append(f"meta.json: stamp.{f} missing")
    marker = meta.get("jev_marker", {})
    if not isinstance(marker.get("available"), bool):
        problems.append("meta.json: jev_marker.available must be true or false")
    elif marker["available"] and not (isinstance(marker.get("stigma"), (int, float)) and 0 <= marker["stigma"] <= 1):
        problems.append("meta.json: jev_marker.stigma must be between 0 and 1 when available")
    for f in ("generated_at", "scorecard_scope", "runs_per_cell"):
        if f not in meta:
            problems.append(f"meta.json: {f} missing")


def _check_tables(problems, d, v):
    P, S, B = v["policies"], v["scenarios"], v["bank_types"]
    sc = d["scorecard.csv"]
    _coverage(problems, "scorecard.csv", sc, ["policy", "scenario", "bank_type", "metric"],
              [(p, s, b, m) for p in P for s in S for b in B for m in METRICS if metric_applies(m, p, s)])
    for r in sc:
        where = f"scorecard.csv {r['policy']}/{r['scenario']}/{r['bank_type']}/{r['metric']}"
        blank_ok = r["metric"] in MAY_BE_BLANK
        if num(r["value"]) is None and not blank_ok:
            problems.append(f"{where}: value is blank")
        has_ci = METRICS.get(r["metric"], (0, 0, False))[2] and r["policy"] != "A"
        if has_ci and num(r["diff_vs_a"]) is None and not blank_ok:
            problems.append(f"{where}: paired difference against A is blank")
        if not has_ci and any(r[k] for k in ("diff_vs_a", "diff_lo", "diff_hi")):
            problems.append(f"{where}: should have no paired difference")
        _interval(problems, where, r["diff_vs_a"], r["diff_lo"], r["diff_hi"])

    tb = d["timing_bands.csv"]
    _coverage(problems, "timing_bands.csv", tb, ["policy", "scenario", "bank_type", "band"],
              [(p, s, b, t) for p in P for s in S for b in B for t in TIMING_BANDS])
    for p in P:
        for s in S:
            for b in B:
                shares = [num(r["share"]) for r in tb if (r["policy"], r["scenario"], r["bank_type"]) == (p, s, b)]
                if shares and not all(x is None for x in shares) and abs(sum(x or 0 for x in shares) - 1) > 1e-4:   # allow for rounding in the CSV
                    problems.append(f"timing_bands.csv {p}/{s}/{b}: band shares do not sum to 1")

    to = d["tradeoff.csv"]
    _coverage(problems, "tradeoff.csv", to, ["comparison", "scenario", "bank_type", "stigma", "supervision"],
              [(c, s, b, str(x), u) for c in COMPARISONS for s in S for b in B for x in v["stigma"]
               for u in v["supervision"]])
    for r in to:
        where = f"tradeoff.csv {r['comparison']}/{r['scenario']}/{r['bank_type']}/{r['stigma']}/{r['supervision']}"
        if r["label"] not in LABELS:
            problems.append(f"{where}: label {r['label']!r} not one of {LABELS}")
        if num(r["cost_diff_m"]) is None:
            problems.append(f"{where}: cost difference blank")
        _interval(problems, where + " survival", r["survival_diff"], r["survival_lo"], r["survival_hi"])
        _interval(problems, where + " shortfall", r["shortfall_diff_bn"], r["shortfall_lo"], r["shortfall_hi"])

    rv = d["reversal.csv"]
    if d["meta.json"].get("jev_marker", {}).get("available"):
        _coverage(problems, "reversal.csv", rv, ["comparison", "scenario", "bank_type", "supervision"],
                  [(c, s, b, u) for c in COMPARISONS for s in S for b in B for u in v["supervision"]])
        for r in rv:
            for k in ("label_at_marker", "down_label", "up_label"):
                if r[k] and r[k] not in LABELS:
                    problems.append(f"reversal.csv: {k} {r[k]!r} not a label")
    elif rv:
        problems.append("reversal.csv: must be header only when there is no Jev marker")

    fr = d["frontier.csv"]
    _coverage(problems, "frontier.csv", fr, ["policy", "scenario", "bank_type"], [(p, s, b) for p in P for s in S for b in B])
    for r in fr:
        where = f"frontier.csv {r['policy']}/{r['scenario']}/{r['bank_type']}"
        for k, kl, kh in (("cost_m", "cost_lo", "cost_hi"), ("survival", "survival_lo", "survival_hi"),
                          ("shortfall_bn", "shortfall_lo", "shortfall_hi")):
            if num(r[k]) is None:
                problems.append(f"{where}: {k} blank")
            _interval(problems, f"{where} {k}", r[k], r[kl], r[kh])

    oc = d["option_c.csv"]
    _coverage(problems, "option_c.csv", oc, ["policy", "scenario", "bank_type", "uptake", "hqla_released"],
              [(p, s, b, str(u), str(h)) for p in OPTION_C_POLICIES for s in S for b in B for u in UPTAKE for h in RELEASED])
    for r in oc:
        where = f"option_c.csv {r['policy']}/{r['scenario']}/{r['bank_type']}/{r['uptake']}/{r['hqla_released']}"
        on_cross = num(r["uptake"]) == OPTION_C_DEFAULTS["uptake"] or num(r["hqla_released"]) == OPTION_C_DEFAULTS["hqla_released"]
        if r["run"] not in ("true", "false"):
            problems.append(f"{where}: run must be true or false")
        elif (r["run"] == "true") != on_cross:
            problems.append(f"{where}: run must be true exactly on the one-at-a-time cross (Clarification 14)")
        filled = num(r["survival_diff"]) is not None and num(r["cost_m"]) is not None
        if (r["run"] == "true") != filled:
            problems.append(f"{where}: numbers must be filled exactly where run is true")
        _interval(problems, where, r["survival_diff"], r["survival_lo"], r["survival_hi"])

    at = d["attribution.csv"]
    _coverage(problems, "attribution.csv", at, ["feature", "scenario", "bank_type", "outcome"],
              [(f, s, b, o) for f in FEATURES for s in S for b in B for o in OUTCOMES])
    for r in at:
        _interval(problems, f"attribution.csv {r['feature']}/{r['scenario']}/{r['bank_type']}/{r['outcome']}",
                  r["contribution"], r["lo"], r["hi"])


def _check_replay(problems, replays, v):
    """Schema 1.1: a list of replays (Clarification 31 B8); an empty list means none was written."""
    if not isinstance(replays, list):
        problems.append("replay.json: must be a list of replays (schema 1.1)")
        return
    for rp in replays:
        _check_one_replay(problems, rp, v)


def _check_one_replay(problems, rp, v):
    if rp.get("scenario") not in v["scenarios"] or rp.get("policy") not in v["policies"]:
        problems.append("replay.json: scenario or policy not recognised")
    lines = {e.get("line") for e in rp.get("log", [])}
    if not rp.get("days"):
        problems.append("replay.json: no days")
    for day in rp.get("days", []):
        for e in day.get("entries", []):
            if e.get("kind") not in REPLAY_KINDS:
                problems.append(f"replay.json day {day.get('day')}: kind {e.get('kind')!r} not one of {REPLAY_KINDS}")
            if e.get("log_line") not in lines:
                problems.append(f"replay.json day {day.get('day')}: sentence links to missing log line {e.get('log_line')}")
            if e.get("support_check") not in SUPPORT_CHECKS:
                problems.append(f"replay.json day {day.get('day')}: support_check {e.get('support_check')!r} not allowed")
            if not e.get("text"):
                problems.append(f"replay.json day {day.get('day')}: empty sentence")


def _check_hypotheses(problems, hy):
    got = {h.get("id"): h for h in hy}
    if sorted(got) != sorted(HYPOTHESIS_PARTS):
        problems.append(f"hypotheses.json: ids must be exactly {sorted(HYPOTHESIS_PARTS)}")
    for hid, parts in HYPOTHESIS_PARTS.items():
        h = got.get(hid, {"parts": []})
        if [p.get("part") for p in h["parts"]] != parts:
            problems.append(f"hypotheses.json {hid}: parts must be {parts}")
        for p in h["parts"]:
            allowed = VERDICTS + EXTRA_VERDICTS.get(hid, [])
            if p.get("verdict") not in allowed:
                problems.append(f"hypotheses.json {hid}/{p.get('part')}: verdict {p.get('verdict')!r} not in {allowed}")
            if "result" not in p:
                problems.append(f"hypotheses.json {hid}/{p.get('part')}: result missing")


def validate(folder):
    """Every problem with a results folder, in plain words. An empty list means it is valid."""
    folder = Path(folder)
    problems = []
    needed = list(COLUMNS) + ["meta.json", "replay.json", "hypotheses.json"]
    missing = [n for n in needed if not (folder / n).exists()]
    if missing:
        return [f"missing file: {n}" for n in missing]
    for name, cols in COLUMNS.items():
        with open(folder / name, newline="") as f:
            header = next(csv.reader(f), [])
        if header != cols:
            problems.append(f"{name}: columns must be {cols}, got {header}")
    if problems:
        return problems
    try:
        d = load(folder)
    except (ValueError, json.JSONDecodeError) as err:
        return [f"could not parse: {err}"]
    v = vocabulary()
    for name in COLUMNS:
        for r in d[name]:
            for key, allowed in (("policy", v["policies"]), ("scenario", v["scenarios"]), ("bank_type", v["bank_types"])):
                if key in r and r[key] not in allowed:
                    problems.append(f"{name}: {key} {r[key]!r} not recognised")
    if problems:
        return problems
    _check_meta(problems, d["meta.json"])
    try:
        _check_tables(problems, d, v)
    except ValueError as err:
        problems.append(f"a number could not be read: {err}")
    _check_replay(problems, d["replay.json"], v)
    _check_hypotheses(problems, d["hypotheses.json"])
    return problems


if __name__ == "__main__":
    import sys
    found = validate(sys.argv[1] if len(sys.argv) > 1 else ROOT / "outputs" / "results")
    print("\n".join(found) if found else "valid")
    sys.exit(1 if found else 0)
