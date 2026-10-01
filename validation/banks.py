"""Signature-like and First Republic-like validation banks (session M1.11; Clarification 16).

Built from the archetype midpoints (contract 1b), sized to the stated totals. Same
format as the 40 synthetic banks, so the same engine runs them. Used only for
validation, never in the sample. Choices Clarification 16 leaves open are in
config/validation/checks.yaml and the validation report.
"""

import numpy as np

from engine.balance_sheet import check_balances
from engine.banks import load_settings
from engine.collateral import LOAN_TYPES


def midpoint_bank(bank_id, archetype, total_assets, uninsured_share, rows):
    """One bank at its archetype's range midpoints, `rows` identical copies."""
    a = load_settings()["archetypes"][archetype]
    mid = lambda k: sum(a[k]) / 2   # noqa: E731
    ta = total_assets
    securities, reserves, loans = (mid(k) * ta for k in ("securities_share_of_assets", "reserves_share_of_assets",
                                                         "loans_share_of_assets"))
    level1 = mid("level1_share_of_securities") * securities
    equity = mid("equity_share_of_assets") * ta
    stwf = mid("stwf_share_of_liabilities") * (ta - equity)
    deposits = ta - equity - stwf
    uninsured = uninsured_share * deposits
    one = {"total_assets_bn": ta, "reserves_bn": reserves, "securities_bn": securities,
           "level1_securities_bn": level1, "level2a_securities_bn": securities - level1, "loans_bn": loans,
           **{f"{t}_loans_bn": a["loan_mix"][t] * loans for t in LOAN_TYPES},
           "other_assets_bn": ta - reserves - securities - loans,
           "unrealized_loss_bn": mid("unrealized_loss_share_of_securities") * securities,
           "eligible_loans_bn": mid("eligible_share_of_loans") * loans,
           "insured_deposits_bn": deposits - uninsured, "uninsured_deposits_bn": uninsured, "stwf_bn": stwf,
           "equity_bn": equity,
           "lcr_calibration": np.nan if a["lcr_calibration"] is None else a["lcr_calibration"]}
    banks = {k: np.full(rows, float(v)) for k, v in one.items()}
    banks.update(bank_id=np.full(rows, bank_id), archetype=np.full(rows, archetype),
                 lcr_category=np.full(rows, str(a["lcr_category"])))
    check_balances(banks)
    return banks


def remove_from_window(place, banks, capital_call_bn):
    """Signature: take capital-call (C&I) and all CRE loans out of the window pools (Clarification 16 item 1).

    The same share of each pool is removed, so prepositioned and unpledged pools both lose them;
    Home Loan Bank pledges are unchanged. Returns a new placement.
    """
    p = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in place.items()}
    ci_usable = np.maximum(banks["ci_loans_bn"] - capital_call_bn, 0) / banks["ci_loans_bn"]
    for pool in ("fed_{}_baseline_bn", "unpledged_{}_bn"):
        p[pool.format("cre")] = p[pool.format("cre")] * 0.0
        p[pool.format("ci")] = p[pool.format("ci")] * ci_usable
    return p
