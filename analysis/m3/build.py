"""Turn the raw M3 outcomes into the results files the report reads (session v0.1-C; Clarification 31).

    python -m analysis.m3.build [RAW_FOLDER] [RESULTS_FOLDER]

Every number follows a rule fixed in Clarification 31 before any stress run of B, B', C, C' or E: paired
differences per (bank, run) unit with 90% normal intervals, contract 4's lead / tie / trade-off rule (cost never
sets a label), reversal distances from A's provisional Jev reference, and the hypotheses scored as registered.
replay.json is written by analysis/m3/replay.py; this module leaves an existing one in place.
"""

import csv
import datetime
import json
import sys
from itertools import product
from pathlib import Path

import numpy as np

from analysis.m3 import hypotheses
from analysis.m3.raw import OUTCOME, Raw, false_comfort
from analysis.m3.run import configure, extra_combinations, load_settings, switch_name
from analysis.m3.stats import FEATURES, effective_setup, implied_s, label, paired_interval, reversal, shapley_weights
from analysis.mock_results import stamp as config_stamp
from analysis.results_schema import COMPARISONS, OPTION_C_POLICIES, RELEASED, UPTAKE, comparison_sides
from engine.banks import generate_banks
from engine.costs import load_cost_settings, policy_costs
from engine.policies import draw_policy_randoms, load_policies, policy_setup
from engine.run_plan import load_run_plan

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "outputs" / "raw"
OUT = ROOT / "outputs" / "results"
FROZEN = ROOT / "signals" / "frozen"
SCHEMA = "1.1"


