"""Where each bank's collateral sits, and what it is worth at the window (session M1.7).

Starting point is the status quo (Clarification 4): eligible loans 30% at the Fed,
40% pledged to the Home Loan Bank, 30% unpledged; no securities at the Fed.
Policies then move collateral to the Fed in a stated order (Clarification 11).

Two values matter for every pool:
- face value: the loans or securities themselves (securities at market value);
- lendable value: what the Fed would lend against them, after its margin (contract 2b).

All banks at once: every quantity is an array with one entry per bank.
"""

import numpy as np

from engine.funding import LOAN_TYPES, SECURITY_CLASSES


def lendable_per_loan(banks, margins):
    """Fed lendable value per $1 of the bank's eligible loans, at its own loan mix."""
    return sum(margins[t] * banks[f"{t}_loans_bn"] / banks["loans_bn"] for t in LOAN_TYPES)


def securities_mv(banks, c):
    """Market value of class c securities: book less the bank's pro-rata unrealized loss (Clarification 3)."""
    loss_rate = banks["unrealized_loss_bn"] / banks["securities_bn"]
    return banks[f"{c}_securities_bn"] * (1 - loss_rate)


def start_placement(banks, fs):
    """Collateral placement under the status quo (Clarification 4), in face value ($bn)."""
    place = fs["collateral_placement"]
    eligible = banks["eligible_loans_bn"]
    zero = np.zeros_like(eligible)
    return {
        "lendable_per_loan": lendable_per_loan(banks, fs["discount_window"]["margins"]),
        "fed_loans_baseline_bn": place["fed_prepositioned"] * eligible,  # already at the Fed under A
        "fed_loans_from_unpledged_bn": zero.copy(),
        "fed_loans_from_fhlb_bn": zero.copy(),
        "fed_loans_converted_bn": zero.copy(),   # B only: prepositioned loans turned into reserves
        "unpledged_loans_bn": place["unpledged"] * eligible,
        "fhlb_loans_bn": place["fhlb_pledged"] * eligible,
        "fed_level1_mv_bn": zero.copy(),
        "fed_level2a_mv_bn": zero.copy(),
    }


def fed_loans(place):
    """All eligible loans now at the Fed (face value)."""
    return (place["fed_loans_baseline_bn"] + place["fed_loans_from_unpledged_bn"]
            + place["fed_loans_from_fhlb_bn"] - place["fed_loans_converted_bn"])


def loan_capacity(place):
    """Lendable value of loans at the Fed: the only collateral that can earn C's credit (contract 2d)."""
    return fed_loans(place) * place["lendable_per_loan"]


def securities_capacity(place, margins):
    """Lendable value of securities at the Fed. They stay HQLA, so they never earn C's credit."""
    return sum(place[f"fed_{c}_mv_bn"] * margins[c] for c in SECURITY_CLASSES)


def prepositioned_capacity(place, margins):
    return loan_capacity(place) + securities_capacity(place, margins)


def pool_caps(banks, place, margins, order):
    """Lendable value each pool could still add, one column per pool, in the order given."""
    caps = {
        "level2a": (securities_mv(banks, "level2a") - place["fed_level2a_mv_bn"]) * margins["level2a"],
        "level1": (securities_mv(banks, "level1") - place["fed_level1_mv_bn"]) * margins["level1"],
        "unpledged_loans": place["unpledged_loans_bn"] * place["lendable_per_loan"],
        "fhlb_loans": place["fhlb_loans_bn"] * place["lendable_per_loan"],
    }
    return np.column_stack([caps[k] for k in order])


def fill_in_order(need, caps):
    """Take lendable value from each pool in turn until `need` is met.

    Returns one column per pool: how much lendable value is taken from it. A pool
    is used only once every earlier pool is full; the last pool used is partial.
    That is "the least that passes, cheapest first" (contract 2c).
    """
    need = np.maximum(np.asarray(need, float), 0.0)
    before = np.cumsum(caps, axis=1) - caps   # capacity of all earlier pools
    return np.clip(need[:, None] - before, 0.0, caps)


def move_to_fed(banks, place, taken, margins, order):
    """Move the taken lendable value to the Fed, pool by pool; returns a new placement."""
    p = {k: v.copy() for k, v in place.items()}
    for j, pool in enumerate(order):
        lendable = taken[:, j]
        if pool in SECURITY_CLASSES:
            p[f"fed_{pool}_mv_bn"] += lendable / margins[pool]
        else:
            face = lendable / p["lendable_per_loan"]
            source = "unpledged" if pool == "unpledged_loans" else "fhlb"
            p[f"{source}_loans_bn"] -= face   # Home Loan Bank capacity falls one for one (Clarification 4)
            p[f"fed_loans_from_{source}_bn"] += face
    return p


def add_loans(b, amount, eligible_amount):
    """Change a bank's loans by `amount` ($bn; negative = run off), at its own loan mix.

    `eligible_amount` is the part of the change that is eligible as collateral.
    Changes `b` in place. The mix is kept, so lendable value per loan is unchanged.
    """
    scale = 1 + amount / b["loans_bn"]
    for t in LOAN_TYPES:
        b[f"{t}_loans_bn"] = b[f"{t}_loans_bn"] * scale
    b["loans_bn"] = b["loans_bn"] + amount
    b["eligible_loans_bn"] = b["eligible_loans_bn"] + eligible_amount
