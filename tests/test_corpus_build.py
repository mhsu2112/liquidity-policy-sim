"""Checks on building the corpus files (session M2.2; rules of Clarification 20).

Mechanics only: near-duplicates collapse to the earliest copy; the 25% type cap arithmetic
holds and keeps the largest possible total; at most 2 passages per document; ids are stable.
Made-up rows only; no network. If corpus.csv exists it is also checked against the brief and
Clarification 20: word limit, dates and periods, unique ids, no near-duplicates left, the
caps, no news or analyst wording in the public file, and hashes matching the private excerpts.
Nothing here says which passages or policies are better or worse.
"""

import csv
import math
import random
from collections import Counter

import pytest

from signals.corpus.build_corpus import (CORPUS_PATH, FIELDS, PRIVATE_PATH, excerpt_sha256, keep_per_group,
                                         passage_id, remove_near_duplicates, shingles, type_cap_sizes)
from signals.corpus.candidates import SOURCE_TYPES
from signals.corpus.passages import load_settings, stratum_of

SETTINGS = load_settings()
SHARE = SETTINGS["caps"]["max_type_share_per_stratum"]
STORY = ("Banks borrowed $9.4 billion from the Federal Reserve's discount window in the week to Wednesday, "
         "the most since October, Fed data showed on Thursday, as lenders sought cash amid market turmoil.")


def row(passage, date="2008-03-20", url="https://example.org/a", source_type="news"):
    r = {"url": url, "passage": passage, "pub_date": date, "source_type": source_type, "company": "",
         "stratum": stratum_of(date, SETTINGS)}
    r["id"] = passage_id(r)
    return r


def test_syndicated_copies_collapse_to_the_earliest():
    copies = [row(STORY + " Analysts said the figure was watched closely.", "2008-03-21", "https://b.example/x"),
              row(STORY, "2008-03-20", "https://a.example/x"),
              row(STORY.replace("Thursday", "Thursday afternoon"), "2008-03-22", "https://c.example/x")]
    kept, dropped = remove_near_duplicates(copies, SETTINGS)
    assert [r["url"] for r in kept] == ["https://a.example/x"] and len(dropped) == 2


def test_different_passages_are_kept():
    other = ("The Bank of England said it stood ready to provide liquidity support to the lender, which had "
             "struggled to raise funds in wholesale markets since the summer.")
    kept, _ = remove_near_duplicates([row(STORY), row(other, url="https://b.example/y")], SETTINGS)
    assert len(kept) == 2


@pytest.mark.parametrize("counts", [
    {"filing": 300, "news": 40, "official_statement": 90, "speech_testimony": 60, "analyst_note": 20},
    {"filing": 10, "news": 10, "official_statement": 10, "speech_testimony": 10},
    {"filing": 500, "official_statement": 5, "speech_testimony": 200, "news": 1, "analyst_note": 3, "data_release": 2},
])
def test_type_cap_keeps_no_type_above_a_quarter_and_the_largest_possible_total(counts):
    sizes = type_cap_sizes(counts, SHARE)
    n = sum(sizes.values())
    assert all(0 <= sizes[t] <= counts[t] for t in counts)
    assert all(sizes[t] <= math.floor(SHARE * n) for t in counts)          # no type above 25%
    # no larger total could satisfy the cap
    for bigger in range(n + 1, sum(counts.values()) + 1):
        assert sum(min(c, math.floor(SHARE * bigger)) for c in counts.values()) < bigger


def test_type_cap_with_fewer_than_four_types_keeps_nothing():
    assert sum(type_cap_sizes({"filing": 50, "news": 50, "official_statement": 50}, SHARE).values()) == 0


def test_at_most_two_passages_per_document():
    rows = [row(f"Passage {i}: banks borrowed from the discount window " + "more words here " * 4,
                url=f"https://doc.example/{i % 3}") for i in range(12)]
    kept, dropped = keep_per_group(rows, lambda r: r["url"], SETTINGS["caps"]["max_per_document"], random.Random(1))
    assert max(Counter(r["url"] for r in kept).values()) == 2 and len(kept) + len(dropped) == 12
    again, _ = keep_per_group(rows, lambda r: r["url"], 2, random.Random(1))
    assert again == kept                                                 # same seed, same choice


def test_ids_are_stable_and_depend_on_link_and_text():
    a = row(STORY)
    assert passage_id(a) == passage_id(dict(a))
    assert passage_id(a) != passage_id(row(STORY, url="https://other.example/"))


def test_shingles_ignore_case_and_punctuation():
    assert shingles("Banks BORROWED, from the Fed!", 5) == shingles("banks borrowed from the fed", 5)


# ---------- the built files, if present ----------

def _read(path):
    if not path.exists():
        pytest.skip(f"{path.name} not built yet (run make corpus-build)")
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_corpus_file_meets_the_brief_and_clarification_20():
    rows = _read(CORPUS_PATH)
    assert list(rows[0].keys()) == FIELDS
    assert len({r["id"] for r in rows}) == len(rows)
    public = set(SETTINGS["copyright"]["public_text_types"])
    for r in rows:
        assert all(r[k] for k in ["id", "document_id", "url", "pub_date", "source_name", "source_type", "stratum",
                                  "found_via", "excerpt_sha256"]), r["id"]
        assert r["source_type"] in SOURCE_TYPES
        assert stratum_of(r["pub_date"], SETTINGS) == r["stratum"]
        if r["source_type"] not in public:
            assert r["passage"] == "", f"{r['id']}: news/analyst wording must not be in the public file"
    assert max(Counter(r["document_id"] for r in rows).values()) <= SETTINGS["caps"]["max_per_document"]
    for stratum in SETTINGS["strata"]:
        types = Counter(r["source_type"] for r in rows if r["stratum"] == stratum)
        n = sum(types.values())
        assert all(c <= math.floor(SHARE * n) for c in types.values()), stratum


def test_private_excerpts_match_the_public_hashes_and_limits():
    rows = {r["id"]: r for r in _read(CORPUS_PATH)}
    private = _read(PRIVATE_PATH)
    assert {p["id"] for p in private} == set(rows)
    for p in private:
        assert excerpt_sha256(p["passage"]) == rows[p["id"]]["excerpt_sha256"]
        assert len(p["passage"].split()) <= SETTINGS["passage"]["max_words"]
        if rows[p["id"]]["passage"]:
            assert rows[p["id"]]["passage"] == p["passage"]
    kept, _ = remove_near_duplicates([dict(rows[p["id"]], passage=p["passage"]) for p in private], SETTINGS)
    assert len(kept) == len(private)                                     # no near-duplicates left
