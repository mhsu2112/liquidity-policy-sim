"""Turn the reviewed passages into the corpus files (session M2.2; Clarifications 20 and 21).

Steps, in order. Every passage that does not reach the corpus is logged with the step that
dropped it (work/build_drops.csv), so nothing disappears silently:
1. recheck      re-apply the current quality, scope and personal-data rules (no re-reading of pages);
2. review       filings outside the reviewed company-year sample are dropped as `filing_not_sampled`
                (Clarification 23); then keep only passages the review decided `keep` (Clarification 21);
                passages not yet reviewed are logged as `unreviewed`, never kept;
3. excluded     passages listed by id in exclusions.csv (e.g. a private individual's words);
4. near_duplicate  passages sharing most of their 5-word runs (a syndicated story, repeated
                boilerplate): the earliest is kept;
5. document_cap at most 2 passages per document;
6. company_year_cap  filings: one passage per company per year.
There is no source-type cap in the corpus: Clarification 21 moves the 25% cap to the M2.3 draw.
Choices among equals use the seeded random order, never the wording.

Outputs:
  corpus.csv              public: id, link, date, source, type, period, SHA-256 of the excerpt, the
                          review's reason code, and the excerpt itself only for official and SEC text
  excerpts_private.csv    git-ignored: id and excerpt for every row (news and analyst text stay here)
  work/build_summary.json counts by period and source type, for the readout

Run: python -m signals.corpus.build_corpus
"""

import csv
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
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
REVIEWS_PATH = HERE / "eligibility_reviews.csv"
OWNER_CHECK_PATH = HERE / "eligibility_owner_check.csv"        # Clarification 22: owner's final decisions override
GOLD_EXCLUSIONS_PATH = HERE / "gold_set_exclusions.csv"        # Clarification 22: passages already seen (hashes)
SEEN_PRIVATE_PATH = HERE / "check" / "seen_passages_private.csv"   # git-ignored text of the same, for near-copies
FIELDS = ["id", "document_id", "url", "pub_date", "source_name", "source_type", "stratum", "found_via",
          "excerpt_sha256", "eligibility", "decided_by", "gold_set_eligible", "gold_set_exclusion",
          "filing_sampling_rate", "passage"]


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


