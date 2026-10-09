"""Score H1–H8 exactly as docs/hypotheses.md registers them (session v0.1-C).

Where the registered text leaves room, Clarification 31 B7 (recorded before any stress run of B, B', C, C' or E)
says how; Clarifications 17 (item 3) and 18 (item 1) govern H8. Each verdict is "supported" unless the
hypothesis's "Shown wrong if" condition holds; "untestable" only when the test cannot be computed; H2 is
"reported". Nothing here weighs one result against another or adjusts anything to a result.
"""

import numpy as np

from analysis.m3.raw import OUTCOME, false_comfort
from analysis.m3.stats import paired_interval


def _labels(b, scen, x, y, cells, bank_type, sx=("-", "-")):
    """Lead labels for X vs Y in each cell, for one bank type; X may run at a sensitivity point."""
    r = b.raw.type_rows(bank_type)
    return [b.cell_label(scen, x, y, c, r, sx=sx)[0] for c in cells]


def _count(labels):
    return {k: labels.count(k) for k in ("x_leads", "y_leads", "tie", "trade_off")}


def h1(b):
    lab = _count(_labels(b, "S1", "B", "C", b.mid, "svb_like"))
    wrong = lab["x_leads"] >= 5 or lab["y_leads"] >= 5
    res = (f"SVB-like, S1, 9 mid-range cells: B leads in {lab['x_leads']}, C leads in {lab['y_leads']}, tie in "
           f"{lab['tie']}, trade-off in {lab['trade_off']}. Shown wrong if either leads in 5 or more.")
    return [{"part": "main", "result": res, "verdict": "not supported" if wrong else "supported"}], lab


def h2(b, attribution):
    parts, detail = [], {}
    for t in b.types:
        detail[t] = _count(_labels(b, "S1", "B", "E", b.main, t))
    att = {r[2]: r for r in attribution if r[0] == "five_day_ratio" and r[1] == "S1" and r[3] == "survival_rate"}
    tot = {t: sum(float(r[4]) for r in attribution if r[1] == "S1" and r[2] == t and r[3] == "survival_rate")
           for t in b.types}
    bits = "; ".join(f"{t}: B leads {d['x_leads']}, E leads {d['y_leads']}, tie {d['tie']}, trade-off {d['trade_off']}"
                     for t, d in detail.items())
    sh = "; ".join(f"{t}: {float(att[t][4]) * 100:+.1f} pp [{float(att[t][5]) * 100:+.1f}, {float(att[t][6]) * 100:+.1f}]"
                   f" of a {tot[t] * 100:+.1f} pp total effect of all four switches" for t in b.types)
    res = f"S1, B vs E in all 35 cells — {bits}. Five-day-ratio switch's Shapley contribution to survival (9 mid-range cells) — {sh}."
    parts.append({"part": "main", "result": res, "verdict": "reported"})
    return parts, {"b_vs_e": detail, "five_day_ratio_survival": {t: att[t][4:7] for t in b.types}}


def h3(b):
    labs = []
    for t in ("svb_like", "regional_cat3"):
        labs += _labels(b, "S1", "C", "A", b.main, t, sx=("c_uptake", "0.5"))
    lab = _count(labs)
    n = len(labs)
    main_wrong = lab["x_leads"] > n / 2
    strong = lab["y_leads"] >= n / 3
    res = (f"SVB-like and Category III regional, S1, uptake 50%, released 100%, {n} cells: C leads A in {lab['x_leads']}, "
           f"A leads C in {lab['y_leads']}, tie {lab['tie']}, trade-off {lab['trade_off']}.")
    return [{"part": "main", "result": res + " Shown wrong if C leads in a majority.",
             "verdict": "not supported" if main_wrong else "supported"},
            {"part": "strong_form", "result": res + f" Strong form holds if A leads in at least one-third ({n / 3:.1f}).",
             "verdict": "supported" if strong else "not supported"}], lab


