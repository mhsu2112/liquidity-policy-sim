"""Checks for the M3 report shells on mock data (session M3.0; Clarification 28).

Mechanics only: the mock never touches the engine or outputs/, every page and image carries the mock
banner, the schema validator accepts the mock files and rejects broken ones, and the layout matches the
fingerprint recorded in docs/amendments.md. Nothing here looks at which policy any number favours.
"""

import ast
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from analysis import mock_results
from analysis.report import build
from analysis.results_schema import COMPARISONS, LABELS, validate
from engine.frozen import frozen_fingerprint

ROOT = Path(__file__).resolve().parent.parent
MOCK_SOURCES = [ROOT / "analysis" / "mock_results.py", ROOT / "analysis" / "results_schema.py"]
SIMULATION_PACKAGES = {"engine", "agents", "validation", "signals", "cost"}
BANNER = "MOCK DATA — LAYOUT ONLY — NOT RESULTS"


@pytest.fixture(scope="module")
def mock(tmp_path_factory):
    """One mock results folder (with marker), one without, and the report built from them."""
    base = tmp_path_factory.mktemp("mock")
    mock_results.write(base / "results", marker=True)
    mock_results.write(base / "results_no_marker", marker=False)
    pages = build.build(base / "results", base / "report", base / "results_no_marker")
    return base, pages


# ---------- the mock is cut off from the simulation ----------

def test_mock_source_imports_no_simulation_code():
    """Neither the mock script nor the schema module it uses imports engine, agents, validation, signals or cost."""
    for src in MOCK_SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for n in names:
                assert n.split(".")[0] not in SIMULATION_PACKAGES, f"{src.name} imports {n}"


def test_mock_run_loads_no_simulation_module_and_reads_nothing_in_outputs(tmp_path):
    """Run the mock in a fresh Python with an audit hook: record every file opened and every module loaded."""
    script = f"""
import json, sys
opened = []
sys.addaudithook(lambda ev, args: opened.append(str(args[0])) if ev == "open" and isinstance(args[0], str) else None)
from analysis import mock_results
mock_results.main(out={str(tmp_path)!r})
mods = sorted({{m.split(".")[0] for m in sys.modules}})
print(json.dumps({{"opened": opened, "modules": mods}}))
"""
    res = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, check=True)
    report = json.loads(res.stdout.strip().splitlines()[-1])
    assert not SIMULATION_PACKAGES & set(report["modules"])
    outputs = str((ROOT / "outputs").resolve())
    reads_in_outputs = [p for p in report["opened"] if str(Path(p).resolve()).startswith(outputs)]
    assert reads_in_outputs == [], f"mock opened files in outputs/: {reads_in_outputs[:3]}"
    assert (tmp_path / "results" / "meta.json").exists()


def test_mock_writes_only_under_outputs_mock():
    assert mock_results.OUT == ROOT / "outputs" / "mock"


def test_mock_fingerprint_recipe_matches_engine():
    """The mock repeats engine/frozen.py's recipe so it needn't import it; the two must agree."""
    assert mock_results.stamp()["params_fingerprint"] == frozen_fingerprint()


def test_mock_is_reproducible(tmp_path):
    a, b = mock_results.write(tmp_path / "a"), mock_results.write(tmp_path / "b")
    for name in ("scorecard.csv", "tradeoff.csv", "reversal.csv", "frontier.csv", "attribution.csv"):
        assert (a / name).read_text() == (b / name).read_text()


def test_mock_labels_use_every_label_for_every_comparison(mock):
    """Labels are drawn at random from all four, so each comparison shows each label somewhere."""
    base, _ = mock
    rows = list(csv.DictReader(open(base / "results" / "tradeoff.csv")))
    for comp in COMPARISONS:
        assert {r["label"] for r in rows if r["comparison"] == comp} == set(LABELS)


def test_mock_hypothesis_verdicts_all_pending(mock):
    base, _ = mock
    for h in json.loads((base / "results" / "hypotheses.json").read_text()):
        assert all(p["verdict"] == "pending" and p["result"] == "pending" for p in h["parts"])


# ---------- the schema ----------

def test_validator_accepts_mock_files(mock):
    base, _ = mock
    assert validate(base / "results") == []
    assert validate(base / "results_no_marker") == []


