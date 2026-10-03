"""Plain-English readout of the corpus (session M2.2; Clarification 20).

Prints: the eligible share (eligible / in scope) and drop reasons by source type; counts by
period and source type before and after the 25% type cap; any period under 150; and random rows.
Excerpt text is read from the git-ignored private file, so it is shown on this computer only.
`--examples N` also writes N random rows, spread across periods and types, to the git-ignored
signals/corpus/trial_examples.md.

Run: python -m signals.corpus.readout [--rows 20] [--examples 30]   (or: make corpus-sample)
"""

import argparse
import csv
import json
import random
import textwrap
from collections import Counter, defaultdict

from signals.corpus.build_corpus import CORPUS_PATH, DROPS_PATH, PRIVATE_PATH, SUMMARY_PATH
from signals.corpus.candidates import SOURCE_TYPES
from signals.corpus.extract import WORK_DIR
from signals.corpus.passages import load_settings, stratum_of

SAMPLE_SEED = 2   # any fixed number; only chooses which rows are shown


def _read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _table(title, counts, strata, minimum=None):
    print(f"\n{title}")
    print(f"{'source type':<20}" + "".join(f"{s:>8}" for s in strata) + f"{'total':>8}")
    for t in SOURCE_TYPES:
        print(f"{t:<20}" + "".join(f"{counts.get((s, t), 0):>8}" for s in strata)
              + f"{sum(counts.get((s, t), 0) for s in strata):>8}")
    totals = [sum(counts.get((s, t), 0) for t in SOURCE_TYPES) for s in strata]
    print(f"{'total':<20}" + "".join(f"{n:>8}" for n in totals) + f"{sum(totals):>8}")
    if minimum:
        for s, n in zip(strata, totals):
            if n < minimum:
                print(f"  SHORT: {s} has {n}, below the minimum of {minimum}. Report before any gold-set draw; not padded.")


def eligibility_tally(settings):
    """In-scope candidates, how many were eligible, and why the rest were dropped, by source type."""
    cut = [r for p in sorted(WORK_DIR.glob("cut_drops_*.csv")) for r in _read(p)]
    raw = [r for p in sorted(WORK_DIR.glob("passages_raw_*.csv")) for r in _read(p)]
    in_scope_drops = [r for r in cut if r["reason"].startswith(("ineligible:", "personal_data"))]
    by_type = defaultdict(Counter)
    for r in in_scope_drops:
        by_type[r["source_type"]][r["reason"]] += 1
    eligible = Counter(r["source_type"] for r in raw)
    print("\nEligibility while cutting (Clarification 20): in-scope passages, eligible share, drop reasons")
    for t in SOURCE_TYPES:
        n_in = eligible[t] + sum(by_type[t].values())
        if n_in:
            reasons = ", ".join(f"{k.replace('ineligible:', '')} {v}" for k, v in by_type[t].most_common())
            print(f"  {t:<19} {eligible[t]:>4} of {n_in:>4} eligible ({eligible[t] / n_in:5.1%})   dropped: {reasons or '-'}")
    n_in = len(raw) + len(in_scope_drops)
    if n_in:
        print(f"  {'all':<19} {len(raw):>4} of {n_in:>4} eligible ({len(raw) / n_in:5.1%})")
    other = Counter(r["reason"] for r in cut if r not in in_scope_drops)
    print("  Also dropped before the scope test: " + ", ".join(f"{k} {v}" for k, v in other.most_common()))
    if DROPS_PATH.exists():
        print("  Dropped at build: " + ", ".join(f"{k} {v}" for k, v in Counter(r["reason"] for r in _read(DROPS_PATH)).most_common()))


def spread_sample(rows, n, rng):
    """n random rows, spread as evenly as possible across periods, and across types within a period."""
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by[r["stratum"]][r["source_type"]].append(r)
    for s in by.values():
        for v in s.values():
            rng.shuffle(v)
    picks, strata = [], sorted(by)
    while len(picks) < min(n, len(rows)):
        for s in strata:
            types = [t for t in sorted(by[s]) if by[s][t]]
            if types and len(picks) < n:
                t = types[sum(1 for p in picks if p["stratum"] == s) % len(types)]
                picks.append(by[s][t].pop())
    return sorted(picks, key=lambda r: (r["stratum"], r["pub_date"]))


def main(n_rows=20, n_examples=0):
    settings = load_settings()
    strata = list(settings["strata"])
    rows = _read(CORPUS_PATH)
    text = {r["id"]: r["passage"] for r in _read(PRIVATE_PATH)} if PRIVATE_PATH.exists() else {}
    print(f"Calibration corpus: {len(rows)} passages (Clarification 20: all eligible passages, at least "
          f"{settings['targets']['min_per_stratum']} per period)")
    eligibility_tally(settings)
    if SUMMARY_PATH.exists():
        summary = json.loads(SUMMARY_PATH.read_text())
        before = {(s, t): c for s, v in summary.items() for t, c in v["before_cap"].items()}
        _table("Before the 25% type cap (after duplicates, document and company-year caps):", before, strata)
        for s, v in summary.items():
            cut = {t: v["before_cap"][t] - v["after_cap"][t] for t in v["before_cap"] if v["before_cap"][t] > v["after_cap"][t]}
            if cut:
                print(f"  {s}: the cap removed " + ", ".join(f"{k} {c}" for k, c in cut.items()))
    _table("In the corpus (after the type cap):", Counter((r["stratum"], r["source_type"]) for r in rows), strata,
           settings["targets"]["min_per_stratum"])

    rng = random.Random(SAMPLE_SEED)
    print(f"\n{n_rows} random rows:")
    for r in rng.sample(rows, min(n_rows, len(rows))):
        print(f"\n{r['id']}  {r['stratum']}  {r['pub_date']}  {r['source_type']}  {r['source_name']}\n  {r['url']}")
        print(textwrap.indent(textwrap.fill(text.get(r["id"], "(excerpt not on this computer)"), 100), "  > "))
    if n_examples:
        path = CORPUS_PATH.parent / "trial_examples.md"
        with open(path, "w") as f:
            f.write(f"# M2.2 trial examples ({n_examples} random passages)\n\nDrawn at random (seed {settings['seed']}), "
                    "spread across periods and source types. Not hand-picked. Contains news and analyst text: "
                    "git-ignored, never published. No passage has been sent to Jev.\n")
            for i, r in enumerate(spread_sample(rows, n_examples, random.Random(settings["seed"])), 1):
                f.write(f"\n## {i}. {r['stratum']} | {r['pub_date']} | {r['source_type']} | {r['source_name']}\n"
                        f"<{r['url']}>\n\n> {text.get(r['id'], '')}\n")
        print(f"\nwrote {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=20)
    ap.add_argument("--examples", type=int, default=0)
    a = ap.parse_args()
    main(a.rows, a.examples)
