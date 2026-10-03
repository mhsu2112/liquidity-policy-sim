"""Candidate pages from the Federal Reserve Board: press releases, speeches, testimony (session M2.2).

The Board publishes complete lists of these as small public files (the same files its
website's search pages use). We keep every item dated 2007-2024; extract.py then reads
each page and keeps only passages that are in scope. A press release about discount
window lending data is tagged as a data release rather than an official statement.

Run: python -m signals.corpus.collect_fed
"""

import re
from datetime import datetime

from signals.corpus.candidates import write_candidates
from signals.corpus.fetch import get_json
from signals.corpus.passages import load_settings

BASE = "https://www.federalreserve.gov"
LISTS = {   # listing file -> source type
    "/json/ne-press.json": "official_statement",
    "/json/ne-speeches.json": "speech_testimony",
    "/json/ne-testimony.json": "speech_testimony",
}
# Titles of releases that publish borrowing data (e.g. the 2010 and 2011 disclosures, quarterly transaction data).
_LENDING = r"(discount window|term auction facility|emergency lending|lending facilities|credit and liquidity (programs|facilities)|liquidity facilities)"
_DATA = r"(data|transaction|disclos|detailed information|report on|results)"
DATA_TITLE = re.compile(f"{_LENDING}.*{_DATA}|{_DATA}.*{_LENDING}", re.IGNORECASE)


def collect(settings=None):
    settings = settings or load_settings()
    start, end = settings["date_range"]["start"], settings["date_range"]["end"]
    rows = []
    for path, source_type in LISTS.items():
        for item in get_json(BASE + path, settings):
            if "d" not in item or "l" not in item:
                continue   # the last entry is just an "updated on" note
            date = datetime.strptime(item["d"].split()[0], "%m/%d/%Y").strftime("%Y-%m-%d")
            if not start <= date <= end:
                continue
            kind = source_type
            if source_type == "official_statement" and DATA_TITLE.search(item["t"]):
                kind = "data_release"
            rows.append({"url": BASE + item["l"], "source_name": "Federal Reserve Board", "source_type": kind,
                         "pub_date": date, "found_via": f"Fed Board listing {path}: {item['t'][:120]}"})
    return write_candidates("fed_board", rows)


if __name__ == "__main__":
    collect()
