"""M2.6: score the whole corpus with the M2.4 configuration and show the historical range (release v0.1).

Same question as the gold-set check (Clarification 30 Part A): the labeling guide's question and
four level descriptions at commit a0f08db, the passage as the only state. The 293 corpus passages
already read in M2.4 reuse those answers (the gold set is run once); the rest are asked once each.
Filings are weighted by 1 / their period's sampling rate (Clarification 23); other passages weigh 1.

Writes signals/corpus_scores.csv (no passage text) and signals/historical_range.csv.
Run: python -m signals.corpus_scores   (or: make corpus-scores)
"""

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

from signals.corpus.build_corpus import CORPUS_PATH, PRIVATE_PATH
from signals.gold_set.draw import KEY_PATH
from signals.gold_set.jev_check import ANSWERS_PATH, guide_question, start_checks, to_row
from signals.jev_client import ask, score

ROOT = Path(__file__).resolve().parents[1]
SCORES_PATH = ROOT / "signals" / "corpus_scores.csv"
RANGE_PATH = ROOT / "signals" / "historical_range.csv"
FIELDS = ["corpus_id", "stratum", "source_type", "weight", "label", "p1", "p2", "p3", "p4", "expected_score",
          "model_version", "source"]
PERIODS = {"S-A": "2007–09", "S-B": "2010–19", "S-C": "2020–21", "S-D": "2022–24"}


def weight(row):
    """Clarification 23: filings stand for unreviewed company-years in their period."""
    return 1 / float(row["filing_sampling_rate"]) if row["source_type"] == "filing" else 1.0


def reused_answers():
    """{corpus ID: M2.4 answer row} for passages read in the gold-set check."""
    with open(KEY_PATH, newline="") as f:
        to_corpus = {k["gold_id"]: k["corpus_id"] for k in csv.DictReader(f)}
    with open(ANSWERS_PATH, newline="") as f:
        return {to_corpus[r["ID"]]: r for r in csv.DictReader(f)}


def run():
    start_checks()
    instructions, levels = guide_question()
    question = {"level": score(instructions, levels)}
    with open(CORPUS_PATH, newline="") as f:
        corpus = list(csv.DictReader(f))
    with open(PRIVATE_PATH, newline="") as f:
        text = {r["id"]: r["passage"] for r in csv.DictReader(f)}
    reused = reused_answers()
    done = {}
    if SCORES_PATH.exists():                              # resume: never re-ask a passage already scored
        with open(SCORES_PATH, newline="") as f:
            done = {r["corpus_id"]: r for r in csv.DictReader(f)}
    rows = []
    for c in corpus:
        base = {"corpus_id": c["id"], "stratum": c["stratum"], "source_type": c["source_type"], "weight": round(weight(c), 6)}
        if c["id"] in done:
            rows.append(done[c["id"]])
        elif c["id"] in reused:
            a = reused[c["id"]]
            rows.append({**base, **{k: a[k] for k in ("label", "p1", "p2", "p3", "p4", "expected_score", "model_version")},
                         "source": "M2.4 answer reused"})
        else:
            a = to_row(c["id"], "corpus", ask(text[c["id"]], question, mock=False, tag="M2.6-v0.1"))
            rows.append({**base, **{k: a[k] for k in ("label", "p1", "p2", "p3", "p4", "expected_score", "model_version")},
                         "source": "M2.6 call"})
            _write(rows)
    _write(rows)
    ranges = historical_range(rows)
    print(f"wrote {SCORES_PATH.name} ({len(rows)} passages) and {RANGE_PATH.name}")
    return rows, ranges


def _write(rows):
    with open(SCORES_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _weighted_quantile(x, w, q):
    order = np.argsort(x)
    x, w = np.asarray(x)[order], np.asarray(w)[order]
    cum = (np.cumsum(w) - 0.5 * w) / w.sum()
    return float(np.interp(q, cum, x))


def summarize(rows):
    """Weighted mean expected score, level shares, distress-leaning share, 10th-90th percentile."""
    x = np.array([float(r["expected_score"]) for r in rows])
    w = np.array([float(r["weight"]) for r in rows])
    labels = np.array([int(r["label"]) for r in rows])
    share = {lvl: float(w[labels == lvl].sum() / w.sum()) for lvl in (1, 2, 3, 4)}
    return {"passages": len(rows), "weighted_n": round(float(w.sum()), 1), "mean_expected": float((x * w).sum() / w.sum()),
            "share_1": share[1], "share_2": share[2], "share_3": share[3], "share_4": share[4],
            "distress_leaning": share[3] + share[4],
            "p10": _weighted_quantile(x, w, 0.10), "p90": _weighted_quantile(x, w, 0.90)}


def historical_range(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[("all", "all")].append(r)
        groups[("period", r["stratum"])].append(r)
        groups[("source_type", r["source_type"])].append(r)
    out = [{"group": g, "value": PERIODS.get(v, v), **summarize(members)} for (g, v), members in groups.items()]
    order = {"all": 0, "period": 1, "source_type": 2}
    out.sort(key=lambda r: (order[r["group"]], r["value"]))
    with open(RANGE_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in out)
    return out


if __name__ == "__main__":
    run()
