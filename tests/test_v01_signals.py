"""Checks on M2.5 markers, M2.6 corpus scores and the frozen outputs (release v0.1; Clarification 30).

Mechanics only, on made-up numbers where possible: the reading formula, both flags, the
equal-weight policy marker, B′ = B and C′ = C without L3/P5, filing weights = 1/rate, and that the
frozen files match their manifest and carry the banner. Nothing here says any policy's marker is
better or worse.
"""

import csv
import hashlib
import json

import pytest

import signals.markers as mk
from signals.corpus_scores import weight
from signals.jev_client import ROOT
from signals.templates.load import load_templates

BANNER = "v0.1 proof of concept. Jev reference not validated against human readers. Not a v1 result."


def test_reading_and_pair_flag():
    assert mk.reading(0.8, 0.4) == pytest.approx(0.7)              # mean of 0.8 and 1 - 0.4
    assert mk.pair_flag(0.2, 0.2, 0.25) and not mk.pair_flag(0.7, 0.3, 0.25)


def test_sibling_flag_compares_each_wording_with_its_siblings_mean():
    rows = [{"template": "T", "vantage": "v", "reading": x} for x in (0.50, 0.52, 0.48, 0.80)]
    mk.sibling_flags(rows, 0.15)
    assert [r["sibling_flag"] for r in rows] == [False, False, False, True]


def test_marker_is_the_equal_weight_mean_of_template_means():
    rows = ([{"template": "T1", "reading": x} for x in (0.2, 0.4)]          # template mean 0.3
            + [{"template": "T2", "reading": x} for x in (0.8, 0.8, 0.8, 0.8)])   # template mean 0.8
    m, lo, hi, n = mk.markers(rows, {"X": ["T1", "T2"]})["X"]
    assert m == pytest.approx(0.55) and (lo, hi, n) == (0.2, 0.8, 6)


def test_policy_membership_follows_clarification_30():
    members = mk.policy_templates(mk.config(), load_templates())
    assert members["B′"] == members["B"]
    assert members["C′"] == [t for t in members["C"] if t not in ("L3", "P5")]
    draw = set(mk.config()["draw_templates"])
    assert all(set(v) <= draw for v in members.values())                   # non-draw templates never in a marker


def test_filing_weight_is_the_inverse_of_the_sampling_rate():
    assert weight({"source_type": "filing", "filing_sampling_rate": "0.25"}) == pytest.approx(4.0)
    assert weight({"source_type": "news", "filing_sampling_rate": ""}) == 1.0


def test_frozen_files_match_the_manifest_and_carry_the_banner():
    frozen = ROOT / "signals" / "frozen"
    if not (frozen / "MANIFEST.json").exists():
        pytest.skip("not frozen yet")
    manifest = json.loads((frozen / "MANIFEST.json").read_text())
    assert manifest["model_version"] == "jev-1.13.0" and manifest["banner"] == BANNER
    for name, digest in manifest["files"].items():
        data = (frozen / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name
        text = data.decode()
        assert BANNER in text, name
        assert "validation" not in text.replace(BANNER, "").lower().replace("not human validation", ""), name
