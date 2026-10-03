"""Candidate pages from SEC filings, via EDGAR full-text search (session M2.2).

Most filings repeat the same sentence every quarter ("we have access to the discount
window"), so the plan caps filings at about a quarter of each period and one passage
per company per year (config/corpus.yaml, `filings`). Here we gather, for each year, a
seeded random set of companies and up to two of their filings, preferring 8-K exhibits
(press releases and announcements, which more often describe actual borrowing) over
quarterly and annual reports. build_corpus.py applies the caps.

Run: python -m signals.corpus.collect_edgar
"""

import random
import urllib.parse
from collections import defaultdict

from signals.corpus.candidates import write_candidates
from signals.corpus.fetch import get_json
from signals.corpus.passages import load_settings

SEARCH = "https://efts.sec.gov/LATEST/search-index"
PAGE_SIZE = 100                                      # EDGAR full-text search returns 100 hits a page
FORM_PREFERENCE = {"8-K": 0, "10-Q": 1, "10-K": 2}   # plan: non-boilerplate filings (8-Ks) first


def _hits(query, year, forms, settings, max_pages):
    for page in range(max_pages):
        params = {"q": f'"{query}"', "dateRange": "custom", "startdt": f"{year}-01-01",
                  "enddt": f"{year}-12-31", "forms": forms, "from": page * PAGE_SIZE}
        hits = get_json(SEARCH + "?" + urllib.parse.urlencode(params), settings)["hits"]["hits"]
        yield from hits
        if len(hits) < PAGE_SIZE:
            return


def _filing_url(hit):
    adsh, filename = hit["_id"].split(":", 1)
    cik = int(hit["_source"]["ciks"][0])
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{filename}"


def collect(settings=None):
    settings = settings or load_settings()
    e = settings["edgar"]
    rng = random.Random(settings["seed"])
    first, last = int(settings["date_range"]["start"][:4]), int(settings["date_range"]["end"][:4])
    rows = []
    for year in range(first, last + 1):
        by_company = defaultdict(list)
        for query in e["queries"]:
            for forms in e["form_groups"]:
                for hit in _hits(query, year, forms, settings, e["max_pages_per_search"]):
                    src = hit["_source"]
                    form = src["root_forms"][0] if src.get("root_forms") else src["form"]
                    by_company[src["ciks"][0]].append((FORM_PREFERENCE.get(form, 3), query, form, hit))
        companies = sorted(by_company)
        rng.shuffle(companies)
        for cik in companies[:e["companies_per_year"]]:
            options = sorted(by_company[cik], key=lambda t: (t[0], t[3]["_id"]))
            for _, query, form, hit in options[:e["filings_per_company"]]:
                src = hit["_source"]
                rows.append({"url": _filing_url(hit), "source_name": src["display_names"][0].split("  (")[0].strip(),
                             "source_type": "filing", "pub_date": src["file_date"], "company": f"CIK {int(cik)}",
                             "found_via": f'EDGAR full-text search "{query}", {year}, form {form} ({src["file_type"]})'})
        print(year, len(by_company), "companies found")
    return write_candidates("edgar", rows)


if __name__ == "__main__":
    collect()
