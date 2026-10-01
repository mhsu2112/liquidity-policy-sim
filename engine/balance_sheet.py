"""Balance-sheet checks (session M1.2).

Two views of each bank's balance sheet must always add up:
- Book value: assets = deposits + wholesale funding + equity.
- Market value: the same, with securities marked down by their unrealized loss
  and equity marked down by the same amount (mark-to-market equity).
"""

import numpy as np

ASSET_LINES = ["reserves", "level1_securities", "level2a_securities",
               "resi_loans", "cre_loans", "ci_loans", "other_assets"]
LIABILITY_LINES = ["insured_deposits", "uninsured_deposits", "stwf"]

ONE_DOLLAR_BN = 1e-9  # tolerance: $1, written in $ billions


def total_assets(banks):
    return sum(banks[f"{k}_bn"] for k in ASSET_LINES)


def total_liabilities(banks):
    return sum(banks[f"{k}_bn"] for k in LIABILITY_LINES)


def mtm_equity(banks):
    """Book equity less unrealized losses on securities. For information only."""
    return banks["equity_bn"] - banks["unrealized_loss_bn"]


def check_balances(banks):
    """Raise an error naming the first bank whose balance sheet does not add up."""
    gap_book = total_assets(banks) - (total_liabilities(banks) + banks["equity_bn"])
    gap_total = total_assets(banks) - banks["total_assets_bn"]
    gap_market = ((total_assets(banks) - banks["unrealized_loss_bn"])
                  - (total_liabilities(banks) + mtm_equity(banks)))
    for name, gap in [("book", gap_book), ("total assets", gap_total), ("market value", gap_market)]:
        bad = np.flatnonzero(np.abs(gap) >= ONE_DOLLAR_BN)
        if bad.size:
            raise ValueError(f"Balance sheet ({name}) does not balance for {banks['bank_id'][bad[0]]}")
