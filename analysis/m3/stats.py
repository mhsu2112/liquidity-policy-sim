"""The arithmetic of the v0.1 comparison (session v0.1-C), every rule as fixed in Clarification 31.

Small pure functions, tested by hand in tests/test_m3_stats.py. Nothing here runs the model or knows which
policy is which: a "difference" is always X minus Y for whichever two policies the caller passes.
"""

from itertools import combinations
from math import factorial, log

import numpy as np

FEATURES = ("prepositioning_mandate", "testing_mandate", "five_day_ratio", "lcr_credit")   # contract 2a


def paired_interval(diffs, z):
    """Mean of paired differences and its 90% interval (Clarification 31 B2: mean +/- z x standard error).

    `diffs` holds one number per unit (one bank x run pair). With fewer than two units there is no spread to
    measure, so the interval collapses to the mean.
    """
    d = np.asarray(diffs, float)
    mean = float(d.mean())
    if len(d) < 2:
        return mean, mean, mean
    se = float(d.std(ddof=1) / np.sqrt(len(d)))
    return mean, mean - z * se, mean + z * se


def label(surv, short):
    """Contract 4 as fixed in Clarification 31 B1. `surv` and `short` are (diff, lo, hi) for X minus Y.

    Survival: higher is better. Shortfall: lower is better. Cost never enters.
    """
    (ds, ls, hs), (df, lf, hf) = surv, short
    x_sig = (ls > 0, hf < 0)          # X significantly better on survival, on shortfall
    y_sig = (hs < 0, lf > 0)          # Y significantly better on survival, on shortfall
    if ds >= 0 and df <= 0 and any(x_sig):
        return "x_leads"
    if ds <= 0 and df >= 0 and any(y_sig):
        return "y_leads"
    if (x_sig[0] and y_sig[1]) or (y_sig[0] and x_sig[1]):
        return "trade_off"
    return "tie"


def reversal(labels, grid, marker):
    """Clarification 31 A: the label at the grid point nearest the marker, and how far stigma must move down or
    up from the marker before the label changes. `labels` lists one label per grid point, in grid order.

    Returns (label_at_marker, down_distance, down_label, up_distance, up_label); a distance is None if the label
    never changes on that side of the grid.
    """
    grid = list(grid)
    at = min(range(len(grid)), key=lambda i: (abs(grid[i] - marker), grid[i]))
    here = labels[at]
    down = next(((marker - grid[i], labels[i]) for i in range(len(grid) - 1, -1, -1)
                 if grid[i] < marker and labels[i] != here), (None, None))
    up = next(((grid[i] - marker, labels[i]) for i in range(len(grid))
               if grid[i] > marker and labels[i] != here), (None, None))
    return here, down[0], down[1], up[0], up[1]


def implied_s(marker_p, marker_a, r_p, r_a):
    """Clarification 31 A2: s = -ln(marker_P / marker_A) / (r_P - r_A). None when r_P = r_A (undefined)."""
    if r_p == r_a:
        return None
    return -log(marker_p / marker_a) / (r_p - r_a)


def effective_setup(on):
    """Contract 2a / Clarification 14 item 5: the five-day ratio always prepositions, so ratio-on means
    prepositioning-on. `on` is a set of switch names; returns the 4-tuple of what is actually built."""
    return ("prepositioning_mandate" in on or "five_day_ratio" in on, "testing_mandate" in on,
            "five_day_ratio" in on, "lcr_credit" in on)


def shapley_weights():
    """Clarification 31 B6. For each switch, {coalition (frozenset): weight} so that its Shapley contribution is
    sum(weight x outcome(coalition)) over the 16 switch combinations. Weights for one switch sum to zero."""
    n = len(FEATURES)
    out = {}
    for f in FEATURES:
        others = [g for g in FEATURES if g != f]
        w = {}
        for k in range(n):
            share = factorial(k) * factorial(n - k - 1) / factorial(n)
            for s in combinations(others, k):
                w[frozenset(s) | {f}] = w.get(frozenset(s) | {f}, 0.0) + share
                w[frozenset(s)] = w.get(frozenset(s), 0.0) - share
        out[f] = w
    return out


def combination_rate(setup, info, uptake):
    """Clarification 31 B6: routine draws per quarter for an unnamed switch combination.

    1.0 for quarterly tests if the testing mandate is on, plus uptake x 2.5 usage draws if LCR credit is on;
    the voluntary rate (A's 0.1) if neither.
    """
    _, test, _, credit = setup
    rb = info["routine_borrowing"]
    r = (rb["rate_by_policy"]["B"] if test else 0.0) + (uptake * rb["c_usage_draws_per_quarter"] if credit else 0.0)
    return r if (test or credit) else rb["rate_by_policy"]["A"]
