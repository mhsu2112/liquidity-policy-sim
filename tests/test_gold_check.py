"""Checks on the v0.1 model-to-model check (Clarification 30, Part A).

Mechanics only: Krippendorff's ordinal alpha matches a hand-worked example and is 1 for perfect
agreement; the bootstrap repeats with its seed; Jev's Score answer maps to a label and an expected
score; the run refuses to start without the pin and the AI lock; the report carries the banner
and never calls the comparison "validation". Nothing here judges whether Jev or the AI is right.
"""

import math

import numpy as np
import pytest

import signals.gold_set.jev_check as jc
from signals.gold_set.agreement import bootstrap_interval, confusion, ordinal_alpha, summarize
from signals.gold_set.check_report import render

BANNER = "v0.1 proof of concept. Jev reference not validated against human readers. Not a v1 result."


def test_alpha_is_one_for_perfect_agreement():
    assert ordinal_alpha([1, 2, 3, 4, 2], [1, 2, 3, 4, 2]) == pytest.approx(1.0)


def test_alpha_matches_a_hand_worked_example():
    # Passages (1,1), (2,2), (1,2): n1 = n2 = 3, n = 6; o12 = o21 = 1; distance(1,2) = (6 - 3)^2 = 9.
    # alpha = 1 - (6 - 1) x (1x9 + 1x9) / (3x3x9 + 3x3x9) = 1 - 90/162 = 4/9.
    assert ordinal_alpha([1, 2, 1], [1, 2, 2]) == pytest.approx(4 / 9)


def test_alpha_is_undefined_when_every_answer_is_the_same_level():
    assert math.isnan(ordinal_alpha([2, 2, 2], [2, 2, 2]))


def test_bootstrap_repeats_with_its_seed_and_confusion_counts_add_up():
    rng = np.random.default_rng(1)
    a, b = rng.integers(1, 5, 60), rng.integers(1, 5, 60)
    assert bootstrap_interval(a, b, resamples=200) == bootstrap_interval(a, b, resamples=200)
    m = confusion(a, b)
    assert m.sum() == 60 and m[0, 0] == sum(1 for x, y in zip(a, b) if x == 1 and y == 1)


def test_score_answer_maps_to_most_likely_level_and_expected_score():
    result = {"model": "jev-1.13.0", "answers": {"level": {"value": 1.7, "probabilities": {"0": 0.1, "1": 0.2, "2": 0.6, "3": 0.1}}}}
    row = jc.to_row("G001", "main", result)
    assert row["label"] == 3 and row["expected_score"] == pytest.approx(2.7) and row["p3"] == 0.6


def test_run_refuses_without_the_pin_or_the_ai_lock(monkeypatch):
    monkeypatch.setattr(jc, "settings", lambda: {"model": "jev-latest"})
    with pytest.raises(jc.NotReady, match="jev-1.13.0"):
        jc.start_checks()
    monkeypatch.setattr(jc, "settings", lambda: {"model": "jev-1.13.0"})
    monkeypatch.setattr(jc, "ai_lock_holds", lambda: False)
    with pytest.raises(jc.NotReady, match="not locked"):
        jc.start_checks()


def test_guide_question_is_copied_word_for_word_from_the_fixed_commit():
    instructions, levels = jc.guide_question()
    assert instructions.startswith("How does this passage present a bank's borrowing from a central bank")
    assert levels[0] == "The borrowing is presented as prudent, a sign of strength, or a responsible use of the facility."
    assert len(levels) == 4


def test_report_carries_the_banner_and_never_says_validation():
    s = summarize([1, 2, 3, 4, 2, 3], [1, 2, 3, 3, 2, 4], resamples=50)
    r = {"all": s, "not_unsure": s, "by_type": {"news": s}, "by_period": {"S-A": s}, "practice": s, "excluded_na": 1}
    page = render(r, BANNER)
    assert BANNER in page and "model-to-model agreement" in page
    body = page.replace(BANNER, "")
    assert "validation" not in body.lower() and "validated" not in body.lower()
