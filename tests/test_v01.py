"""Checks on the v0.1 switch (Amendment 7): AI-label conversion and lock, the gold-set guard, the banner.

Mechanics only, on made-up rows and stubbed git. The guard opens on AI labels only in release v0.1
and only while the locked file is unchanged; under any other release it needs both human locks, as
before. Nothing here judges any label or says any policy is better.
"""

import csv

import pytest
import yaml

import signals.gold_set.ai_labels as ai
import signals.gold_set.labels as labels
import signals.jev_client as jc

ROOT = jc.ROOT
LABELER = "AI:GPT-6.1 Sol (high)"


@pytest.fixture
def small(tmp_path, monkeypatch):
    summary = tmp_path / "summary.csv"
    summary.write_text("round,stratum,source_type,count\nmain,S-B,news,3\npractice,S-B,news,1\n")
    monkeypatch.setattr(labels, "SUMMARY_PATH", summary)
    monkeypatch.setattr(labels, "LOCKS_PATH", tmp_path / "locks.md")
    monkeypatch.setattr(labels, "HERE", tmp_path / "signals" / "gold_set")
    calls = []
    monkeypatch.setattr(labels, "git", lambda *a: calls.append(a))
    monkeypatch.setattr(labels, "release", lambda: {"release": "v0.1", "ai_labels": {"labeler": LABELER}})
    return tmp_path, calls


ROWS = [{"ID": "G001", "Passage": "t", "Answer": "routine", "Unsure": None, "Note": "plain report"},
        {"ID": "G002", "Passage": "t", "Answer": "Clear Distress", "Unsure": "y", "Note": "forced to turn"},
        {"ID": "G003", "Passage": "t", "Answer": " not  applicable", "Unsure": "", "Note": ""}]


def test_conversion_stores_word_code_and_labeler(small):
    out = ai.convert(ROWS, LABELER)
    assert [(r["ID"], r["Answer"], r["Code"], r["Unsure"]) for r in out] == [
        ("G001", "Routine", "2", ""), ("G002", "Clear Distress", "4", "Y"), ("G003", "Not Applicable", "N", "")]
    assert all(r["Labeler"] == LABELER for r in out)


def test_conversion_refuses_blank_invalid_and_wrong_ids(small):
    with pytest.raises(labels.Refused, match="blank or invalid"):
        ai.convert(ROWS[:2] + [{**ROWS[2], "Answer": None}], LABELER)
    with pytest.raises(labels.Refused, match="blank or invalid"):
        ai.convert(ROWS[:2] + [{**ROWS[2], "Answer": "3"}], LABELER)
    with pytest.raises(labels.Refused, match="IDs do not match"):
        ai.convert(ROWS[:2], LABELER)


def _labels_file(tmp_path):
    path = tmp_path / "labels_AI.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ai.FIELDS)
        w.writeheader()
        w.writerows(ai.convert(ROWS, LABELER))
    return path


def test_ai_lock_only_in_release_v01_and_commits_labels_with_locks(small, monkeypatch):
    tmp, calls = small
    path = _labels_file(tmp)
    monkeypatch.setattr(labels, "release", lambda: {"release": "v1", "ai_labels": {"labeler": LABELER}})
    with pytest.raises(labels.Refused, match="only in release v0.1"):
        labels.lock(path)
    monkeypatch.setattr(labels, "release", lambda: {"release": "v0.1", "ai_labels": {"labeler": LABELER}})
    labels.lock(path)
    line = (tmp / "locks.md").read_text().strip().splitlines()[-1]
    assert "| AI | main | labels_AI.csv | 3 |" in line and labels.sha256(path) in line
    assert calls[1][0] == "commit" and str(path) in calls[1] and calls[2] == ("push",)
    with pytest.raises(labels.Refused, match="already locked"):
        labels.lock(path)


def test_guard_opens_on_the_ai_lock_only_in_v01_and_only_while_unchanged(small, monkeypatch):
    tmp, _ = small
    key, private = ROOT / "signals/gold_set/key.csv", ROOT / "signals/corpus/excerpts_private.csv"
    if not (key.exists() and private.exists()):
        pytest.skip("gold-set key and excerpts are not on this computer")
    with open(key, newline="") as f:
        first = next(csv.DictReader(f))["corpus_id"]
    with open(private, newline="") as f:
        gold = next(r["passage"] for r in csv.DictReader(f) if r["id"] == first)
    path = _labels_file(tmp)
    monkeypatch.setattr(labels, "HERE", tmp)              # labels_AI.csv is looked for next to locks.md
    with pytest.raises(jc.JevError, match="Amendment 7"):
        jc.gold_guard(gold)                               # before the AI lock: refused
    labels.lock(path)
    jc.gold_guard(gold)                                   # v0.1 and locked: allowed
    monkeypatch.setattr(labels, "release", lambda: {"release": "v1", "ai_labels": {"labeler": LABELER}})
    with pytest.raises(jc.JevError):
        jc.gold_guard(gold)                               # v1: the AI lock opens nothing
    monkeypatch.setattr(labels, "release", lambda: {"release": "v0.1", "ai_labels": {"labeler": LABELER}})
    path.write_text(path.read_text().replace("Routine", "Reassuring"))
    with pytest.raises(jc.JevError):
        jc.gold_guard(gold)                               # labels changed after the lock: refused


def test_readme_carries_the_banner_word_for_word():
    with open(ROOT / "config" / "release.yaml") as f:
        banner = yaml.safe_load(f)["banner"]
    assert banner == "v0.1 proof of concept. Jev reference not validated against human readers. Not a v1 result."
    readme = (ROOT / "README.md").read_text()
    assert banner in readme and readme.index(banner) < readme.index("## What this is")   # next to the disclosure
