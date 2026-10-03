"""Candidate documents: pages that may hold an in-scope passage (session M2.2).

Each collector writes one CSV in signals/corpus/candidates/ listing pages to read, with
where they came from. Only links and metadata are stored, never page text. (The Guardian
and NYT services are not listed here: collect_news_api.py cuts their text straight away.)
"""

import csv
from pathlib import Path

CANDIDATE_DIR = Path(__file__).resolve().parent / "candidates"
FIELDS = ["url", "source_name", "source_type", "pub_date", "found_via", "company"]

# The six source types used in the corpus (plan, Step 1).
SOURCE_TYPES = ["news", "analyst_note", "official_statement", "speech_testimony", "filing", "data_release"]


def write_candidates(name, rows):
    """Write one collector's candidate list, one row per page, without duplicate URLs."""
    CANDIDATE_DIR.mkdir(exist_ok=True)
    seen, out = set(), []
    for row in rows:
        assert row["source_type"] in SOURCE_TYPES, row["source_type"]
        if row["url"] not in seen:
            seen.add(row["url"])
            out.append({k: row.get(k, "") for k in FIELDS})
    path = CANDIDATE_DIR / f"{name}.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(out)
    print(f"{path.name}: {len(out)} candidate pages")
    return path


def read_candidates():
    rows = []
    for path in sorted(CANDIDATE_DIR.glob("*.csv")):
        with open(path, newline="") as f:
            rows.extend(csv.DictReader(f))
    return rows
