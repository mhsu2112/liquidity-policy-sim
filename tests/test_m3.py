"""Mechanics of the v0.1 comparison run (session v0.1-C; Clarification 31).

These check arithmetic, plumbing, pairing and reproducibility only. No test here says which policy wins, loses,
or performs better or worse than another (CLAUDE.md rule 1).
"""

import copy
import json
import math
from itertools import product

import numpy as np
import pytest

from analysis.m3 import hypotheses, memo, replay
from analysis.m3.build import build as build_results
from analysis.m3.run import configure, extra_combinations, load_settings, run as run_grid, run_batch, tasks
from analysis.m3.stats import (FEATURES, combination_rate, effective_setup, implied_s, label, paired_interval, reversal,
                               shapley_weights)
from analysis.report import build as report
from analysis.results_schema import validate
from engine.policies import load_policies
from engine.run_plan import count_runs, load_run_plan, totals


# ---------- arithmetic, by hand ----------

def test_paired_interval_by_hand():
    d = [1.0, 2.0, 3.0, 4.0]                       # mean 2.5, sd 1.29099, se 0.645497
    m, lo, hi = paired_interval(d, 1.6449)
    assert m == 2.5
    assert lo == pytest.approx(2.5 - 1.6449 * 0.6454972, abs=1e-6)
    assert hi == pytest.approx(2.5 + 1.6449 * 0.6454972, abs=1e-6)
    assert paired_interval([0.0, 0.0, 0.0], 1.6449) == (0.0, 0.0, 0.0)
    assert paired_interval([0.7], 1.6449) == (0.7, 0.7, 0.7)


@pytest.mark.parametrize("surv,short,expected", [
    ((0.10, 0.02, 0.18), (-1.0, -2.0, 0.5), "x_leads"),     # better survival, significant; shortfall no worse
    ((0.00, 0.00, 0.00), (-1.0, -2.0, -0.1), "x_leads"),    # survival equal, shortfall significantly lower
    ((-0.10, -0.18, -0.02), (0.5, -0.5, 1.5), "y_leads"),
    ((0.10, 0.02, 0.18), (1.0, 0.2, 1.8), "trade_off"),     # X better on survival, Y better on shortfall
    ((-0.10, -0.18, -0.02), (-1.0, -1.8, -0.2), "trade_off"),
    ((0.01, -0.02, 0.04), (-0.1, -0.5, 0.3), "tie"),        # nothing excludes zero
    ((0.10, 0.02, 0.18), (0.2, -0.3, 0.7), "tie"),          # significantly better survival but point shortfall worse
    ((0.00, 0.00, 0.00), (0.00, 0.00, 0.00), "tie"),
])
def test_lead_rule_on_made_up_intervals(surv, short, expected):
    assert label(surv, short) == expected


def test_reversal_from_078():
    grid = [0.0, 0.10, 0.20, 0.35, 0.50, 0.70, 0.90]
    labs = ["tie", "tie", "tie", "x_leads", "x_leads", "x_leads", "trade_off"]
    here, dd, dl, ud, ul = reversal(labs, grid, 0.78)
    assert here == "x_leads"                       # nearest grid point to 0.78 is 0.70
    assert dd == pytest.approx(0.78 - 0.20) and dl == "tie"
    assert ud == pytest.approx(0.90 - 0.78) and ul == "trade_off"
    assert reversal(["tie"] * 7, grid, 0.78) == ("tie", None, None, None, None)


def test_implied_s_arithmetic():
    s = implied_s(0.6515, 0.7787, 1.0, 0.1)
    assert s == pytest.approx(-math.log(0.6515 / 0.7787) / 0.9)
    assert implied_s(0.7787, 0.7787, 0.1, 0.1) is None          # C': same r as A, undefined
    assert implied_s(0.7787, 0.7787, 1.875, 0.1) == 0.0


def test_shapley_weights_add_up():
    w = shapley_weights()
    rng = np.random.default_rng(0)
    coalitions = [frozenset(f for f, b in zip(FEATURES, bits) if b) for bits in product([0, 1], repeat=4)]
    v = {c: rng.normal() for c in coalitions}
    for f in FEATURES:
        assert sum(w[f].values()) == pytest.approx(0.0)
    total = sum(sum(wt * v[c] for c, wt in w[f].items()) for f in FEATURES)
    assert total == pytest.approx(v[frozenset(FEATURES)] - v[frozenset()])   # efficiency
    additive = {c: sum({"prepositioning_mandate": 1, "testing_mandate": 2, "five_day_ratio": 3, "lcr_credit": 4}[f]
                       for f in c) for c in coalitions}
    for f, k in zip(FEATURES, (1, 2, 3, 4)):
        assert sum(wt * additive[c] for c, wt in w[f].items()) == pytest.approx(k)