def h4(b):
    a_cells = [c for c in b.main if c[0] in (0.0, 0.10)]
    c_cells = [c for c in b.main if c[1] in ("encourages", "strongly_encourages")]
    conds = {"a": (a_cells, ("-", "-"), "market stigma 0 or 0.10"),
             "b": (b.main, ("c_uptake", "1.0"), "uptake 100%"),
             "c": (c_cells, ("-", "-"), "supervisors encourage or strongly encourage")}
    parts, detail = [], {}
    for k, (cells, sens, what) in conds.items():
        r = b.raw.type_rows("svb_like")
        labs = [b.cell_label("S1", "B", "C", c, r, sy=sens)[0] for c in cells]
        lab = _count(labs)
        wrong = lab["x_leads"] > len(cells) / 2
        parts.append({"part": k, "result": (f"SVB-like, S1, {what}, {len(cells)} cells: B leads C in {lab['x_leads']}, C leads B "
                                            f"in {lab['y_leads']}, tie {lab['tie']}, trade-off {lab['trade_off']}. Shown wrong "
                                            f"if B leads in a majority."),
                      "verdict": "not supported" if wrong else "supported"})
        detail[k] = lab
    return parts, detail


def h5(b):
    fc = false_comfort(b.cfg)
    detail, ok = {}, True
    for t in ("svb_like", "gsib"):
        d = b.diff("S1", "C", "A", b.main, fc, b.raw.type_rows(t))
        lvl = {p: float(np.nanmean(b.raw.per_row("S1", p, b.main, fc, rows=b.raw.type_rows(t)))) for p in ("C", "A")}
        detail[t] = {"diff": d, "C": lvl["C"], "A": lvl["A"]}
        ok &= d[1] > 0
    res = "; ".join(f"{t}: false comfort C {v['C']:.1%} vs A {v['A']:.1%}, C − A {v['diff'][0] * 100:+.2f} pp "
                    f"[{v['diff'][1] * 100:+.2f}, {v['diff'][2] * 100:+.2f}]" for t, v in detail.items())
    res = f"S1, all 35 cells. {res}. Shown wrong if the interval includes zero or is negative in either archetype."
    return [{"part": "main", "result": res, "verdict": "supported" if ok else "not supported"}], detail


def h6(b):
    cost = b.costs()
    med = {p: float(np.median(cost[p])) for p in ("B", "E", "A", "C", "C_prime")}
    order = ["B", "E", "A", "C", "C_prime"]
    ok = all(med[order[i]] > med[order[i + 1]] for i in range(len(order) - 1))
    spread = {f"{x}-{y}": [float(np.min(cost[x] - cost[y])), float(np.median(cost[x] - cost[y])), float(np.max(cost[x] - cost[y]))]
              for x, y in zip(order, order[1:])}
    res = ("Median annual cost across the 40 banks ($m vs A): " + ", ".join(f"{p.replace('_prime', '′')} {med[p]:,.1f}" for p in order)
           + ". Pairwise differences across banks (min / median / max): "
           + "; ".join(f"{k.replace('_prime', '′')} {v[0]:,.1f} / {v[1]:,.1f} / {v[2]:,.1f}" for k, v in spread.items())
           + ". Expected strictly B > E > A > C > C′.")
    return [{"part": "main", "result": res, "verdict": "supported" if ok else "not supported"}], {"medians": med, "spread": spread}


def h7(b):
    pols = b.cfg["h7_policies"]
    stig = b.plan["cells"]["mid_range"]["stigma"]
    r = b.raw.type_rows("svb_like")

    def surv(p, x, u):
        return float(np.mean(b.raw.per_row("S1", p, [(x, u)], OUTCOME["survival_rate"], rows=r)))

    sup = float(np.mean([abs(surv(p, x, "strongly_encourages") - surv(p, x, "strongly_penalizes")) for p in pols for x in stig]))
    pol = float(np.mean([max(surv(p, x, "neutral") for p in pols) - min(surv(p, x, "neutral") for p in pols) for x in stig]))
    if pol == 0:
        return [{"part": "main", "result": f"Supervision swing {sup:.3f}; policy swing 0: the ratio is undefined.",
                 "verdict": "untestable"}], {"supervision_swing": sup, "policy_swing": pol}
    ratio = sup / pol
    res = (f"SVB-like, S1, mid-range stigma: supervision swing (dial end to end, policy fixed) {sup * 100:.1f} pp; policy swing "
           f"(across A, B, C, C′, E at neutral) {pol * 100:.1f} pp; ratio {ratio:.2f}. Shown wrong if below 0.5 or above 2.")
    return [{"part": "main", "result": res, "verdict": "supported" if 0.5 <= ratio <= 2 else "not supported"}], \
        {"supervision_swing": sup, "policy_swing": pol, "ratio": ratio}


