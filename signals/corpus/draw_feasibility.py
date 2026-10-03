"""Can the gold-set draw be filled under Clarification 22's caps? (session M2.2; the draw itself is M2.3)

The draw takes 75 passages per period, 300 in all (Clarification 19), from passages flagged
gold_set_eligible. Caps (Clarification 22): no source type above 25% of the 300 overall, and no
type above 25% of a period's 75 where that period's supply allows; where it does not, that period
is drawn as evenly as possible and this is reported.

The check is a maximum-flow count: periods feed (period, type) cells, which feed types, with each
link limited by its cap. The largest flow is the most passages any draw could take under the caps.
This counts what is possible; it does not draw anything.
"""

import math

import networkx as nx


def per_period_cap_holds(counts, quota, share):
    """True if the period alone can fill its quota with no type above `share` of it."""
    cap = math.floor(share * quota)
    return sum(min(c, cap) for c in counts.values()) >= quota


def feasibility(pool, strata, quota, share):
    """pool: {(stratum, type): available passages}. Returns a plain-English summary dict."""
    types = sorted({t for _, t in pool})
    g = nx.DiGraph()
    relaxed = []
    for s in strata:
        counts = {t: pool.get((s, t), 0) for t in types}
        holds = per_period_cap_holds(counts, quota, share)
        if not holds:
            relaxed.append(s)
        g.add_edge("start", s, capacity=quota)
        for t in types:
            cell_cap = min(counts[t], math.floor(share * quota)) if holds else counts[t]
            g.add_edge(s, (s, t), capacity=cell_cap)
            g.add_edge((s, t), t, capacity=cell_cap)
    total = quota * len(strata)
    for t in types:
        g.add_edge(t, "end", capacity=math.floor(share * total))   # overall cap per type
    filled, flow = nx.maximum_flow(g, "start", "end")
    per_period = {s: sum(flow[s].values()) for s in strata}
    return {"target": total, "fillable": filled, "per_period": per_period, "relaxed_periods": relaxed,
            "can_fill": filled == total}
