"""Balance-sheet checks (session M1.2).

Two views of each bank's balance sheet must always add up:
- Book value: assets = deposits + wholesale funding + equity.
- Market value: the same, with securities marked down by their unrealized loss
  and equity marked down by the same amount (mark-to-market equity).
"""

import numpy as np

ASSET_LINES = ["reserves", "level1_securities", "level2a_securities",
               "resi_loans", "cre_loans", "ci_loans", "other_assets",
               "sale_proceeds_due"]  # from M1.3: securities sold, cash not yet settled
LIABILITY_LINES = ["insured_deposits", "uninsured_deposits", "stwf",
                   "repo",                       # from M1.3b: same-day repo (Clarification 6)
                   "fhlb_advances", "dw_loans",  # from M1.3: borrowing
                   "unpaid_outflows",            # from M1.3: owed to depositors, not yet paid
                   "other_liabilities"]          # from M1.10: long-term debt and other stable liabilities
                                                 # (SVB validation bank; zero for the 40 banks)

ONE_DOLLAR_BN = 1e-9  # tolerance: $1, written in $ billions


def _line(banks, k):
    # Lines added in M1.3 don't exist before the first funding step; they count as zero.
    return banks.get(f"{k}_bn", 0.0)


def total_assets(banks):
    return sum(_line(banks, k) for k in ASSET_LINES)


def total_liabilities(banks):
    return sum(_line(banks, k) for k in LIABILITY_LINES)


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
