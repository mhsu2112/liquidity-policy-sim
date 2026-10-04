"""Eligibility review of in-scope passages (session M2.2; Clarification 21).

Every in-scope passage is read and decided against signals/corpus/eligibility_instruction.md. The
reader sees only an ID and the passage text: no source, date or link. Decisions are published
by ID and excerpt hash, without text, in eligibility_reviews.csv.

  python -m signals.corpus.review --batches 60     write unreviewed passages to work/review_batches/
                                                   (ID and text only, seeded random order, 60 a batch)
  python -m signals.corpus.review --import FILE    add a batch of decisions (id,decision,reason), checked
  python -m signals.corpus.review --check-sheet    the owner's random 50 for hand-checking (git-ignored;
                                                   the reviewer's decisions are not shown on it)
  python -m signals.corpus.review --score-check FILE   agreement between the owner's sheet and the reviews
"""

import argparse
import csv
import datetime
import random
from pathlib import Path

from signals.corpus.build_corpus import excerpt_sha256, passage_id
from signals.corpus.extract import WORK_DIR
from signals.corpus.passages import load_settings

HERE = Path(__file__).resolve().parent
REVIEWS_PATH = HERE / "eligibility_reviews.csv"
FILING_SAMPLE_PATH = HERE / "filing_sample.csv"   # Clarification 23: which company-years are reviewed
BATCH_DIR = WORK_DIR / "review_batches"
CHECK_DIR = HERE / "check"                     # git-ignored: holds passage text
INSTRUCTION_VERSION = "v2"   # Clarification 22 (v1 decisions keep "v1")
REVIEWER = "claude-opus-5-5"                   # model ID recorded on every decision (Clarification 21)
KEEP_CODES = {"borrowing", "planned", "avoided", "perception"}
DROP_CODES = {"facility_description", "funding_source_list", "policy_design", "not_bank_borrower",
              "no_borrowing", "personal_data"}
REVIEW_FIELDS = ["id", "excerpt_sha256", "decision", "reason", "doubtful", "reviewer", "instruction", "date"]
CHECK_SEED = 20261003


def raw_passages():
    """Every passage cut so far, keyed by its stable ID."""
    rows = {}
    for path in sorted(WORK_DIR.glob("passages_raw_*.csv")):
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                rows[passage_id(r)] = r
    return rows


def reviews(version=None):
    """Latest decision per passage (the highest instruction version), or only those under `version`.

    Earlier-version decisions stay in the file as a record; they are never overwritten.
    """
    if not REVIEWS_PATH.exists():
        return {}
    out = {}
    with open(REVIEWS_PATH, newline="") as f:
        for r in csv.DictReader(f):
            if version and r["instruction"] != version:
                continue
            if r["id"] not in out or r["instruction"] >= out[r["id"]]["instruction"]:
                out[r["id"]] = r
    return out


def company_year(row, settings):
    from signals.corpus.passages import stratum_of
    return row["company"], row["pub_date"][:4], stratum_of(row["pub_date"], settings)