@pytest.mark.parametrize("breakage", ["drop_file", "bad_label", "bad_interval", "bad_verdict", "missing_row"])
def test_validator_rejects_broken_files(mock, tmp_path, breakage):
    base, _ = mock
    bad = tmp_path / "bad"
    shutil.copytree(base / "results", bad)
    if breakage == "drop_file":
        (bad / "frontier.csv").unlink()
    elif breakage in ("bad_label", "bad_interval", "missing_row"):
        rows = list(csv.DictReader(open(bad / "tradeoff.csv")))
        if breakage == "bad_label":
            rows[0]["label"] = "winner"
        elif breakage == "bad_interval":
            rows[0]["survival_lo"] = str(float(rows[0]["survival_diff"]) + 1)
        else:
            rows = rows[1:]
        with open(bad / "tradeoff.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    else:
        hy = json.loads((bad / "hypotheses.json").read_text())
        hy[0]["parts"][0]["verdict"] = "reported"          # only H2 may be "reported" (Clarification 31 B7 allows untestable for any)
        (bad / "hypotheses.json").write_text(json.dumps(hy))
    assert validate(bad) != []


def test_report_refuses_invalid_results(mock, tmp_path):
    base, _ = mock
    bad = tmp_path / "bad"
    shutil.copytree(base / "results", bad)
    (bad / "scorecard.csv").write_text("nonsense\n")
    with pytest.raises(ValueError):
        build.build(bad, tmp_path / "out")


# ---------- banner, disclosure, pages ----------

def test_every_page_carries_banner_and_disclosure(mock):
    base, pages = mock
    html_files = sorted((base / "report").rglob("*.html"))
    assert len(html_files) == len(pages) == len(build.load_layout()["pages"]) + 2
    for f in html_files:
        text = f.read_text()
        assert text.count(BANNER) >= 2, f"{f.name}: banner and watermark"      # banner + watermark
        assert 'class="watermark"' in text and 'class="banner"' in text
        assert "publicly advocated a version of Option B" in text, f"{f.name}: disclosure (rule 7)"


def test_every_image_carries_banner(mock):
    """Each chart records the banner in its metadata (it is drawn on the image by the same call)."""
    base, _ = mock
    images = [p for p in (base / "report").rglob("*.png") if not p.stem.endswith("_bw")]
    assert images
    for p in images:
        assert Image.open(p).info.get("Description") == BANNER, p.name


def test_real_results_have_no_banner(mock, tmp_path):
    """The same build on files marked mock = false shows no banner: the only change from mock to real."""
    base, _ = mock
    real = tmp_path / "real"
    shutil.copytree(base / "results", real)
    meta = json.loads((real / "meta.json").read_text())
    meta["mock"] = False
    (real / "meta.json").write_text(json.dumps(meta))
    build.build(real, tmp_path / "out")
    for f in (tmp_path / "out").glob("*.html"):
        assert BANNER not in f.read_text()
        assert "publicly advocated a version of Option B" in f.read_text()


def test_front_page_links_every_page_and_shows_stamp(mock):
    base, _ = mock
    text = (base / "report" / "index.html").read_text()
    for p in build.load_layout()["pages"][1:]:
        assert f'href="{p["file"]}"' in text
    meta = json.loads((base / "results" / "meta.json").read_text())
    for v in meta["stamp"].values():
        assert v in text


def test_hypotheses_page_quotes_the_registered_tests(mock):
    base, _ = mock
    text = (base / "report" / "hypotheses.html").read_text()
    parsed = build.parse_hypotheses()
    assert sorted(parsed) == [f"H{i}" for i in range(1, 9)]
    for h in parsed.values():
        assert any(k.startswith(("Shown wrong if", "Pre-committed report")) for k, _ in h["bullets"])
    assert "either B or C leads in 5 or more of the 9 mid-range cells" in text


def test_scorecard_grace_column_label(mock):
    base, _ = mock
    assert "Upper bound on timing-only failures (reported, not scored)" in (base / "report" / "scorecard.html").read_text()


def test_no_marker_version_has_no_marker(mock):
    base, _ = mock
    assert "mock marker" not in (base / "report" / "no-marker" / "tradeoff.html").read_text()
    assert "mock marker" in (base / "report" / "tradeoff.html").read_text()


# ---------- the layout is fixed (Clarification 28) ----------

def test_layout_matches_recorded_fingerprint():
    recorded = build.recorded_layout_fingerprints()
    assert recorded, "docs/amendments.md records no layout fingerprint"
    assert recorded[-1] == build.layout_fingerprint(), (
        "analysis/report/layout.yaml changed: record the reason and the new layout fingerprint in docs/amendments.md")


def test_layout_names_only_schema_metrics():
    from analysis.results_schema import METRICS
    assert [c["metric"] for c in build.load_layout()["scorecard_columns"]] == [
        m for m in ["survival_rate", "liquidity_shortfall_bn", "support_peak_bn", "support_total_bn", "annual_cost_m",
                    "buffer_gap_pp", "effective_stigma", "routine_borrowing_per_quarter", "hesitation_gap_days",
                    "false_comfort", "needless_borrowing_bn", "timing_only_upper_bound"]]
    assert set(METRICS) == {c["metric"] for c in build.load_layout()["scorecard_columns"]}
