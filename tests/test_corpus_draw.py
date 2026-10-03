"""Checks on Clarification 22's gold-set mechanics (session M2.2): draw feasibility, exclusion flags,
two instruction versions in the review file, and preformatted transcripts.

Mechanics only, on made-up numbers and text. Nothing here draws the gold set (that is M2.3) or
says anything about which policy or passage is better.
"""

import csv

import signals.corpus.build_corpus as build
import signals.corpus.review as review
from signals.corpus.build_corpus import excerpt_sha256, flag_gold_set, passage_id
from signals.corpus.draw_feasibility import feasibility
from signals.corpus.passages import load_settings

SETTINGS = load_settings()
STRATA = list(SETTINGS["strata"])
TYPES = ["news", "analyst_note", "official_statement", "speech_testimony", "filing"]


def test_ample_balanced_supply_can_be_filled():
    pool = {(s, t): 40 for s in STRATA for t in TYPES}
    f = feasibility(pool, STRATA, 75, 0.25)
    assert f["can_fill"] and f["fillable"] == 300 and not f["relaxed_periods"]


def test_one_type_cannot_fill_beyond_its_overall_quarter():
    pool = {(s, "filing"): 500 for s in STRATA}                  # filings only
    f = feasibility(pool, STRATA, 75, 0.25)
    assert f["fillable"] == 75 and not f["can_fill"]             # 25% of 300
    assert set(f["relaxed_periods"]) == set(STRATA)


def test_a_period_short_of_types_is_relaxed_but_overall_cap_still_holds():
    pool = {(s, t): 40 for s in STRATA for t in TYPES}
    pool.update({("S-C", t): 0 for t in TYPES})
    pool[("S-C", "filing")] = 200                                 # 2020-21: filings only
    f = feasibility(pool, STRATA, 75, 0.25)
    assert "S-C" in f["relaxed_periods"]
    assert f["per_period"]["S-C"] <= 75 and f["fillable"] <= 300


def _row(text, doubtful=""):
    r = {"url": "https://example.org/x", "passage": text, "pub_date": "2020-03-20", "doubtful": doubtful}
    r["id"] = passage_id(r)
    return r


def test_gold_set_flags(tmp_path, monkeypatch):
    seen_text = ("Banks borrowed record amounts from the discount window this week as deposits fled regional "
                 "lenders, according to weekly figures released by the Federal Reserve on Thursday afternoon.")
    near_copy = seen_text.replace("Thursday afternoon", "Thursday")
    other = "Several lenders turned to the Bank of England's special liquidity scheme to swap mortgage bonds for bills."
    excl = tmp_path / "excl.csv"
    excl.write_text(f"excerpt_sha256,reason\n{excerpt_sha256(seen_text)},owner_check_sheet\n")
    private = tmp_path / "seen.csv"
    with open(private, "w", newline="") as f:
        csv.writer(f).writerows([["excerpt_sha256", "reason", "passage"], ["x", "trial_examples_round1", seen_text]])
    monkeypatch.setattr(build, "GOLD_EXCLUSIONS_PATH", excl)
    monkeypatch.setattr(build, "SEEN_PRIVATE_PATH", private)
    rows = [_row(seen_text), _row(near_copy), _row(other, doubtful="Y"), _row(other + " It said so.")]
    flag_gold_set(rows, SETTINGS)
    assert [r["gold_set_eligible"] for r in rows] == ["N", "N", "N", "Y"]
    assert rows[0]["gold_set_exclusion"] == "owner_check_sheet"
    assert rows[1]["gold_set_exclusion"].endswith("(near-copy)")
    assert rows[2]["gold_set_exclusion"] == "doubtful_review"


def test_latest_instruction_version_counts_and_old_decisions_stay(tmp_path, monkeypatch):
    path = tmp_path / "reviews.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=review.REVIEW_FIELDS)
        w.writeheader()
        w.writerow({"id": "P1", "excerpt_sha256": "h", "decision": "drop", "reason": "policy_design", "doubtful": "",
                    "reviewer": "m", "instruction": "v1", "date": "2026-10-03"})
        w.writerow({"id": "P1", "excerpt_sha256": "h", "decision": "keep", "reason": "perception", "doubtful": "",
                    "reviewer": "m", "instruction": "v2", "date": "2026-10-03"})
    monkeypatch.setattr(review, "REVIEWS_PATH", path)
    assert review.reviews()["P1"]["decision"] == "keep"
    assert review.reviews("v1")["P1"]["decision"] == "drop"
    assert len(open(path).read().strip().splitlines()) == 3      # both decisions kept on record


def test_preformatted_transcripts_are_rejoined_into_whole_sentences(monkeypatch):
    import signals.corpus.extract as extract
    page = ("<html><body><pre>\nSenator Smith. Did any of these banks borrow\nfrom the discount window before "
            "they\nfailed?\n\nChair Powell. Yes, Senator, they did.\n</pre></body></html>")
    monkeypatch.setattr(extract, "get", lambda url, settings: page)
    text, _ = extract.page_text({"url": "https://www.govinfo.gov/x", "pub_date": "2023-05-18"}, SETTINGS)
    assert "Did any of these banks borrow from the discount window before they failed?" in text
