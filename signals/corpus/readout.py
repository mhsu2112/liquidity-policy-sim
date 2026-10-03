"""Plain-English readout of the corpus (session M2.2; Clarification 20).

Prints: the eligibility review by source type (eligible share, reasons, doubtful calls, agreement
with the written rules); counts by period and source type, with types above 25% of a period noted
(the cap applies in the M2.3 draw); any period under 150; and random rows.
Excerpt text is read from the git-ignored private file, so it is shown on this computer only.
`--examples N` also writes N random rows, spread across periods and types, to the git-ignored
signals/corpus/trial_examples.md.

Run: python -m signals.corpus.readout [--rows 20] [--examples 30]   (or: make corpus-sample)
"""

import argparse
import csv
import random
import textwrap
from collections import Counter, defaultdict

from signals.corpus.build_corpus import CORPUS_PATH, DROPS_PATH, PRIVATE_PATH
from signals.corpus.candidates import SOURCE_TYPES
from signals.corpus.extract import WORK_DIR
from signals.corpus.passages import load_settings

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
    """Review results by source type: eligible share, reason codes, doubtful calls, and agreement with the rules."""
    from signals.corpus.review import raw_passages, reviews
    rows, done = raw_passages(), reviews()
    reviewed = [(rows[i], d) for i, d in done.items() if i in rows]
    print(f"\nEligibility review (Clarification 21): {len(reviewed)} of {len(rows)} in-scope passages reviewed")
    by_type = defaultdict(list)
    for r, d in reviewed:
        by_type[r["source_type"]].append(d)
    for t in SOURCE_TYPES:
        ds = by_type.get(t, [])
        if ds:
            keep = sum(d["decision"] == "keep" for d in ds)
            reasons = ", ".join(f"{k} {v}" for k, v in Counter(d["reason"] for d in ds).most_common())
            print(f"  {t:<19} {keep:>4} of {len(ds):>4} eligible ({keep / len(ds):5.1%})   {reasons}")
    if reviewed:
        keep = sum(d["decision"] == "keep" for _, d in reviewed)
        doubtful = sum(d["doubtful"] == "Y" for _, d in reviewed)
        agree = sum(r["rule_verdict"].split(":")[0] == d["decision"] for r, d in reviewed)
        print(f"  {'all':<19} {keep:>4} of {len(reviewed):>4} eligible ({keep / len(reviewed):5.1%}); "
              f"doubtful calls {doubtful}")
        print(f"  The written rules alone would have agreed with the review on {agree} of {len(reviewed)} "
              f"({agree / len(reviewed):.0%})")
    cut = [r for p in sorted(WORK_DIR.glob("cut_drops_*.csv")) for r in _read(p)]
    print("  Dropped while cutting (before review): " + ", ".join(f"{k} {v}" for k, v in Counter(r["reason"] for r in cut).most_common()))
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
    counts = Counter((r["stratum"], r["source_type"]) for r in rows)
    _table("In the corpus:", counts, strata, settings["targets"]["min_per_stratum"])
    share = settings["caps"]["max_type_share_per_stratum"]
    for st in strata:
        n = sum(counts.get((st, t), 0) for t in SOURCE_TYPES)
        over = [f"{t} {counts[(st, t)] / n:.0%}" for t in SOURCE_TYPES if n and counts.get((st, t), 0) / n > share]
        if over:
            print(f"  {st}: above {share:.0%} of the period (capped in the M2.3 draw, not here): " + ", ".join(over))

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
