"""Freeze every v0.1 Jev output into signals/frozen/ (M2.6; release v0.1, Amendment 7).

signals/frozen/ is the only link between Jev and the simulation (CLAUDE.md): the simulation reads
these files and never calls Jev. Each CSV starts with the v0.1 banner as a comment line; the
manifest records the model version, date, git commit, every file's SHA-256, the configs used and
the gold-check figures labelled "model-to-model agreement".

Run: python -m signals.freeze   (or: make freeze)
"""

import datetime
import hashlib
import json
import subprocess
from pathlib import Path

import yaml

from signals.gold_set.check_report import compute

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "signals" / "frozen"
SOURCES = {   # frozen name -> working file
    "markers.csv": ROOT / "signals" / "markers.csv",
    "markers_readings.csv": ROOT / "signals" / "markers_readings.csv",
    "corpus_scores.csv": ROOT / "signals" / "corpus_scores.csv",
    "historical_range.csv": ROOT / "signals" / "historical_range.csv",
    "gold_set_answers.csv": ROOT / "signals" / "gold_set" / "jev_answers.csv",
}
CONFIGS = ["config/jev.yaml", "config/markers.yaml", "config/templates_fill.yaml", "config/release.yaml",
           "signals/templates/paraphrases.csv", "signals/gold_set/labels_AI.csv"]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _jsonable(stats):
    lo, hi = stats["interval"]
    return {"passages": stats["n"], "alpha_ordinal": round(stats["alpha"], 4), "interval_90": [round(lo, 4), round(hi, 4)],
            "exact_agreement": round(stats["exact"], 4), "confusion_rows_ai_cols_jev": stats["confusion"].tolist()}


def gold_check():
    r = compute()
    return {"label": "model-to-model agreement: Jev jev-1.13.0 vs AI labels (GPT-6.1 Sol (high)); not human validation",
            "all": _jsonable(r["all"]), "ai_not_unsure": _jsonable(r["not_unsure"]),
            "by_source_type": {k: _jsonable(v) for k, v in r["by_type"].items()},
            "by_period": {k: _jsonable(v) for k, v in r["by_period"].items()},
            "owner_practice_illustrative_only_n15": _jsonable(r["practice"]),
            "excluded_not_applicable": r["excluded_na"], "reference_threshold_not_a_gate": 0.60}


def run():
    with open(ROOT / "config" / "release.yaml") as f:
        banner = yaml.safe_load(f)["banner"]
    with open(ROOT / "config" / "jev.yaml") as f:
        model = yaml.safe_load(f)["model"]
    FROZEN.mkdir(exist_ok=True)
    for name, src in SOURCES.items():
        (FROZEN / name).write_text(f"# {banner}\n" + src.read_text())
    (FROZEN / "gold_check.json").write_text(json.dumps({"banner": banner, **gold_check()}, indent=1, ensure_ascii=False) + "\n")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    manifest = {
        "banner": banner, "release": "v0.1", "amendments": ["Amendment 7", "Clarification 27", "Clarification 30"],
        "model_version": model, "frozen_on": datetime.date.today().isoformat(), "git_commit_at_freeze": commit,
        "markers_status": "provisional", "gold_check_label": "model-to-model agreement",
        "guide_commit": "a0f08dbd2f1a55b861874ad6d855b08166cee4ee",
        "files": {p.name: sha256(p) for p in sorted(FROZEN.iterdir()) if p.suffix in (".csv", ".json", ".md")
                  and p.name != "MANIFEST.json"},
        "inputs": {c: sha256(ROOT / c) for c in CONFIGS},
    }
    (FROZEN / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    print(f"froze {len(manifest['files'])} files into signals/frozen/ (model {model}, commit {commit[:7]})")
    return manifest


if __name__ == "__main__":
    run()