def test_switch_combinations_and_rates():
    pol = load_policies()
    extra = extra_combinations(pol)
    assert len(extra) == 8                                        # Clarification 14 item 5
    assert effective_setup({"five_day_ratio"}) == (True, False, True, False)
    info = configure("-", "-", load_settings())["info"]
    assert combination_rate((True, True, False, True), info, 0.75) == pytest.approx(1.0 + 1.875)
    assert combination_rate((True, False, False, False), info, 0.75) == pytest.approx(0.1)


# ---------- the run plan, as tasks ----------

def test_tasks_match_the_run_plan_count():
    plan, pol = load_run_plan(), load_policies()
    ts = tasks(plan, pol)
    rows_per = {"all": 40, "svb_like": 10}
    sens = {s["name"]: s for s in plan["sensitivities"]}
    episodes = sum(rows_per[sens[t[1]].get("banks", "all")] if t[0] == "sens" else 40 for t in ts) * plan["runs_per_cell"]
    assert episodes == totals(count_runs(plan, pol))["total"] == 25_832_000
    assert len(ts) == len(set(ts))


def _flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flat(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


@pytest.mark.parametrize("setting,point,changed", [
    ("leak_probability", "0.5", {"info.routes.leak.probability"}),
    ("leak_lag_days", "5", {"info.routes.leak.lag_days"}),
    ("c_ceiling", "0.15", {"pol.lcr_credit.ceiling"}),
    ("c_uptake", "0.5", {"pol.lcr_credit.uptake"}),
    ("c_hqla_released", "0.0", {"pol.lcr_credit.release_share"}),
    ("c_stress_trigger", "fires_day_1", {"pol.lcr_credit.stress_trigger_fires"}),
    ("depositor_coordination", "x1.5", {"behavior.coordination_strength.value"}),
    ("b_full_run", "uninsured_runoff_100pct", {"pol.five_day_ratio.runoff_uninsured"}),
    ("fhlb_line_share", "0.08", {"fs.fhlb.line_share_of_assets"}),
    ("starting_collateral_split", "fed_minus_20pp", {"fs.collateral_placement.fed_prepositioned",
                                                     "fs.collateral_placement.unpledged"}),
    ("routine_borrowing_strength_s", "0.7", {"s"}),
    ("distress_hit_size", "0.4", {"hit"}),
    ("svb_like_no_lcr", "no_lcr", {"no_lcr_type", "only_type"}),
])
def test_each_override_changes_only_its_setting(setting, point, changed):
    cfg = load_settings()
    base, mine = _flat(configure("-", "-", cfg)), _flat(configure(setting, point, cfg))
    diff = {k for k in base if base[k] != mine[k]}
    # c_uptake also moves the SW_ combination rates that use LCR credit (Clarification 31 B6).
    diff = {k for k in diff if not k.startswith("info.routine_borrowing.rate_by_policy.SW_")}
    assert diff == changed


def test_margin_and_repo_overrides():
    cfg = load_settings()
    base = configure("-", "-", cfg)
    up = configure("collateral_margins_pp", "5", cfg)["fs"]["discount_window"]["margins"]
    for k, v in base["fs"]["discount_window"]["margins"].items():
        assert up[k] == pytest.approx(min(1.0, v + 0.05))
    half = configure("repo_line_multiple", "x0.5", cfg)["fs"]["repo"]["same_day_line_share_of_assets"]
    for k, v in base["fs"]["repo"]["same_day_line_share_of_assets"].items():
        assert half[k] == pytest.approx(v * 0.5)
    split = configure("starting_collateral_split", "fhlb_plus_20pp", cfg)["fs"]["collateral_placement"]
    assert sum(split.values()) == pytest.approx(1.0)


# ---------- pairing and reproducibility ----------

def test_batches_are_reproducible_and_paired():
    cfg = load_settings()
    a1 = run_batch(("main", "-", "-", "S1", "A", 0.35, "neutral"), 2, cfg)
    a2 = run_batch(("main", "-", "-", "S1", "A", 0.35, "neutral"), 2, cfg)
    b = run_batch(("main", "-", "-", "S1", "B", 0.35, "neutral"), 2, cfg)
    for k in a1:
        np.testing.assert_array_equal(a1[k], a2[k])
    np.testing.assert_array_equal(a1["row"], b["row"])            # same rows, same order, every policy
    svb = run_batch(("sens", "svb_like_no_lcr", "no_lcr", "S1", "A", 0.35, "neutral"), 2, cfg)
    np.testing.assert_array_equal(svb["failed"], a1["failed"][svb["row"]])   # A reads no LCR: a subset reruns identically


def test_replayed_row_matches_its_batch():
    cfg = load_settings()
    b = run_batch(("main", "-", "-", "S2", "C", 0.35, "neutral"), 2, cfg)
    row = 37
    st, setup, recs, _ = replay.replay_row(row, 2, "S2", "C", cfg)
    assert bool(st["end_state"][0] == 1) == bool(b["failed"][row])
    assert int(st["end_step"][0] // 2 + 1) == int(b["end_day"][row])


# ---------- hypotheses scoring on synthetic labels ----------

class _Stub:
    """A stand-in builder whose labels are made up, to check the counting rules alone."""
    def __init__(self, labels):
        self.labels = labels
        self.mid = [(x, u) for x in (0.2, 0.35, 0.5) for u in ("penalizes", "neutral", "encourages")]
        self.raw = type("R", (), {"type_rows": staticmethod(lambda t: np.arange(3))})()

    def cell_label(self, scen, x, y, cell, rows, sx=("-", "-"), sy=("-", "-")):
        return self.labels[self.mid.index(cell)], None, None


@pytest.mark.parametrize("n_x,verdict", [(5, "not supported"), (4, "supported")])
def test_h1_counts_against_its_registered_threshold(n_x, verdict):
    labs = ["x_leads"] * n_x + ["tie"] * (9 - n_x)
    parts, counts = hypotheses.h1(_Stub(labs))
    assert counts["x_leads"] == n_x and parts[0]["verdict"] == verdict


def test_h1_counts_either_side():
    parts, _ = hypotheses.h1(_Stub(["y_leads"] * 5 + ["trade_off"] * 4))
    assert parts[0]["verdict"] == "not supported"


# ---------- end to end on a tiny grid ----------

@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    base = tmp_path_factory.mktemp("m3")
    run_grid(runs=1, out=base / "raw", workers=4, log=lambda m: None)
    build_results(base / "raw", base / "results")
    fake = lambda state, qs: {"model": "fake (test)", "answers": {k: {"value": 0.9} for k in qs}}
    replay.CACHE = base / "cache.csv"
    replay.run(base / "raw", base / "results", ask=fake)
    memo.write(base / "results")
    report.build(base / "results", base / "report")
    return base


def test_tiny_results_pass_schema_1_1(tiny):
    assert validate(tiny / "results") == []
    reps = json.loads((tiny / "results" / "replay.json").read_text())
    assert {(r["scenario"], r["policy"]) for r in reps} == {(s, p) for s in ("S1", "S2") for p in ("A", "B", "C", "C_prime", "E")}


def test_every_page_carries_banner_and_disclosure(tiny):
    banner = load_release_banner()
    pages = list((tiny / "report").glob("*.html"))
    assert len(pages) == len(report.load_layout()["pages"])
    for p in pages:
        html = p.read_text()
        assert html.count(banner) >= 2, p.name
        assert "publicly advocated a version of Option B" in html, p.name
        assert "MOCK" not in html, p.name
    from PIL import Image
    for png in (tiny / "report" / "img").glob("*.png"):
        if not png.stem.endswith("_bw"):
            assert Image.open(png).info.get("Description") == banner, png.name


def test_memo_quotes_hypotheses_unedited(tiny):
    text = (tiny / "results" / "hypotheses_memo.md").read_text()
    assert load_release_banner() in text and "publicly advocated a version of Option B" in text
    for hid, h in report.parse_hypotheses().items():
        assert f"## {hid}. {h['title']}" in text
        for k, v in h["bullets"]:
            assert f"- **{k}:** {v}" in text
    hy = json.loads((tiny / "results" / "hypotheses.json").read_text())
    assert all(p["verdict"] in ("supported", "not supported", "untestable", "reported") for h in hy for p in h["parts"])


def test_rebuild_is_identical(tiny, tmp_path):
    build_results(tiny / "raw", tmp_path / "again")
    for f in (tiny / "results").glob("*.csv"):
        assert (tmp_path / "again" / f.name).read_bytes() == f.read_bytes(), f.name


def load_release_banner():
    import yaml
    from analysis.m3.run import ROOT
    return yaml.safe_load((ROOT / "config" / "release.yaml").read_text())["banner"]
