"""Candidate pages from US congressional hearing transcripts, 2020-2024 (session M2.2; Clarification 22).

Transcripts are public domain, published by the Government Publishing Office on govinfo.gov.
We use govinfo's search service to find hearings that mention a bank lending facility, keep
those held 2020-2024, and list each transcript's public web page for extract.py to read. The
search service needs a key: a free api.data.gov key in .env (GOVINFO_API_KEY) if present,
otherwise the public demonstration key (a few dozen searches an hour, enough for this list).

Run: python -m signals.corpus.collect_hearings
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from signals.corpus.candidates import write_candidates
from signals.corpus.fetch import env
from signals.corpus.passages import load_settings

SEARCH = "https://api.govinfo.gov/search"
PAGE = "https://www.govinfo.gov/content/pkg/{p}/html/{p}.htm"


def _search(query, key, settings, offset="*"):
    body = json.dumps({"query": query, "pageSize": 100, "offsetMark": offset}).encode()
    req = urllib.request.Request(SEARCH + "?" + urllib.parse.urlencode({"api_key": key}), data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": settings["fetch"]["user_agent"]})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=settings["fetch"]["timeout_seconds"]) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as err:
            if err.code != 429 or attempt == 7:
                raise
            print(f"  govinfo says too many requests; waiting {10 * (attempt + 1)} minutes", flush=True)
            time.sleep(600 * (attempt + 1))   # the demonstration key's hourly allowance resets


def collect(settings=None):
    settings = settings or load_settings()
    h = settings["hearings"]
    key = env("GOVINFO_API_KEY") or "DEMO_KEY"
    rows = []
    for term in h["queries"]:
        offset = "*"
        while offset:
            res = _search(f'collection:CHRG AND "{term}"', key, settings, offset)
            for item in res.get("results", []):
                date = item.get("dateIssued", "")
                if not h["start"] <= date <= h["end"]:
                    continue
                chamber = "Senate" if "Senate" in item.get("governmentAuthor", []) else "House"
                rows.append({"url": PAGE.format(p=item["packageId"]), "source_name": f"U.S. {chamber} hearing",
                             "source_type": "speech_testimony", "pub_date": date,
                             "found_via": f'govinfo search "{term}" (CHRG): {item.get("title", "")[:120]}'})
            nxt = res.get("offsetMark")
            offset = nxt if res.get("results") and nxt != offset else None
            time.sleep(h["pause_seconds"])
    return write_candidates("hearings", rows)


if __name__ == "__main__":
    collect()