def flag_gold_set(rows, settings):
    """Clarification 22: mark passages the gold-set draw must skip (they stay in the corpus).

    Skipped: doubtful review calls; passages the owner has already seen (his check sheet and every
    trial-examples file), matched by excerpt hash, and also as near-copies of the seen text when the
    git-ignored copy of that text is on this computer.
    """
    seen = {}
    if GOLD_EXCLUSIONS_PATH.exists():
        with open(GOLD_EXCLUSIONS_PATH, newline="") as fh:
            seen = {e["excerpt_sha256"]: e["reason"] for e in csv.DictReader(fh)}
    n, threshold = settings["dedup"]["shingle_words"], settings["dedup"]["jaccard_threshold"]
    seen_text = []                                           # (5-word runs, reason) of each seen passage
    if SEEN_PRIVATE_PATH.exists():
        with open(SEEN_PRIVATE_PATH, newline="") as fh:
            seen_text = [(shingles(e["passage"], n), e["reason"]) for e in csv.DictReader(fh)]
    for r in rows:
        why = seen.get(excerpt_sha256(r["passage"]))
        if not why:
            sh = shingles(r["passage"], n)
            why = next((f"{reason} (near-copy)" for other, reason in seen_text
                        if len(sh & other) / len(sh | other) >= threshold), None)
        if not why and r.get("doubtful") == "Y":
            why = "doubtful_review"
        r["gold_set_eligible"], r["gold_set_exclusion"] = ("N", why) if why else ("Y", "")


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
    from signals.corpus.review import reviews              # here to avoid a circular import
    decisions = {i: {**d, "decided_by": f"{d['reviewer']} ({d['instruction']})"} for i, d in reviews().items()}
    if OWNER_CHECK_PATH.exists():                           # Clarification 22: the owner's final decisions override
        with open(OWNER_CHECK_PATH, newline="") as fh:
            for o in csv.DictReader(fh):
                d = decisions.get(o["id"], {"reason": "", "doubtful": ""})
                decisions[o["id"]] = {**d, "id": o["id"], "excerpt_sha256": o["excerpt_sha256"],
                                      "decision": o["owner_final_after_annotation"], "decided_by": "owner check",
                                      "reason": d["reason"] if d.get("decision") == o["owner_final_after_annotation"]
                                      else f"owner_{o['owner_final_after_annotation']}"}
    sample = {}                                               # Clarification 23: filing company-years reviewed
    sample_path = HERE / "filing_sample.csv"
    if sample_path.exists():
        with open(sample_path, newline="") as fh:
            sample = {(x["company"], x["year"]): x for x in csv.DictReader(fh)}
    rows, seen = [], set()
    for r in raw:
        r["stratum"], r["id"] = stratum_of(r["pub_date"], settings), passage_id(r)
        if r["id"] in seen:
            continue   # the same passage read twice (e.g. a page listed by two collectors)
        seen.add(r["id"])
        d = decisions.get(r["id"])
        if not r["stratum"]:                                  # step 1: recheck
            reason = "recheck:date"
        elif not reads_cleanly(r["passage"], settings["passage"]):
            reason = "recheck:quality"
        elif not scope.passage_in_scope(r["passage"]):
            reason = "recheck:out_of_scope"
        elif elig.personal_data(r["passage"]):
            reason = "recheck:personal_data"
        elif r["source_type"] == "filing" and sample.get((r["company"], r["pub_date"][:4]), {}).get("sampled") != "Y":
            reason = "filing_not_sampled"                     # Clarification 23
        elif d is None:                                       # step 2: review
            reason = "unreviewed"
        elif d["excerpt_sha256"] != excerpt_sha256(r["passage"]):
            reason = "review_hash_mismatch"
        elif d["decision"] != "keep":
            reason = f"review:{d['reason']}"
        else:
            reason, r["eligibility"], r["decided_by"], r["doubtful"] = None, d["reason"], d["decided_by"], d.get("doubtful", "")
            if r["source_type"] == "filing":
                r["filing_sampling_rate"] = sample[(r["company"], r["pub_date"][:4])]["period_sampling_rate"]
        if reason:
            drop([r], reason)
        else:
            rows.append(r)

    excluded = {}                                             # step 3: exclusion list
    if EXCLUSIONS_PATH.exists():
        with open(EXCLUSIONS_PATH, newline="") as fh:
            excluded = {e["id"]: e["reason"] for e in csv.DictReader(fh)}
    drop([r for r in rows if r["id"] in excluded], "excluded")
    rows = [r for r in rows if r["id"] not in excluded]

    rows, dup = remove_near_duplicates(rows, settings)        # step 4
    drop(dup, "near_duplicate")
    rows, over = keep_per_group(rows, lambda r: r["url"], caps["max_per_document"], rng)   # step 5
    drop(over, "document_cap")
    filings = [r for r in rows if r["source_type"] == "filing"]                            # step 6
    kept_f, over = keep_per_group(filings, lambda r: (r["company"], r["pub_date"][:4]),
                                  caps["filings_per_company_per_year"], rng)
    drop(over, "company_year_cap")
    final = [r for r in rows if r["source_type"] != "filing"] + kept_f

    summary = {s: dict(sorted(Counter(r["source_type"] for r in final if r["stratum"] == s).items()))
               for s in settings["strata"]}
    flag_gold_set(final, settings)
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
    print(f"{len(seen)} in-scope passages -> {len(final)} in the corpus ({len(drops)} dropped at build; see {DROPS_PATH.name})")
    return final


if __name__ == "__main__":
    build()
