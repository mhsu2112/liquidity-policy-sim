"""News passages from the Guardian and New York Times search services (session M2.2).

Both need a free key in .env (GUARDIAN_API_KEY, NYT_API_KEY); a missing key skips that
source with a message. Clarification 20: we use only what these services return, and never
read the newspapers' own pages (paywalled or not).
- Guardian: the search call returns each article's body text; passages are cut from it in
  memory at once and the body is discarded.
- NYT: the service returns only a summary and first paragraph; passages are cut from those.
Passages, drops and logs go to signals/corpus/work/ (git-ignored), like every other source.

Run: python -m signals.corpus.collect_news_api [--trial]
"""

import argparse
import time
import urllib.error
import urllib.parse

from signals.corpus.eligibility import Eligibility
from signals.corpus.extract import WORK_DIR, _already_read, paths, record_page
from signals.corpus.fetch import env, get_json
from signals.corpus.passages import Scope, clean_text, load_settings

GUARDIAN = "https://content.guardianapis.com/search"
NYT = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
TRIAL_YEARS = [2008, 2013, 2020, 2023]   # one year per period, for a quick trial


def _years(settings, trial):
    if trial:
        return TRIAL_YEARS
    return range(int(settings["date_range"]["start"][:4]), int(settings["date_range"]["end"][:4]) + 1)


def guardian(settings, trial=False):
    key, n = env("GUARDIAN_API_KEY"), settings["news_api"]
    if not key:
        print("GUARDIAN_API_KEY not set in .env: Guardian skipped")
        return
    scope, elig, files, done, kept = Scope(settings), Eligibility(settings), paths("guardian"), _already_read(), 0
    for query in n["queries"]:
        for year in _years(settings, trial):
            for page in range(1, (1 if trial else n["guardian_max_pages"]) + 1):
                params = {"q": f'"{query}"', "from-date": f"{year}-01-01", "to-date": f"{year}-12-31",
                          "page-size": 50, "page": page, "show-fields": "bodyText", "api-key": key}
                time.sleep(n["guardian_pause_seconds"])
                res = get_json(GUARDIAN + "?" + urllib.parse.urlencode(params), settings)["response"]
                for item in res.get("results", []):
                    body = item.get("fields", {}).get("bodyText", "")
                    if item.get("type") != "article" or not body or item["webUrl"] in done:
                        continue
                    done.add(item["webUrl"])
                    cand = {"url": item["webUrl"], "source_name": "The Guardian", "source_type": "news",
                            "found_via": f'Guardian search service "{query}", {year} (article text as returned)'}
                    kept += record_page(cand, clean_text(body), item["webPublicationDate"][:10], files,
                                        settings, scope, elig)
                if page >= res.get("pages", 0):
                    break
    print(f"Guardian: {kept} passages kept")


def nyt(settings, trial=False):
    key, n = env("NYT_API_KEY"), settings["news_api"]
    if not key:
        print("NYT_API_KEY not set in .env: New York Times skipped")
        return
    scope, elig, files, done, kept = Scope(settings), Eligibility(settings), paths("nyt"), _already_read(), 0
    for query in n["queries"]:
        for year in _years(settings, trial):
            for page in range(1 if trial else n["nyt_max_pages"]):
                params = {"q": f'"{query}"', "begin_date": f"{year}0101", "end_date": f"{year}1231",
                          "page": page, "api-key": key}
                time.sleep(n["nyt_pause_seconds"])           # NYT allows about 5 requests a minute
                try:
                    docs = get_json(NYT + "?" + urllib.parse.urlencode(params), settings)["response"]["docs"] or []
                except urllib.error.HTTPError as err:
                    print(f"NYT stopped at {query} {year} page {page}: {err}")
                    break
                for d in docs:
                    if d["web_url"] in done:
                        continue
                    done.add(d["web_url"])
                    # Summary and first paragraph only, as returned; often the same sentence, so keep it once.
                    parts = [t.strip() for t in (d.get("abstract"), d.get("lead_paragraph")) if t]
                    cand = {"url": d["web_url"], "source_name": "The New York Times", "source_type": "news",
                            "found_via": f'NYT search service "{query}", {year} (summary and first paragraph as returned)'}
                    kept += record_page(cand, clean_text("\n".join(dict.fromkeys(parts))), d["pub_date"][:10],
                                        files, settings, scope, elig)
                if len(docs) < 10:
                    break
    print(f"NYT: {kept} passages kept")


def collect(settings=None, trial=False):
    settings = settings or load_settings()
    WORK_DIR.mkdir(exist_ok=True)
    guardian(settings, trial)
    nyt(settings, trial)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trial", action="store_true", help="one year per period, first results page only")
    collect(trial=ap.parse_args().trial)
