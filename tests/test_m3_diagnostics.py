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
