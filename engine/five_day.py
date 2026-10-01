"""Option B's five-day readiness ratio and the collateral it calls for (session M1.7).

Contract 2c: (reserves + post-margin prepositioned capacity) / five-day runnable
outflows >= 100%, where runnable outflows = 40% of uninsured deposits + 100% of
short-term wholesale funding (Decision 2-2).

Under B and E a bank prepositions the least collateral that passes, cheapest
first (contract 2c; order in Clarification 11 item 3). Under B, if all its
collateral is not enough, it holds extra reserves (Clarification 11 item 2).

All banks at once: every quantity is an array with one entry per bank.
"""

import numpy as np

from engine.collateral import (add_loans, fed_loans, fill_in_order, move_to_fed, pool_caps,
                               prepositioned_capacity)

# Safety margin for "the ratio passes", not a model parameter: $1, in $ billions.
ONE_DOLLAR_BN = 1e-9


def runnable_outflows(banks, cfg):
    """Five-day stressed runnable outflows (Decision 2-2)."""
    r = cfg["five_day_ratio"]
    return r["runoff_uninsured"] * banks["uninsured_deposits_bn"] + r["runoff_stwf"] * banks["stwf_bn"]


def five_day_ratio(banks, place, cfg, margins):
    """The ratio itself, for any policy (it is reported under all of them)."""
    return (banks["reserves_bn"] + prepositioned_capacity(place, margins)) / runnable_outflows(banks, cfg)


def preposition_least_to_pass(banks, place, cfg, margins):
    """Move just enough collateral to the Fed for the ratio to reach its minimum.

    Returns the new placement and the shortfall: lendable value still missing once
    every eligible pool is at the Fed (zero for a bank that passes with collateral).
    """
    order = cfg["prepositioning"]["order"]
    need = (cfg["five_day_ratio"]["minimum"] * runnable_outflows(banks, cfg)
            - banks["reserves_bn"] - prepositioned_capacity(place, margins))
    caps = pool_caps(banks, place, margins, order)
    taken = fill_in_order(need, caps)
    shortfall = np.maximum(need - taken.sum(axis=1), 0.0)
    return move_to_fed(banks, place, taken, margins, order), shortfall


def hold_extra_reserves(banks, place, shortfall):
    """Close a shortfall by holding extra reserves, funded by running off loans (Clarification 11 item 2).

    First loans that are not eligible as collateral: each $1 run off adds $1 of reserves.
    Then, only if those run out, loans already at the Fed: each $1 adds $1 of reserves
    but removes its lendable value, so it nets (1 - lendable per loan). A shortfall
    exists only once every eligible loan is at the Fed, so these come from the Fed pool.
    Total assets do not change. Returns new banks, new placement, the extra reserves and any
    gap that remains once every loan is reserves (lendable value, $bn).
    """
    b = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in banks.items()}
    p = {k: v.copy() for k, v in place.items()}
    ineligible = b["loans_bn"] - b["eligible_loans_bn"]
    from_ineligible = np.minimum(shortfall, ineligible)
    # A bank that would need more loans than it has at the Fed converts them all and
    # still falls short; that gap is reported (`unmet`), never hidden.
    wanted_from_fed = (shortfall - from_ineligible) / (1 - p["lendable_per_loan"])
    from_fed = np.minimum(wanted_from_fed, fed_loans(p))
    unmet = (wanted_from_fed - from_fed) * (1 - p["lendable_per_loan"])
    extra = from_ineligible + from_fed
    add_loans(b, -extra, -from_fed)
    b["reserves_bn"] = b["reserves_bn"] + extra
    p["fed_loans_converted_bn"] += from_fed
    return b, p, extra, unmet

