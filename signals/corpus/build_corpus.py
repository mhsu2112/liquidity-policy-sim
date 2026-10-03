"""Turn the raw passages into the corpus files (session M2.2, rules of Clarification 20).

Steps, in order. Every passage that does not reach the corpus is logged with the step that
dropped it (work/build_drops.csv), so nothing disappears silently:
1. recheck      re-apply the current quality, scope, personal-data and eligibility rules, so a
                tightened rule takes effect without reading the pages again;
2. excluded     passages listed by id in exclusions.csv (e.g. a private individual's words);
3. near_duplicate  passages sharing most of their 5-word runs (a syndicated story, repeated
                boilerplate): the earliest is kept;
4. document_cap at most 2 passages per document;
5. company_year_cap  filings: one passage per company per year;
6. type_cap     no source type above 25% of any period (see type_cap_sizes).
Choices among equals use the seeded random order, never the wording.

Outputs:
  corpus.csv              public: id, link, date, source, type, period, SHA-256 of the excerpt, and
                          the excerpt itself only for official and SEC text (Clarification 20, item 4)
  excerpts_private.csv    git-ignored: id and excerpt for every row (news and analyst text stay here)
  work/build_summary.json counts before and after the type cap, for the readout

Run: python -m signals.corpus.build_corpus
"""

import csv
import hashlib
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path

from signals.corpus.eligibility import Eligibility
from signals.corpus.extract import WORK_DIR
from signals.corpus.passages import Scope, load_settings, reads_cleanly, stratum_of

HERE = Path(__file__).resolve().parent
CORPUS_PATH = HERE / "corpus.csv"
PRIVATE_PATH = HERE / "excerpts_private.csv"
EXCLUSIONS_PATH = HERE / "exclusions.csv"
DROPS_PATH = WORK_DIR / "build_drops.csv"
SUMMARY_PATH = WORK_DIR / "build_summary.json"
FIELDS = ["id", "document_id", "url", "pub_date", "source_name", "source_type", "stratum", "found_via",
          "excerpt_sha256", "passage"]


def passage_id(row):
    """Stable id from the link and the passage itself, so rebuilding never renumbers rows."""
    return "P" + hashlib.sha1(f"{row['url']}|{row['passage']}".encode()).hexdigest()[:10]


def document_id(url):
    return "D" + hashlib.sha1(url.encode()).hexdigest()[:10]


def excerpt_sha256(passage):
    return hashlib.sha256(passage.encode("utf-8")).hexdigest()


def shingles(text, n):
    words = re.findall(r"[a-z0-9$%]+", text.lower())
    return {" ".join(words[i:i + n]) for i in range(max(1, len(words) - n + 1))}


def remove_near_duplicates(rows, settings):
    """(kept, dropped): keep the earliest of each group whose 5-word-run overlap reaches the threshold."""
    d = settings["dedup"]
    rows = sorted(rows, key=lambda r: (r["pub_date"], r["url"], r["passage"]))
    kept, dropped, kept_shingles, index = [], [], [], defaultdict(list)
    for row in rows:
        sh = shingles(row["passage"], d["shingle_words"])
        shared = defaultdict(int)
        for s in sh:
            for k in index[s]:
                shared[k] += 1
        if any(n / len(sh | kept_shingles[k]) >= d["jaccard_threshold"] for k, n in shared.items()):
            dropped.append(row)
            continue
        for s in sh:
            index[s].append(len(kept))
        kept.append(row)
        kept_shingles.append(sh)
    return kept, dropped


def _seeded(rows, rng):
    """Rows in a seeded random order, starting from a fixed sort so the result never depends on file order."""
    rows = sorted(rows, key=lambda r: r["id"])
    rng.shuffle(rows)
    return rows


def keep_per_group(rows, key, limit, rng):
    """(kept, dropped): at most `limit` rows per group, chosen in seeded random order."""
    groups = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    kept, dropped = [], []
    for k in sorted(groups):
        ordered = _seeded(groups[k], rng)
        kept += ordered[:limit]
        dropped += ordered[limit:]
    return kept, dropped


