"""Read each candidate page and cut its in-scope passages for review (session M2.2).

Pages are read into memory, cut, and discarded: only the short passages, the link and a
fingerprint of the page text are kept (M2.2 brief: links and short excerpts only). Pages on
paywalled sites are never read (Clarification 20), and there is no fallback to archived copies.
The run can be stopped and restarted; pages already read are skipped.

Everything goes to work/ (git-ignored), one set of files per candidate list:
  passages_raw_<list>.csv   in-scope passages, to be reviewed for eligibility (Clarification 21)
  cut_drops_<list>.csv      every candidate passage rejected while cutting, with its reason
  fetch_log_<list>.csv      pages that gave nothing, and why (not read, paywalled, no date, ...)

Run: python -m signals.corpus.extract [--candidates fed_board] [--sample 200]
"""

import argparse
import csv
import html
import random
import re
import urllib.error
import urllib.parse
from pathlib import Path

from signals.corpus.candidates import CANDIDATE_DIR, read_candidates
from signals.corpus.eligibility import Eligibility
from signals.corpus.fetch import get
from signals.corpus.passages import Scope, clean_text, cut_passages, html_to_text, load_settings, page_fingerprint, stratum_of

WORK_DIR = Path(__file__).resolve().parent / "work"     # intermediate files; rebuilt, not saved to history
# rule_verdict: what the written rules alone would decide; kept only to compare with the review (Clarification 21)
RAW_FIELDS = ["url", "source_name", "source_type", "pub_date", "found_via", "company", "page_sha256", "rule_verdict",
              "passage"]
DROP_FIELDS = ["url", "source_name", "source_type", "pub_date", "reason", "passage"]
LOG_FIELDS = ["url", "status"]


def paths(name):
    """The three work files for one candidate list (or news service)."""
    return {"raw": WORK_DIR / f"passages_raw_{name}.csv", "drops": WORK_DIR / f"cut_drops_{name}.csv",
            "log": WORK_DIR / f"fetch_log_{name}.csv"}


def _already_read():
    done = set()
    for path in [*WORK_DIR.glob("passages_raw_*.csv"), *WORK_DIR.glob("fetch_log_*.csv")]:
        with open(path, newline="") as f:
            # A dropped connection is retried next run; only a site's real answer counts as done.
            done.update(row["url"] for row in csv.DictReader(f)
                        if "status" not in row or not row["status"].startswith("not read: <urlopen")
                        and "Remote end closed" not in row["status"])
    return done


def _append(path, fields, rows):
    if not rows:
        return
    new = not path.exists()
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            writer.writeheader()
        writer.writerows(rows)


_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                        "september", "october", "november", "december"], 1)}
_DATE_PATTERNS = [   # most specific first; each finds the page's OWN date, not a related item's
    r"Published on\s+(\d{1,2}) (\w+) (\d{4})",                                   # Bank of England
    r'property="article:published_time"\s+content="(\d{4})-(\d{2})-(\d{2})',
    r'content="(\d{4})-(\d{2})-(\d{2})[^"]*"\s+property="article:published_time"',
    r'"datePublished"\s*:\s*"(\d{4})-(\d{2})-(\d{2})',                           # structured data
]


def page_date(raw_html):
    """The page's publication date as YYYY-MM-DD, or '' if it does not state one clearly."""
    for pattern in _DATE_PATTERNS:
        m = re.search(pattern, raw_html)
        if not m:
            continue
        a, b, c = m.groups()
        if b.lower() in _MONTHS:                    # "16 April 2008"
            return f"{c}-{_MONTHS[b.lower()]:02d}-{int(a):02d}"
        if b.isdigit():
            return f"{a}-{b}-{c}"
    return ""


def is_paywalled(url, settings):
    host = urllib.parse.urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in settings["copyright"]["paywalled_domains"])


