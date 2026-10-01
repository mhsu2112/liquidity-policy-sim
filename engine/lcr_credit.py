"""Option C: LCR credit for discount window capacity (session M1.7).

Contract 2d, built exactly as written:
- Credit = the lowest of three limits:
    1. the ceiling x total net cash outflows (20%; 30% when the stress trigger fires);
    2. k x the average of the 1st, 3rd and 5th largest overnight draws over two quarters;
    3. post-margin capacity against loans at the Fed. Securities at the Fed already
       count as HQLA, so they earn nothing here.
- Only banks subject to the LCR can get credit, and only if they opt in (Clarification 11 item 4).
- Banks that opt in preposition enough loans to support the 30% ceiling, make five
  overnight draws every six months sized so the formula supports that credit, and
  release HQLA equal to a share of their credit into loans.
- Credit falls by any amount actually drawn in stress.

"Total net cash outflows" is the calibrated amount (x70% / x85% for reduced-LCR
banks), which is how 12 CFR 249 defines it for those banks (Clarification 11).

All banks at once: every quantity is an array with one entry per bank.
"""

import numpy as np

from engine.collateral import (SECURITY_CLASSES, add_loans, fill_in_order, loan_capacity, move_to_fed,
                               pool_caps)

ONE_DOLLAR_BN = 1e-9  # tolerance: $1, in $ billions


def draw_opt_in_u(seed, rows):
    """One uniform number per bank: does it opt in? Drawn up front, shared by C and C'.

    Its own random stream (the third child of the seed), so the streams already used
    for leaks, readings and testing (engine/information.py::draw_info_randoms) are unchanged.
    """
    return np.random.default_rng(np.random.SeedSequence(seed).spawn(3)[2]).random(rows)


def lcr_required(banks):
    """Banks subject to the LCR (contract 1c). Diversified regionals have none."""
    return ~np.isnan(banks["lcr_calibration"])


def opted_in(banks, opt_in_u, uptake):
    """Opt in if U < uptake: nested, so a bank in at 50% uptake is in at 75% and 100%."""
    return lcr_required(banks) & (np.asarray(opt_in_u) < uptake)


def preposition_for_credit(banks, place, net_outflows, opt_in, c, margins, order):
    """Banks that opt in move loans to the Fed until loan capacity supports the 30% ceiling.

    Loans only, in Clarification 4 order (unpledged, then Home Loan Bank); every eligible
    loan if that is not enough. Banks that don't opt in move nothing.
    """
    loan_order = [k for k in order if k.endswith("_loans")]
    need = np.where(opt_in, c["stress_ceiling"] * net_outflows - loan_capacity(place), 0.0)
    taken = fill_in_order(need, pool_caps(banks, place, margins, loan_order))
    return move_to_fed(banks, place, taken, margins, loan_order)


def target_credit(place, net_outflows, c):
    """The credit a bank prepares for: the 30% ceiling, or its loan capacity if lower."""
    return np.minimum(c["stress_ceiling"] * net_outflows, loan_capacity(place))


def usage_draws(target, opt_in, k, c):
    """The overnight draws each bank makes over two quarters, one column per draw.

    Five equal draws of target / k: then k x average(1st, 3rd, 5th) = target exactly.
    No usage multiple (C') or no opt-in means no draws.
    """
    size = np.where(opt_in, target / k, 0.0) if k is not None else np.zeros_like(target)
    return np.repeat(size[:, None], c["usage_draws_per_six_months"], axis=1)


def usage_limit(draws, k, c):
    """k x the average of the 1st, 3rd and 5th largest draws. No limit without a multiple."""
    if k is None:
        return np.full(draws.shape[0], np.inf)
    largest_first = -np.sort(-draws, axis=1)
    picks = largest_first[:, [rank - 1 for rank in c["usage_ranks"]]]
    return k * picks.mean(axis=1)


def credit_limits(place, net_outflows, draws, k, c, trigger_fires):
    """The three limits of contract 2d, each on its own."""
    ceiling = c["stress_ceiling"] if trigger_fires else c["ceiling"]
    return {"ceiling_limit_bn": ceiling * net_outflows,
            "usage_limit_bn": usage_limit(draws, k, c),
            "capacity_limit_bn": loan_capacity(place)}


def credit(limits, eligible):
    """The lowest limit, for banks that may claim credit; zero for everyone else."""
    lowest = np.minimum(np.minimum(limits["ceiling_limit_bn"], limits["usage_limit_bn"]),
                        limits["capacity_limit_bn"])
    return np.where(eligible, lowest, 0.0)


def credit_after_draws(credit_bn, drawn_bn):
    """Contract 2d: unused-capacity credit falls by the amount drawn, never below zero."""
    return np.maximum(np.asarray(credit_bn) - np.asarray(drawn_bn), 0.0)


def release_hqla(banks, amount, floor_bn, order):
    """Turn HQLA worth `amount` into loans (Clarification 11 item 1).

    Reserves first, down to the operating floor; then securities in the order given,
    sold at market value. A sale realizes the unrealized loss on what is sold
    (Clarification 5 item 2), which comes off equity; no fire-sale discount, because
    the release is a gradual steady-state choice. The cash goes into new loans at
    the bank's mix and eligible share, not prepositioned.
    Returns new banks and the amount released from each source.
    """
    b = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in banks.items()}
    loss_rate = b["unrealized_loss_bn"] / b["securities_bn"]
    eligible_share = b["eligible_loans_bn"] / b["loans_bn"]
    left = np.asarray(amount, float).copy()
    released = {}
    for source in order:
        if source == "reserves":
            take = np.minimum(left, np.maximum(b["reserves_bn"] - floor_bn, 0.0))
            b["reserves_bn"] = b["reserves_bn"] - take
        else:
            assert source in SECURITY_CLASSES
            take = np.minimum(left, b[f"{source}_securities_bn"] * (1 - loss_rate))
            book = take / (1 - loss_rate)
            loss = book - take
            b[f"{source}_securities_bn"] = b[f"{source}_securities_bn"] - book
            b["securities_bn"] = b["securities_bn"] - book
            b["unrealized_loss_bn"] = b["unrealized_loss_bn"] - loss   # now realized ...
            b["equity_bn"] = b["equity_bn"] - loss                      # ... and off equity
            b["total_assets_bn"] = b["total_assets_bn"] - loss
        released[source] = take
        left = left - take
    if np.any(left > ONE_DOLLAR_BN):
        raise ValueError("A bank has too little HQLA to release the amount its credit calls for.")
    add_loans(b, np.asarray(amount, float), eligible_share * amount)
    return b, released