def type_cap_sizes(counts, share):
    """How many passages of each source type a period keeps so that no type exceeds `share` of the total.

    The period keeps the largest total N for which every type can hold at most floor(share x N) and the
    types together still fill N. Each type keeps min(its count, floor(share x N)); if that adds up to
    more than N, the largest allowances are reduced one at a time (ties by type name) until it equals N.
    With fewer than 1/share types present (4 types for 25%), no N above zero works.
    """
    total = sum(counts.values())
    for n in range(total, -1, -1):
        cap = math.floor(share * n)
        sizes = {t: min(c, cap) for t, c in counts.items()}
        if sum(sizes.values()) >= n:
            while sum(sizes.values()) > n:
                biggest = max(sorted(sizes), key=lambda t: sizes[t])
                sizes[biggest] -= 1
            return sizes
    return {t: 0 for t in counts}


def build(settings=None):
    settings = settings or load_settings()
    rng = random.Random(settings["seed"])
    caps = settings["caps"]
    scope, elig = Scope(settings), Eligibility(settings)
    drops = []

    def drop(rows, reason):
        drops.extend({**r, "reason": reason} for r in rows)

    raw = []
    for path in sorted(WORK_DIR.glob("passages_raw_*.csv")):
        with open(path, newline="") as fh:
            raw.extend(csv.DictReader(fh))
    rows = []
    for r in raw:                                             # step 1: recheck
        r["stratum"], r["id"] = stratum_of(r["pub_date"], settings), passage_id(r)
        if not r["stratum"]:
            reason = "recheck:date"
        elif not reads_cleanly(r["passage"], settings["passage"]):
            reason = "recheck:quality"
        elif not scope.passage_in_scope(r["passage"]):
            reason = "recheck:out_of_scope"
        elif elig.personal_data(r["passage"]):
            reason = "recheck:personal_data"
        else:
            ok, why = elig.judge(r["passage"])
            reason = None if ok else f"recheck:ineligible:{why}"
            r["eligibility"] = why
        if reason:
            drop([r], reason)
        else:
            rows.append(r)

    excluded = {}                                             # step 2: exclusion list
    if EXCLUSIONS_PATH.exists():
        with open(EXCLUSIONS_PATH, newline="") as fh:
            excluded = {e["id"]: e["reason"] for e in csv.DictReader(fh)}
    drop([r for r in rows if r["id"] in excluded], "excluded")
    rows = [r for r in rows if r["id"] not in excluded]

    rows, dup = remove_near_duplicates(rows, settings)        # step 3
    drop(dup, "near_duplicate")
    rows, over = keep_per_group(rows, lambda r: r["url"], caps["max_per_document"], rng)   # step 4
    drop(over, "document_cap")
    filings = [r for r in rows if r["source_type"] == "filing"]                            # step 5
    kept_f, over = keep_per_group(filings, lambda r: (r["company"], r["pub_date"][:4]),
                                  caps["filings_per_company_per_year"], rng)
    drop(over, "company_year_cap")
    rows = [r for r in rows if r["source_type"] != "filing"] + kept_f

    final, summary = [], {}                                   # step 6: type cap per period
    for stratum in settings["strata"]:
        by_type = defaultdict(list)
        for r in rows:
            if r["stratum"] == stratum:
                by_type[r["source_type"]].append(r)
        counts = {t: len(v) for t, v in sorted(by_type.items())}
        sizes = type_cap_sizes(counts, caps["max_type_share_per_stratum"])
        for t, members in sorted(by_type.items()):
            ordered = _seeded(members, rng)
            final += ordered[:sizes[t]]
            drop(ordered[sizes[t]:], "type_cap")
        summary[stratum] = {"before_cap": counts, "after_cap": sizes}

    public = set(settings["copyright"]["public_text_types"])
    for r in final:
        r["document_id"], r["excerpt_sha256"] = document_id(r["url"]), excerpt_sha256(r["passage"])
    final.sort(key=lambda r: (r["stratum"], r["pub_date"], r["id"]))
    with open(CORPUS_PATH, "w", newline="") as fh:            # public: no news or analyst wording
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows({**r, "passage": r["passage"] if r["source_type"] in public else ""} for r in final)
    with open(PRIVATE_PATH, "w", newline="") as fh:           # git-ignored
        w = csv.DictWriter(fh, fieldnames=["id", "passage"], extrasaction="ignore")
        w.writeheader()
        w.writerows(final)
    with open(DROPS_PATH, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "url", "source_type", "stratum", "pub_date", "reason", "passage"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(drops)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=1))
    print(f"{len(raw)} raw passages -> {len(final)} in the corpus ({len(drops)} dropped at build; see {DROPS_PATH.name})")
    return final


if __name__ == "__main__":
    build()
