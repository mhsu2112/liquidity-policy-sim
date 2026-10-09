"""Checks on the M2.5 paraphrases (implementation plan M2.5; Clarification 30, Part B).

Mechanics only: a paraphrase changes wording, never facts, so each one must keep exactly the
original's placeholders and literal numbers; each template has 3-5 paraphrases; every placeholder
has an illustrative fill value. Whether the meaning is unchanged is the owner's check, not a test.
"""

import csv
import re
from collections import Counter

import yaml

from signals.jev_client import ROOT
from signals.templates.load import load_templates

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _numbers(text):
    """Literal numbers outside placeholders (e.g. 50 in '$50 million', 100 in '100%')."""
    return Counter(re.findall(r"\d+(?:\.\d+)?", PLACEHOLDER.sub("", text)))


def _paraphrases():
    with open(ROOT / "signals/templates/paraphrases.csv", newline="") as f:
        return list(csv.DictReader(f))


def test_each_paraphrase_keeps_the_original_placeholders_and_numbers():
    originals = {t["id"]: t for t in load_templates()}
    for p in _paraphrases():
        o = originals[p["template"]]["text"]
        assert Counter(PLACEHOLDER.findall(p["text"])) == Counter(PLACEHOLDER.findall(o)), p["paraphrase_id"]
        assert _numbers(p["text"]) == _numbers(o), p["paraphrase_id"]
        assert p["policy"] == " ".join(originals[p["template"]]["policies"])


def test_three_to_five_paraphrases_per_template_with_unique_ids():
    rows = _paraphrases()
    per = Counter(p["template"] for p in rows)
    assert set(per) == {t["id"] for t in load_templates()} and all(3 <= n <= 5 for n in per.values())
    assert len({p["paraphrase_id"] for p in rows}) == len(rows)


def test_every_placeholder_has_a_fill_value():
    with open(ROOT / "config/templates_fill.yaml") as f:
        fill = yaml.safe_load(f)
    used = {name for t in load_templates() for name in PLACEHOLDER.findall(t["text"])}
    assert used <= set(fill)


def test_loader_reads_the_frozen_file_without_changing_template_text():
    raw = (ROOT / "signals/templates/disclosure_templates.yaml").read_text()
    for t in load_templates():
        assert " ".join(t["text"].split()[:6]) in " ".join(raw.split())