def fmt(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    return f"{float(x):.6g}"


def write_csv(path, cols, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)


class Builder:
    def __init__(self, raw_folder):
        self.cfg, self.plan = load_settings(), load_run_plan()
        self.raw = Raw(raw_folder)
        self.z = self.cfg["z_90"]
        g = self.plan["cells"]
        self.main = list(product(g["main"]["stigma"], g["main"]["supervision"]))
        self.mid = list(product(g["mid_range"]["stigma"], g["mid_range"]["supervision"]))
        self.types = list(dict.fromkeys(self.raw.banks["archetype"]))
        self.bank_type = self.raw.banks["archetype"]
        self._costs = {}
        self._labels = {}

    # ----- costs: static, one value per bank (Clarification 13; Clarification 31 B2 intervals over banks) -----
    def costs(self, setting="-", point="-"):
        key = (setting, point)
        if key not in self._costs:
            conf = configure(setting, point, self.cfg)
            banks = generate_banks()
            if conf["no_lcr_type"]:
                banks["lcr_calibration"] = np.where(banks["archetype"] == conf["no_lcr_type"], np.nan,
                                                    banks["lcr_calibration"])
            rnd = draw_policy_randoms(conf["pol"]["seed"], len(banks["bank_id"]))
            setups = {p: policy_setup(banks, p, conf["pol"], rnd, conf["fs"], conf["lcr"], conf["info"])
                      for p in self.plan["policies"]}
            cc = load_cost_settings()
            self._costs[key] = {p: policy_costs(s, setups["A"], cc, conf["pol"])["annual_cost_m"] for p, s in setups.items()}
        return self._costs[key]

    def bank_interval(self, values, bank_type):
        v = np.asarray(values)[self.bank_type == bank_type]
        return paired_interval(v, self.z)

    # ----- paired comparisons -----
    def diff(self, scen, x, y, cells, outcome, rows, sx=("-", "-"), sy=("-", "-")):
        """X minus Y per row, averaged over cells; (mean, lo, hi). sx / sy: (setting, point) for each side."""
        fn = OUTCOME[outcome] if isinstance(outcome, str) else outcome
        dx = self.raw.per_row(scen, x, cells, fn, *sx, rows=rows)
        dy = self.raw.per_row(scen, y, cells, fn, *sy, rows=rows)
        d = dx - dy
        d = d[~np.isnan(d)]
        return paired_interval(d, self.z) if len(d) else (np.nan, np.nan, np.nan)

    def cell_label(self, scen, x, y, cell, rows, sx=("-", "-"), sy=("-", "-")):
        key = (scen, x, y, cell, tuple(rows[:1]), len(rows), sx, sy)
        if key not in self._labels:
            s = self.diff(scen, x, y, [cell], "survival_rate", rows, sx, sy)
            f = self.diff(scen, x, y, [cell], "liquidity_shortfall_bn", rows, sx, sy)
            self._labels[key] = (label(s, f), s, f)
        return self._labels[key]

    # ----- files -----
    def scorecard(self):
        rows, bands, extra = [], [], []
        fc = false_comfort(self.cfg)
        cost = self.costs()
        n_cells = len(self.main)
        for p, s, t in product(self.plan["policies"], self.plan["scenarios"], self.types):
            r = self.raw.type_rows(t)
            n = len(r) * n_cells

            def row(metric, fn, static=False):
                v = self.raw.per_row(s, p, self.main, fn, rows=r)
                value = np.nanmean(v) if np.any(~np.isnan(v)) else np.nan
                if p == "A":
                    d = (None, None, None)
                elif static:                                   # constant across runs: interval over banks
                    va = self.raw.per_row(s, "A", self.main, fn, rows=r)
                    per_bank = [np.nanmean((v - va)[self.raw.bank_of_row[r] == b]) for b in np.unique(self.raw.bank_of_row[r])]
                    d = paired_interval(per_bank, self.z)
                else:
                    d = self.diff(s, p, "A", self.main, fn, r)
                runs = self.raw.count(s, p, self.main, fn, rows=r)
                return [p, s, t, metric, fmt(value), *(fmt(x) for x in d), runs]

            rows.append(row("survival_rate", OUTCOME["survival_rate"]))
            rows.append(row("liquidity_shortfall_bn", OUTCOME["liquidity_shortfall_bn"]))
            rows.append(row("support_peak_bn", OUTCOME["support_bn"]))
            rows.append(row("support_total_bn", OUTCOME["support_bn"]))
            cb = cost[p][self.bank_type == t]
            cd = (None, None, None) if p == "A" else self.bank_interval(cost[p], t)
            rows.append([p, s, t, "annual_cost_m", fmt(cb.mean()), *(fmt(x) for x in cd), n])
            if p in ("C", "C_prime"):
                rows.append(row("buffer_gap_pp", OUTCOME["buffer_gap_pp"], static=True))
            rows.append(row("effective_stigma", OUTCOME["effective_stigma"], static=True))
            rows.append(row("routine_borrowing_per_quarter", OUTCOME["routine_borrowing_per_quarter"], static=True))
            rows.append(row("hesitation_gap_days", OUTCOME["hesitation_gap_days"]))
            rows.append(row("false_comfort", fc))
            if s == "S2":
                rows.append(row("needless_borrowing_bn", OUTCOME["support_bn"]))
            grace = sum(int(self.raw.batch(s, p, x, u)["grace"][np.isin(self.raw.rows_of(s, p, x, u), r)].sum())
                        for x, u in self.main)
            rows.append([p, s, t, "timing_only_upper_bound", grace, "", "", "", n])
            # Timing bands (Clarification 18 item 2).
            counts = np.zeros(5, int)
            for x, u in self.main:
                b = self.raw.batch(s, p, x, u)
                counts += np.bincount(b["band"][np.isin(b["row"], r)], minlength=5)
            fails = counts[1:].sum()
            for i, name in enumerate(["pure timing", "partly covered", "not covered", "equity below zero"], 1):
                bands.append([p, s, t, name, int(counts[i]), fmt(counts[i] / fails) if fails else ""])
            fh = row("fhlb_peak_bn", OUTCOME["fhlb_peak_bn"])
            extra.append(fh[:8])
        return rows, bands, extra

    def tradeoff(self):
        out = []
        cost = self.costs()
        for c, s, t in product(COMPARISONS, self.plan["scenarios"], self.types):
            x, y = comparison_sides(c)
            r = self.raw.type_rows(t)
            cd = float(np.mean((cost[x] - cost[y])[self.bank_type == t]))
            for cell in self.main:
                lab, sv, sh = self.cell_label(s, x, y, cell, r)
                out.append([c, s, t, str(float(cell[0])), cell[1], lab, fmt(cd), *(fmt(v) for v in sv), *(fmt(v) for v in sh)])
        return out

    def marker(self):
        rows = list(csv.DictReader(l for l in (FROZEN / "markers.csv").read_text().splitlines() if not l.startswith("#")))
        return {r["policy"]: r for r in rows}

    def reversal(self, tradeoff_rows):
        m = self.cfg["marker"]
        at = round(float(self.marker()[m["policy"]]["marker"]), m["decimals"])
        grid = [float(x) for x in self.plan["cells"]["main"]["stigma"]]
        lab = {(r[0], r[1], r[2], float(r[3]), r[4]): r[5] for r in tradeoff_rows}
        out = []
        for c, s, t, u in product(COMPARISONS, self.plan["scenarios"], self.types, self.plan["cells"]["main"]["supervision"]):
            here, dd, dl, ud, ul = reversal([lab[(c, s, t, g, u)] for g in grid], grid, at)
            out.append([c, s, t, u, here, fmt(dd), dl or "", fmt(ud), ul or ""])
        return out, at

    def implied_s(self):
        mk, info = self.marker(), configure("-", "-", self.cfg)["info"]
        rb = info["routine_borrowing"]
        rate = lambda p: (self.cfg["marker"]["c_default_uptake"] * rb["c_usage_draws_per_quarter"] if p == "C"
                          else rb["rate_by_policy"][p])
        a = mk["A"]
        out = []
        for p in self.plan["policies"]:
            key = {"B_prime": "B′", "C_prime": "C′"}.get(p, p)
            row = mk[key]
            s = None if p == "A" else implied_s(float(row["marker"]), float(a["marker"]), rate(p), rate("A"))
            note = ("reference (A)" if p == "A" else "undefined: same r as A" if s is None else "exploratory")
            out.append([p, row["marker"], row["spread_low"], row["spread_high"], fmt(rate(p)), fmt(s), note])
        return out

    def frontier(self):
        out, cost = [], self.costs()
        for p, s, t in product(self.plan["policies"], self.plan["scenarios"], self.types):
            r = self.raw.type_rows(t)
            sv = paired_interval(self.raw.per_row(s, p, self.main, OUTCOME["survival_rate"], rows=r), self.z)
            sh = paired_interval(self.raw.per_row(s, p, self.main, OUTCOME["liquidity_shortfall_bn"], rows=r), self.z)
            out.append([p, s, t, *(fmt(v) for v in self.bank_interval(cost[p], t)), *(fmt(v) for v in sv), *(fmt(v) for v in sh)])
        return out

    def option_c(self):
        """C and C' on the one-at-a-time cross (Clarification 14), on the 9 mid-range cells, survival vs A."""
        d = self.plan["cells"]
        out = []
        for p, s, t, up, rel in product(OPTION_C_POLICIES, self.plan["scenarios"], self.types, UPTAKE, RELEASED):
            on_cross = up == 0.75 or rel == 1.0
            if not on_cross:
                out.append([p, s, t, str(up), str(rel), "false", "", "", "", ""])
                continue
            setting = ("-", "-") if (up, rel) == (0.75, 1.0) else (("c_uptake", str(up)) if rel == 1.0 else ("c_hqla_released", str(rel)))
            r = self.raw.type_rows(t)
            sv = self.diff(s, p, "A", self.mid, "survival_rate", r, sx=setting)
            cm = float(np.mean(self.costs(*setting)[p][self.bank_type == t]))
            out.append([p, s, t, str(up), str(rel), "true", *(fmt(v) for v in sv), fmt(cm)])
        return out

    def attribution(self):
        """Shapley contributions of the four switches (Clarification 31 B6), 9 mid-range cells."""
        pol = configure("-", "-", self.cfg)["pol"]
        names = {effective_setup({f for f, v in pol["policies"][n]["switches"].items() if v}): n for n in ("A", "B", "C", "E")}
        for setup in extra_combinations(load_policies()):   # the plain table: configure() has added the SW_ names
            names[setup] = switch_name(setup)
        weights = shapley_weights()
        out = []
        for s, t, o in product(self.plan["scenarios"], self.types, ["survival_rate", "liquidity_shortfall_bn"]):
            r = self.raw.type_rows(t)
            v = {}
            for coalition in {k for w in weights.values() for k in w}:
                v[coalition] = self.raw.per_row(s, names[effective_setup(coalition)], self.mid, OUTCOME[o], rows=r)
            for f in FEATURES:
                contrib = sum(w * v[k] for k, w in weights[f].items())
                out.append([f, s, t, o, *(fmt(x) for x in paired_interval(contrib, self.z))])
        return out

    def sensitivity(self):
        """Each sensitivity point against the default, for the policies it reruns (Clarification 31 B5)."""
        rows, labels = [], []
        for sens in self.plan["sensitivities"]:
            pols = self.plan["policies"] if sens["policies"] == "all" else sens["policies"]
            cells = self.main if sens["cells"] == "main" else self.mid
            types = [sens["banks"]] if sens.get("banks") else self.types
            for pt, s in product(sens["points"], sens.get("scenarios", self.plan["scenarios"])):
                key = (sens["name"], str(pt))
                for p, t in product(pols, types):
                    r = self.raw.type_rows(t)
                    sv = paired_interval(self.raw.per_row(s, p, cells, OUTCOME["survival_rate"], *key, rows=r), self.z)
                    sh = paired_interval(self.raw.per_row(s, p, cells, OUTCOME["liquidity_shortfall_bn"], *key, rows=r), self.z)
                    dsv = self.diff(s, p, p, cells, "survival_rate", r, sx=key)
                    dsh = self.diff(s, p, p, cells, "liquidity_shortfall_bn", r, sx=key)
                    rows.append([sens["name"], str(pt), p, s, t, fmt(sv[0]), *(fmt(v) for v in dsv), fmt(sh[0]),
                                 *(fmt(v) for v in dsh)])
                for c, t in product(COMPARISONS, types):
                    x, y = comparison_sides(c)
                    r = self.raw.type_rows(t)
                    sx = key if x in pols else ("-", "-")
                    sy = key if y in pols else ("-", "-")
                    changed = sum(self.cell_label(s, x, y, cell, r, sx, sy)[0] != self.cell_label(s, x, y, cell, r)[0]
                                  for cell in self.mid)
                    labels.append([sens["name"], str(pt), c, s, t, len(self.mid), changed])
        return rows, labels

    def meta(self, marker_at):
        st = config_stamp()
        man = json.loads((FROZEN / "MANIFEST.json").read_text())
        st["jev_estimate_version"] = f"v0.1-signals (frozen at {man['git_commit_at_freeze'][:7]}; markers provisional)"
        st["jev_model"] = man["model_version"]
        release = __import__("yaml").safe_load((ROOT / "config" / "release.yaml").read_text())
        return {"schema_version": SCHEMA, "mock": False, "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "stamp": st, "release": {"name": release["release"], "banner": release["banner"]},
                "jev_marker": {"available": True, "stigma": marker_at, "label": self.cfg["marker"]["label"]},
                "scorecard_scope": (f"contract defaults; all {len(self.main)} stigma x supervision cells pooled; the 10 banks "
                                    f"of each type x {self.raw.runs} paired runs (Clarification 31 B4)"),
                "runs_per_cell": self.raw.runs, "run": self.raw.info}


def build(raw_folder=RAW, out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    b = Builder(raw_folder)
    sc, bands, extra = b.scorecard()
    write_csv(out / "scorecard.csv", ["policy", "scenario", "bank_type", "metric", "value", "diff_vs_a", "diff_lo",
                                      "diff_hi", "n_runs"], sc)
    write_csv(out / "timing_bands.csv", ["policy", "scenario", "bank_type", "band", "failures", "share"], bands)
    write_csv(out / "scorecard_extra.csv", ["policy", "scenario", "bank_type", "metric", "value", "diff_vs_a", "diff_lo",
                                            "diff_hi"], extra)
    to = b.tradeoff()
    write_csv(out / "tradeoff.csv", ["comparison", "scenario", "bank_type", "stigma", "supervision", "label", "cost_diff_m",
                                     "survival_diff", "survival_lo", "survival_hi", "shortfall_diff_bn", "shortfall_lo",
                                     "shortfall_hi"], to)
    rv, at = b.reversal(to)
    write_csv(out / "reversal.csv", ["comparison", "scenario", "bank_type", "supervision", "label_at_marker",
                                     "down_distance", "down_label", "up_distance", "up_label"], rv)
    write_csv(out / "implied_s.csv", ["policy", "marker", "spread_low", "spread_high", "r", "implied_s", "note"], b.implied_s())
    write_csv(out / "frontier.csv", ["policy", "scenario", "bank_type", "cost_m", "cost_lo", "cost_hi", "survival",
                                     "survival_lo", "survival_hi", "shortfall_bn", "shortfall_lo", "shortfall_hi"], b.frontier())
    write_csv(out / "option_c.csv", ["policy", "scenario", "bank_type", "uptake", "hqla_released", "run", "survival_diff",
                                     "survival_lo", "survival_hi", "cost_m"], b.option_c())
    att = b.attribution()
    write_csv(out / "attribution.csv", ["feature", "scenario", "bank_type", "outcome", "contribution", "lo", "hi"], att)
    srows, slabels = b.sensitivity()
    write_csv(out / "sensitivity.csv", ["sensitivity", "point", "policy", "scenario", "bank_type", "survival",
                                        "survival_diff", "survival_lo", "survival_hi", "shortfall_bn", "shortfall_diff",
                                        "shortfall_lo", "shortfall_hi"], srows)
    write_csv(out / "sensitivity_labels.csv", ["sensitivity", "point", "comparison", "scenario", "bank_type", "cells",
                                               "cells_changed"], slabels)
    hy, detail = hypotheses.score(b, att)
    (out / "hypotheses.json").write_text(json.dumps(hy, indent=1, ensure_ascii=False) + "\n")
    (out / "hypotheses_detail.json").write_text(json.dumps(detail, indent=1, ensure_ascii=False) + "\n")
    (out / "meta.json").write_text(json.dumps(b.meta(at), indent=1, ensure_ascii=False) + "\n")
    if not (out / "replay.json").exists():
        (out / "replay.json").write_text("[]\n")
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    print(f"wrote {build(*(Path(x) for x in a))}")
