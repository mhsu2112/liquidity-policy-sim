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
BATCH_DIR = WORK_DIR / "review_batches"
CHECK_DIR = HERE / "check"                     # git-ignored: holds passage text
INSTRUCTION_VERSION = "v1"
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


def reviews():
    if not REVIEWS_PATH.exists():
        return {}
    with open(REVIEWS_PATH, newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def make_batches(size, settings):
    done = reviews()
    todo = sorted(i for i in raw_passages() if i not in done)
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
    rows, done = raw_passages(), reviews()
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
