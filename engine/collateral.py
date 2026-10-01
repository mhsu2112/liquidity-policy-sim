"""Where each bank's collateral sits, and what it is worth at the window (sessions M1.7, M1.7b).

Starting point is the status quo (Clarification 4): eligible loans 30% at the Fed,
40% pledged to the Home Loan Bank, 30% unpledged; no securities at the Fed.
Policies then move collateral to the Fed in a stated order (Clarifications 11, 12).

Loans are tracked by type (residential, CRE, C&I) in each place, because B'
moves C&I first (Amendment 3). B, E and C move loans at the bank's own mix.

Two values matter for every pool:
- face value: the loans or securities themselves (securities at market value);
- lendable value: what the Fed would lend against them, after its margin (contract 2b).

All banks at once: every quantity is an array with one entry per bank.
"""

import numpy as np

LOAN_TYPES = ("resi", "cre", "ci")
SECURITY_CLASSES = ("level1", "level2a")
LOAN_SOURCES = ("unpledged", "fhlb")   # where extra loans for the Fed come from (Clarification 4)


def lendable_per_loan(banks, margins):
    """Fed lendable value per $1 of the bank's eligible loans, at its own loan mix."""
    return sum(margins[t] * banks[f"{t}_loans_bn"] / banks["loans_bn"] for t in LOAN_TYPES)


def securities_mv(banks, c):
    """Market value of class c securities: book less the bank's pro-rata unrealized loss (Clarification 3)."""
    loss_rate = banks["unrealized_loss_bn"] / banks["securities_bn"]
    return banks[f"{c}_securities_bn"] * (1 - loss_rate)


def start_placement(banks, fs):
    """Collateral placement under the status quo (Clarification 4), in face value ($bn).

    Each pool holds the bank's own loan mix (Clarification 5 item 8).
    """
    place, margins = fs["collateral_placement"], fs["discount_window"]["margins"]
    eligible = banks["eligible_loans_bn"]
    zero = np.zeros_like(eligible)
    p = {"lendable_per_loan": lendable_per_loan(banks, margins),
         "loan_margins": {t: margins[t] for t in LOAN_TYPES},
         "fed_level1_mv_bn": zero.copy(), "fed_level2a_mv_bn": zero.copy()}
    for t in LOAN_TYPES:
        eligible_t = eligible * banks[f"{t}_loans_bn"] / banks["loans_bn"]
        p[f"fed_{t}_baseline_bn"] = place["fed_prepositioned"] * eligible_t   # already at the Fed under A
        p[f"unpledged_{t}_bn"] = place["unpledged"] * eligible_t
        p[f"fhlb_{t}_bn"] = place["fhlb_pledged"] * eligible_t
        for k in ("from_unpledged", "from_fhlb", "converted"):   # converted: B / B' only, turned into reserves
            p[f"fed_{t}_{k}_bn"] = zero.copy()
    return p


def total(place, pattern):
    """Sum a per-type line over the three loan types, e.g. total(p, "unpledged_{}_bn")."""
    return sum(place[pattern.format(t)] for t in LOAN_TYPES)


def fed_loans_of_type(place, t):
    return (place[f"fed_{t}_baseline_bn"] + place[f"fed_{t}_from_unpledged_bn"]
            + place[f"fed_{t}_from_fhlb_bn"] - place[f"fed_{t}_converted_bn"])


def fed_loans(place):
    """All eligible loans now at the Fed (face value)."""
    return sum(fed_loans_of_type(place, t) for t in LOAN_TYPES)


def loan_capacity(place):
    """Lendable value of loans at the Fed: the only collateral that can earn C's credit (contract 2d)."""
    return sum(fed_loans_of_type(place, t) * place["loan_margins"][t] for t in LOAN_TYPES)


def unpledged_capacity(place):
    """Lendable value of eligible loans pledged nowhere (usable at the window only from day 11)."""
    return sum(place[f"unpledged_{t}_bn"] * place["loan_margins"][t] for t in LOAN_TYPES)


def securities_capacity(place, margins):
    """Lendable value of securities at the Fed. They stay HQLA, so they never earn C's credit."""
    return sum(place[f"fed_{c}_mv_bn"] * margins[c] for c in SECURITY_CLASSES)


def prepositioned_capacity(place, margins):
    return loan_capacity(place) + securities_capacity(place, margins)


def loan_pool(pool):
    """A loan pool name -> (source, loan types). "unpledged_loans" is every type at the bank's
    mix; "fhlb_ci" is C&I only; "unpledged_resi_cre" is residential and CRE together."""
    source, rest = pool.split("_", 1)
    return source, (LOAN_TYPES if rest == "loans" else tuple(rest.split("_")))


def pool_caps(banks, place, margins, order):
    """Lendable value each pool could still add, one column per pool, in the order given."""
    cols = []
    for pool in order:
        if pool in SECURITY_CLASSES:
            cols.append((securities_mv(banks, pool) - place[f"fed_{pool}_mv_bn"]) * margins[pool])
        else:
            source, types = loan_pool(pool)
            cols.append(sum(place[f"{source}_{t}_bn"] * place["loan_margins"][t] for t in types))
    return np.column_stack(cols)


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
    """Move the taken lendable value to the Fed, pool by pool; returns a new placement.

    From a loan pool holding several types, the same share of each type's holding moves
    (pro rata to holdings), so a pool at the bank's mix stays at the bank's mix.
    """
    p = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in place.items()}
    caps = pool_caps(banks, place, margins, order)
    for j, pool in enumerate(order):
        lendable = taken[:, j]
        if pool in SECURITY_CLASSES:
            p[f"fed_{pool}_mv_bn"] += lendable / margins[pool]
            continue
        source, types = loan_pool(pool)
        share = np.divide(lendable, caps[:, j], out=np.zeros_like(lendable), where=caps[:, j] > 0)
        for t in types:
            face = share * place[f"{source}_{t}_bn"]
            p[f"{source}_{t}_bn"] -= face   # Home Loan Bank capacity falls one for one (Clarification 4)
            p[f"fed_{t}_from_{source}_bn"] += face
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