def record_page(cand, text, date, files, settings, scope, eligibility):
    """Cut one page's text and write its passages, drops and log line. Returns the number of passages kept."""
    if stratum_of(date, settings) is None:   # no clear date, or outside 2007-2024
        _append(files["log"], LOG_FIELDS, [{"url": cand["url"], "status": f"read; date '{date}' missing or out of range"}])
        return 0
    drops = []
    passages = cut_passages(text, settings, scope, eligibility, drops)
    base = {**cand, "pub_date": date}
    _append(files["drops"], DROP_FIELDS, [{**base, "reason": r, "passage": p} for r, p in drops])
    if not passages:
        _append(files["log"], LOG_FIELDS, [{"url": cand["url"], "status": "read; no in-scope passage"}])
        return 0
    fingerprint = page_fingerprint(text)
    rows = []
    for p in passages:
        ok, why = eligibility.judge(p)
        rows.append({**base, "page_sha256": fingerprint, "rule_verdict": f"{'keep' if ok else 'drop'}:{why}", "passage": p})
    _append(files["raw"], RAW_FIELDS, rows)
    return len(passages)


def page_text(cand, settings):
    """(text, date) for a web page; the page's own date is used when the listing gave none."""
    body = get(cand["url"], settings)
    if re.search(r"<pre\b", body[:3000], re.IGNORECASE):
        # Preformatted transcripts (congressional hearings) break every line at ~70 characters; rejoin
        # the lines of each paragraph so sentences are whole. Blank lines still separate paragraphs.
        text = html.unescape(re.sub(r"<[^>]+>", "", body))
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
        return clean_text(text), cand["pub_date"] or page_date(body)
    is_html = bool(re.search(r"<(html|body|p|div)\b", body[:5000], re.IGNORECASE))
    return (html_to_text(body) if is_html else clean_text(body)), cand["pub_date"] or page_date(body)


def run(only=None, limit=None, sample=None, settings=None, sample_seed=None, urls=None):
    settings = settings or load_settings()
    scope, eligibility = Scope(settings), Eligibility(settings)
    WORK_DIR.mkdir(exist_ok=True)
    files = paths(only or "all")
    done = _already_read()
    if only:
        with open(CANDIDATE_DIR / f"{only}.csv", newline="") as f:
            todo = list(csv.DictReader(f))
    else:
        todo = read_candidates()
    todo = [c for c in todo if c["url"] not in done]
    if urls:   # re-read exactly these pages (e.g. the same trial pages under a new rule)
        todo = [c for c in todo if c["url"] in urls]
    if sample:   # a seeded random spread of pages, for trial runs
        seed = settings["seed"] if sample_seed is None else sample_seed
        todo = random.Random(seed).sample(todo, min(sample, len(todo)))
    todo = todo[:limit]
    kept = 0
    for n, cand in enumerate(todo, 1):
        if is_paywalled(cand["url"], settings):   # Clarification 20: never read paywalled pages
            _append(files["log"], LOG_FIELDS, [{"url": cand["url"], "status": "skipped: paywalled site"}])
            continue
        try:
            text, date = page_text(cand, settings)
        except (urllib.error.URLError, TimeoutError, ValueError, UnicodeError, OSError) as err:
            _append(files["log"], LOG_FIELDS, [{"url": cand["url"], "status": f"not read: {err}"[:200]}])
            continue
        kept += record_page(cand, text, date, files, settings, scope, eligibility)
        if n % 50 == 0:
            print(f"  {n}/{len(todo)} pages read, {kept} passages kept", flush=True)
    print(f"done: {len(todo)} pages read, {kept} passages kept", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", help="read only this candidate file, e.g. fed_board")
    ap.add_argument("--limit", type=int, help="read at most this many pages (for a trial run)")
    ap.add_argument("--sample", type=int, help="read a seeded random sample of this many pages (trial run)")
    ap.add_argument("--sample-seed", type=int, help="seed for --sample (a fresh trial uses a new seed)")
    ap.add_argument("--urls", help="a text file of page addresses, one per line: read only these")
    args = ap.parse_args()
    urls = set(Path(args.urls).read_text().split()) if args.urls else None
    run(args.candidates, args.limit, args.sample, sample_seed=args.sample_seed, urls=urls)