def draw_filing_sample(settings):
    """Clarification 23: a seeded random sample of company-years per period; every passage of a sampled
    company-year is reviewed. Writes filing_sample.csv (all company-years, sampled Y/N) and returns
    the set of sampled (company, year) keys and each period's sampling rate."""
    keys = {}
    for r in raw_passages().values():
        if r["source_type"] == "filing":
            c, y, s = company_year(r, settings)
            if s:
                keys[(c, y)] = s
    rng = random.Random(settings["seed"])
    limit = settings["caps"]["filing_review_sample_per_period"]
    sampled, rates = set(), {}
    for s in settings["strata"]:
        pool = sorted(k for k, v in keys.items() if v == s)
        pick = rng.sample(pool, min(limit, len(pool)))
        sampled.update(pick)
        rates[s] = len(pick) / len(pool) if pool else 1.0
    with open(FILING_SAMPLE_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company", "year", "stratum", "sampled", "period_sampling_rate"])
        for k in sorted(keys):
            w.writerow([k[0], k[1], keys[k], "Y" if k in sampled else "N", f"{rates[keys[k]]:.4f}"])
    return sampled, rates


def make_batches(size, settings):
    done = reviews(INSTRUCTION_VERSION)          # re-review anything decided only under an older version
    sampled, rates = draw_filing_sample(settings)
    rows_all = raw_passages()
    todo = sorted(i for i, r in rows_all.items() if i not in done
                  and (r["source_type"] != "filing" or company_year(r, settings)[:2] in sampled))
    print("Filing sampling rates by period: " + ", ".join(f"{s} {v:.0%}" for s, v in rates.items()))
    random.Random(settings["seed"]).shuffle(todo)   # mixes sources and periods within a batch
    rows = raw_passages()
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    start = len(list(BATCH_DIR.glob("batch_*.csv")))
    for k in range(0, len(todo), size):
        with open(BATCH_DIR / f"batch_{start + k // size + 1:03d}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "passage"])
            w.writerows([i, rows[i]["passage"]] for i in todo[k:k + size])
    print(f"{len(todo)} passages to review, in {-(-len(todo) // size)} batches of up to {size} ({BATCH_DIR})")


def parse_decision(decision, reason):
    """('keep'|'drop', code, doubtful) after checking the code fits the decision and the instruction."""
    doubtful = reason.endswith("?")
    code = reason.rstrip("?").strip()
    if decision == "keep" and code in KEEP_CODES or decision == "drop" and code in DROP_CODES:
        return decision, code, doubtful
    raise ValueError(f"'{decision},{reason}' is not a valid decision and reason under the instruction")


def import_decisions(path):
    rows, done = raw_passages(), reviews(INSTRUCTION_VERSION)
    new = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f, fieldnames=["id", "decision", "reason"]):
            if r["id"] in ("id", "") or r["id"] in done:
                continue
            if r["id"] not in rows:
                raise ValueError(f"{r['id']}: no such passage")
            decision, code, doubtful = parse_decision(r["decision"].strip(), r["reason"].strip())
            new.append({"id": r["id"], "excerpt_sha256": excerpt_sha256(rows[r["id"]]["passage"]),
                        "decision": decision, "reason": code, "doubtful": "Y" if doubtful else "",
                        "reviewer": REVIEWER, "instruction": INSTRUCTION_VERSION,
                        "date": datetime.date.today().isoformat()})
            done[r["id"]] = new[-1]
    first = not REVIEWS_PATH.exists()
    with open(REVIEWS_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        if first:
            w.writeheader()
        w.writerows(new)
    print(f"{len(new)} decisions added from {Path(path).name}")


def check_sheet(n=50):
    """The owner's random sample, text only, with blank columns to fill in Excel."""
    rows, done = raw_passages(), reviews()
    ids = sorted(i for i in done if i in rows)
    pick = random.Random(CHECK_SEED).sample(ids, min(n, len(ids)))
    CHECK_DIR.mkdir(exist_ok=True)
    path = CHECK_DIR / "eligibility_check_owner.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "passage", "your_decision (keep/drop)", "note"])
        w.writerows([i, rows[i]["passage"], "", ""] for i in pick)
    print(f"wrote {path} ({len(pick)} passages)")


def score_check(path):
    done = reviews()
    with open(path, newline="", encoding="utf-8-sig") as f:
        sheet = [r for r in csv.DictReader(f) if r["your_decision (keep/drop)"].strip()]
    agree = sum(r["your_decision (keep/drop)"].strip().lower() == done[r["id"]]["decision"] for r in sheet)
    print(f"Owner and reviewer agree on {agree} of {len(sheet)} ({agree / len(sheet):.0%})")
    for r in sheet:
        if r["your_decision (keep/drop)"].strip().lower() != done[r["id"]]["decision"]:
            print(f"  {r['id']}: owner {r['your_decision (keep/drop)']}, reviewer {done[r['id']]['decision']} "
                  f"({done[r['id']]['reason']})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", type=int)
    ap.add_argument("--import", dest="import_path")
    ap.add_argument("--check-sheet", action="store_true")
    ap.add_argument("--score-check")
    a = ap.parse_args()
    if a.batches:
        make_batches(a.batches, load_settings())
    if a.import_path:
        import_decisions(a.import_path)
    if a.check_sheet:
        check_sheet()
    if a.score_check:
        score_check(a.score_check)
