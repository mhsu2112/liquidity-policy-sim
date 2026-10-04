"""Draw the gold set and the practice set (session M2.3; Clarification 24, followed step by step).

Reads the corpus (tag corpus-v1) and the git-ignored excerpts. Writes:
  key.csv            git-ignored until publish-labels: gold ID -> corpus passage, source, date, period, type
  draw_summary.csv   public: how many passages each period and source type contributes, per round

Every random choice uses one random.Random(20260923), in the order Clarification 24 lists, so the
draw is the same every time it is run on the same corpus. Nothing here looks at what a passage
says: only its period, source type and document.

Run: python -m signals.gold_set.draw   (or: make gold-draw)
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

from signals.corpus.build_corpus import CORPUS_PATH
from signals.corpus.passages import load_settings

HERE = Path(__file__).resolve().parent
KEY_PATH = HERE / "key.csv"
SUMMARY_PATH = HERE / "draw_summary.csv"
SEED = 20260923            # Clarification 19 / 24
TYPE_CAP = 75              # Clarification 24: 25% of 300, per source type, over the whole draw
PER_PERIOD = 75            # Clarification 19
PRACTICE = 15              # Clarification 19
KEY_FIELDS = ["gold_id", "round", "corpus_id", "document_id", "url", "source_name", "source_type", "pub_date", "stratum"]


def fillable(quota_left, supply_left, cap_left, strata, types):
    """How many more documents can be placed: a maximum flow from periods, through (period, type)
    cells limited by their documents, to types limited by their remaining cap."""
    g = nx.DiGraph()
    for p in strata:
        g.add_edge("start", p, capacity=quota_left[p])
        for t in types:
            g.add_edge(p, (p, t), capacity=supply_left[(p, t)])
            g.add_edge((p, t), t, capacity=supply_left[(p, t)])
    for t in types:
        g.add_edge(t, "end", capacity=cap_left[t])
    return nx.maximum_flow_value(g, "start", "end")


def draw(rows, strata, rng):
    """Steps 1-6 of Clarification 24. rows: draw-eligible corpus rows. Returns (main, practice) lists of rows."""
    # Step 1: one passage per document
    by_doc = defaultdict(list)
    for r in rows:
        by_doc[r["document_id"]].append(r)
    docs = {d: rng.choice(sorted(by_doc[d], key=lambda r: r["id"])) for d in sorted(by_doc)}
    types = sorted({r["source_type"] for r in docs.values()})
    cells = defaultdict(list)                       # (period, type) -> documents, sorted
    for d, r in docs.items():
        cells[(r["stratum"], r["source_type"])].append(d)
    supply = {(p, t): len(cells[(p, t)]) for p in strata for t in types}

    # Step 2: period quotas
    first, others = strata[0], strata[1:]
    quota = {first: sum(supply[(first, t)] for t in types), **{p: PER_PERIOD for p in others}}
    caps = {t: TYPE_CAP for t in types}
    order = list(others)
    rng.shuffle(order)
    flow, i = fillable(quota, supply, caps, strata, types), 0
    while flow < sum(quota.values()):
        p = order[i % len(order)]
        i += 1
        if quota[p] == 0:
            continue
        quota[p] -= 1
        new = fillable(quota, supply, caps, strata, types)
        if new < flow:          # removing here would lose a placeable document: undo, try the next period
            quota[p] += 1
        else:
            flow = new
        if i > 10 * sum(quota.values()) + 100:
            raise RuntimeError("could not settle period quotas")

    # Step 3: spread within periods, one document at a time, periods in turn
    type_order = list(types)
    rng.shuffle(type_order)
    alloc = {(p, t): 0 for p in strata for t in types}
    total = Counter()
    left = dict(supply)

    def remaining_ok():
        q = {p: quota[p] - sum(alloc[(p, t)] for t in types) for p in strata}
        c = {t: TYPE_CAP - total[t] for t in types}
        return fillable(q, left, c, strata, types) == sum(q.values())

    while any(sum(alloc[(p, t)] for t in types) < quota[p] for p in strata):
        for p in strata:
            if sum(alloc[(p, t)] for t in types) >= quota[p]:
                continue
            options = sorted((t for t in types if left[(p, t)] > 0 and total[t] < TYPE_CAP),
                             key=lambda t: (alloc[(p, t)], total[t], type_order.index(t)))
            for t in options:
                alloc[(p, t)] += 1; total[t] += 1; left[(p, t)] -= 1
                if remaining_ok():
                    break
                alloc[(p, t)] -= 1; total[t] -= 1; left[(p, t)] += 1
            else:
                raise RuntimeError(f"no feasible type for {p}")

    # Step 4: documents within each cell
    chosen = []
    for p in strata:
        for t in types:
            if alloc[(p, t)]:
                chosen += rng.sample(sorted(cells[(p, t)]), alloc[(p, t)])

    # Step 5: practice, one document at a time, periods in turn
    rest = {p: sorted(d for t in types for d in cells[(p, t)] if d not in set(chosen)) for p in strata}
    practice = []
    while len(practice) < PRACTICE and any(rest.values()):
        for p in strata:
            if rest[p] and len(practice) < PRACTICE:
                d = rng.choice(rest[p])
                rest[p].remove(d)
                practice.append(d)

    # Step 6: order
    main = sorted(chosen)
    rng.shuffle(main)
    practice = sorted(practice)
    rng.shuffle(practice)
    return [docs[d] for d in main], [docs[d] for d in practice]


def run(settings=None):
    settings = settings or load_settings()
    strata = list(settings["strata"])
    with open(CORPUS_PATH, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["gold_set_eligible"] == "Y"]
    import random
    main, practice = draw(rows, strata, random.Random(SEED))
    key = ([{**r, "gold_id": f"G{i:03d}", "round": "main", "corpus_id": r["id"]} for i, r in enumerate(main, 1)]
           + [{**r, "gold_id": f"PR{i:02d}", "round": "practice", "corpus_id": r["id"]} for i, r in enumerate(practice, 1)])
    with open(KEY_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KEY_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(key)
    counts = Counter((k["round"], k["stratum"], k["source_type"]) for k in key)
    with open(SUMMARY_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["round", "stratum", "source_type", "count"])
        w.writerows([*k, n] for k, n in sorted(counts.items()))
    print(f"main {len(main)}, practice {len(practice)}; key -> {KEY_PATH.name} (private), summary -> {SUMMARY_PATH.name}")
    return main, practice


if __name__ == "__main__":
    run()
