"""Option B's five-day readiness ratio and the collateral it calls for (sessions M1.7, M1.7b).

Contract 2c: (reserves + post-margin prepositioned capacity) / five-day runnable
outflows >= 100%, where runnable outflows = 40% of uninsured deposits + 100% of
short-term wholesale funding (Decision 2-2).

What counts as capacity is a setting (`counts`):
- "all"        every collateral at the Fed (registered B; E mirrors its collateral);
- "loans_only" only loans at the Fed (B', Amendment 3: securities already count as liquid assets).

A bank prepositions the least collateral that passes, cheapest first, in the order
its settings give (Clarifications 11 and 12). If all its collateral is not enough,
it holds extra reserves (Clarification 11 item 2). If even turning every loan into
reserves is not enough, it runs non-compliant and the gap left is reported (Amendment 3).

All banks at once: every quantity is an array with one entry per bank.
"""

import numpy as np

from engine.collateral import (LOAN_TYPES, add_loans, fed_loans, fed_loans_of_type, fill_in_order, loan_capacity,
                               move_to_fed, pool_caps, prepositioned_capacity)

ONE_DOLLAR_BN = 1e-9  # tolerance: $1, in $ billions


def runnable_outflows(banks, cfg):
    """Five-day stressed runnable outflows (Decision 2-2). `cfg` is the policy settings file."""
    r = cfg["five_day_ratio"]
    return r["runoff_uninsured"] * banks["uninsured_deposits_bn"] + r["runoff_stwf"] * banks["stwf_bn"]


def counted_capacity(place, margins, counts):
    """Collateral capacity the ratio counts: everything at the Fed, or loans only (B')."""
    return loan_capacity(place) if counts == "loans_only" else prepositioned_capacity(place, margins)


def five_day_ratio(banks, place, cfg, margins, counts="all"):
    """The ratio itself, for any policy (it is reported under all of them)."""
    return (banks["reserves_bn"] + counted_capacity(place, margins, counts)) / runnable_outflows(banks, cfg)


def preposition_least_to_pass(banks, place, cfg, margins, order, counts="all"):
    """Move just enough collateral to the Fed, in `order`, for the ratio to reach its minimum.

    Returns the new placement and the shortfall: lendable value still missing once
    every pool in `order` is at the Fed (zero for a bank that passes with collateral).
    """
    need = (cfg["five_day_ratio"]["minimum"] * runnable_outflows(banks, cfg)
            - banks["reserves_bn"] - counted_capacity(place, margins, counts))
    taken = fill_in_order(need, pool_caps(banks, place, margins, order))
    shortfall = np.maximum(need - taken.sum(axis=1), 0.0)
    return move_to_fed(banks, place, taken, margins, order), shortfall


def hold_extra_reserves(banks, place, shortfall):
    """Close a shortfall by holding extra reserves, funded by running off loans (Clarification 11 item 2).

    First loans that are not eligible as collateral: each $1 run off adds $1 of reserves.
    Then, only if those run out, loans already at the Fed: each $1 adds $1 of reserves
    but removes its lendable value, so it nets (1 - lendable per $1 at the Fed). A
    shortfall exists only once every eligible loan is at the Fed, so these come from the
    Fed pool, the same share of each loan type. Total assets do not change.

    A bank that would need more loans than it has at the Fed converts them all and
    still falls short: it runs non-compliant (Amendment 3 item 2), and that gap is
    reported, never hidden.
    Returns new banks, new placement, the extra reserves and the gap left (lendable value, $bn).
    """
    b = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in banks.items()}
    p = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in place.items()}
    at_fed = fed_loans(p)
    per_dollar = np.divide(loan_capacity(p), at_fed, out=np.zeros_like(at_fed), where=at_fed > 0)
    ineligible = b["loans_bn"] - b["eligible_loans_bn"]
    from_ineligible = np.minimum(shortfall, ineligible)
    wanted_from_fed = (shortfall - from_ineligible) / (1 - per_dollar)
    from_fed = np.minimum(wanted_from_fed, at_fed)
    unmet = (wanted_from_fed - from_fed) * (1 - per_dollar)
    share = np.divide(from_fed, at_fed, out=np.zeros_like(at_fed), where=at_fed > 0)
    for t in LOAN_TYPES:
        p[f"fed_{t}_converted_bn"] += share * fed_loans_of_type(place, t)
    extra = from_ineligible + from_fed
    add_loans(b, -extra, -from_fed)
    b["reserves_bn"] = b["reserves_bn"] + extra
    return b, p, extra, np.where(unmet > ONE_DOLLAR_BN, unmet, 0.0)