def h8(b):
    c = b.cfg
    scored = [t for t in b.types
              if np.mean(b.raw.per_row("S2", "A", b.main, OUTCOME["survival_rate"], rows=b.raw.type_rows(t))) >= c["h8_min_a_survival"]]
    rows = np.flatnonzero(np.isin(b.raw.type_of_row, scored))
    banks = np.unique(b.raw.bank_of_row[rows])
    detail, verdicts = {"scored_archetypes": scored}, []
    for p in ("B", "E"):
        qual = {bk: [] for bk in banks}
        share = {"A": [], p: []}
        ties, n_pairs = 0, 0
        for x, u in b.main:
            ba, bp = b.raw.batch("S2", "A", x, u), b.raw.batch("S2", p, x, u)
            for bk in banks:
                m = b.raw.bank_of_row[ba["row"]] == bk
                sa, sp = float(np.mean(ba["support"][m] > 0)), float(np.mean(bp["support"][m] > 0))
                share["A"].append(sa)
                share[p].append(sp)
                if max(sa, sp) >= c["h8_min_borrow_share"]:
                    qual[bk].append((x, u))
                    ties += int(np.sum(ba["support"][m] == bp["support"][m]))
                    n_pairs += int(m.sum())
        n_q = sum(len(v) for v in qual.values())
        total = len(banks) * len(b.main)
        d = {"qualifying_bank_cells": n_q, "scored_bank_cells": total, "borrow_share_A": float(np.mean(share["A"])) if share["A"] else 0.0,
             f"borrow_share_{p}": float(np.mean(share[p])) if share[p] else 0.0,
             "exact_tie_share": ties / n_pairs if n_pairs else None}
        if total == 0 or n_q < c["h8_min_qualifying_share"] * total:
            d["test"] = "untestable: no measurable borrowing"
        else:
            units = []
            for bk, cells in qual.items():
                if cells:
                    rr = np.flatnonzero(b.raw.bank_of_row == bk)
                    units.append(b.raw.per_row("S2", p, cells, OUTCOME["support_bn"], rows=rr)
                                 - b.raw.per_row("S2", "A", cells, OUTCOME["support_bn"], rows=rr))
            d["test"] = paired_interval(np.concatenate(units), b.z)
        detail[p] = d
        verdicts.append(d["test"])
    testable = [v for v in verdicts if not isinstance(v, str)]
    if not testable:
        verdict = "untestable"
    else:
        verdict = "not supported" if any(v[1] > 0 or v[2] < 0 for v in testable) else "supported"

    def say(p):
        d = detail[p]
        t = d["test"] if isinstance(d["test"], str) else (f"needless borrowing {p} − A {d['test'][0]:+.3f} $bn "
                                                          f"[{d['test'][1]:+.3f}, {d['test'][2]:+.3f}]")
        tie = "n/a" if d["exact_tie_share"] is None else f"{d['exact_tie_share']:.1%}"
        return (f"{p} vs A: {d['qualifying_bank_cells']} of {d['scored_bank_cells']} bank × cells qualify; runs borrowing "
                f"A {d['borrow_share_A']:.1%}, {p} {d[f'borrow_share_{p}']:.1%}; exact ties {tie}; {t}")
    res = (f"S2, scored archetypes (A survives ≥ 90%): {', '.join(scored) or 'none'}. " + "; ".join(say(p) for p in ("B", "E"))
           + ". Shown wrong if either interval excludes zero.")
    return [{"part": "main", "result": res, "verdict": verdict}], detail


def score(b, attribution=None):
    if attribution is None:
        attribution = b.attribution()
    out, detail = [], {}
    for hid, fn in (("H1", h1), ("H2", lambda bb: h2(bb, attribution)), ("H3", h3), ("H4", h4), ("H5", h5),
                    ("H6", h6), ("H7", h7), ("H8", h8)):
        parts, d = fn(b)
        out.append({"id": hid, "parts": parts})
        detail[hid] = d
    return out, detail
