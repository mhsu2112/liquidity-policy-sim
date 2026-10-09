"""Mechanics of the v0.1 diagnostics (session v0.1-D). No test says which policy wins (CLAUDE.md rule 1)."""

import numpy as np
import pytest

from analysis.m3 import diagnostics as D
from analysis.m3.build import Builder
from analysis.m3.run import run as run_grid
from analysis.m3.stats import label


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    base = tmp_path_factory.mktemp("diag")
    run_grid(runs=1, out=base / "raw", workers=4, log=lambda m: None)
    D.rerun_owed(base / "raw", base / "raw_owed", workers=4, log=lambda m: None)   # stops if any saved field differs
    D.run(base / "raw", base / "raw_owed", base / "out", rerun=False)
    return base


def test_rerun_reproduces_every_saved_field_and_adds_owed(tiny):
    saved = np.load(tiny / "raw" / "main__-__-__S1.npz")
    again = np.load(tiny / "raw_owed" / "main__-__-__S1.npz")
    shared = [k for k in again.files if not k.endswith("|owed")]
    assert set(shared) == set(saved.files)
    for k in shared:
        np.testing.assert_array_equal(saved[k], again[k])
    owed = [again[k] for k in again.files if k.endswith("|owed")]
    unc = [again[k.replace("|owed", "|uncovered")] for k in again.files if k.endswith("|owed")]
    assert all((o >= u - 1e-6).all() for o, u in zip(owed, unc))   # what no source covers is part of what is owed


def test_grace_survival_is_never_below_strict(tiny):
    b = Builder(tiny / "raw")
    for x, u in b.main:
        bt = b.raw.batch("S1", "A", x, u)
        assert (D.GRACE(bt) >= D.STRICT(bt)).all()


def test_diagnostic_labels_use_the_scored_rule(tiny):
    b = Builder(tiny / "raw")
    r = b.raw.type_rows("svb_like")
    cell = b.main[0]
    assert D.cell_label(b, "S1", "B", "A", cell, r, D.STRICT, D.UNCOVERED) == b.cell_label("S1", "B", "A", cell, r)[0]
    assert D.cell_label(b, "S1", "B", "A", cell, r, D.GRACE, D.UNCOVERED) in ("x_leads", "y_leads", "tie", "trade_off")
    assert D.label is label


def test_page_carries_banner_disclosure_and_labels(tiny):
    html = (tiny / "out" / "diagnostics.html").read_text()
    assert html.count("v0.1 proof of concept. Jev reference not validated against human readers.") >= 2
    assert "publicly advocated a version of Option B" in html
    assert "sensitivity, upper bound" in html and "alternative definition, not the scored one" in html


def test_report_shows_diagnostics_as_sensitivities_and_new_limits(tmp_path):
    """Amendment 9: the diagnostics appear on the Sensitivities page, labelled as sensitivities; three new limits."""
    import shutil
    from analysis import mock_results
    from analysis.report import build as report
    mock_results.write(tmp_path / "results")
    shutil.copytree(D.OUT, tmp_path / "diagnostics")
    report.build(tmp_path / "results", tmp_path / "report")
    html = (tmp_path / "report" / "sensitivity.html").read_text()
    for _, heading in report.DIAGNOSTICS:
        assert heading.split(" — ")[0] in html
    assert "Diagnostic sensitivities" in html and "upper bound" in html and "alternative definition, not the scored one" in html
    assert (tmp_path / "report" / "diagnostics" / "1_grace_survival.csv").exists()
    limits = (tmp_path / "report" / "limits.html").read_text()
    for title in ("The results depend on the strict failure rule", "Model banks never hesitate to borrow",
                  "rest on the routine-borrowing assumption"):
        assert title in limits


def test_grace_causes_add_up_and_match_saved_runs(tiny):
    """The cause analysis checks every re-run pair against the saved run (it stops otherwise); categories add up."""
    from analysis.m3 import grace_causes
    ps = grace_causes.pairs(tiny / "raw")
    rows = dict(grace_causes.counts(ps))
    assert rows["1 non-timing failure (all, by construction)"] == len(ps)
    assert sum(v for k, v in rows.items() if not k.startswith("1 ")) == len(ps)
