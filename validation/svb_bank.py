"""The SVB validation bank (session M1.10; Clarification 15 item 3).

Built from SVB Financial Group's December 31, 2022 balance sheet, in the same
format as the 40 synthetic banks (engine/banks.py), so the same engine runs it.
It is used only for tuning (M1.10) and validation (M1.11), never in the sample.

`build_svb(rows)` returns `rows` identical copies (one per run), as arrays.
"""

from pathlib import Path

import numpy as np
import yaml

from engine.balance_sheet import check_balances

SVB_PATH = Path(__file__).resolve().parent.parent / "config" / "validation" / "svb.yaml"


def load_svb(path=SVB_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


def svb_balance_sheet(c):
    """One bank as a dict of plain numbers ($bn), every line the engine reads."""
    securities = c["afs_securities_bn"] + c["htm_securities_bn"]
    loans = c["loans_bn"]
    other_assets = c["total_assets_bn"] - c["reserves_bn"] - securities - loans
    uninsured = c["uninsured_share_of_deposits"] * c["deposits_bn"]
    other_liab = c["total_assets_bn"] - c["deposits_bn"] - c["fhlb_advances_bn"] - c["equity_bn"]
    level1 = c["level1_share_of_securities"] * securities
    b = {
        "total_assets_bn": c["total_assets_bn"], "reserves_bn": c["reserves_bn"],
        "securities_bn": securities, "level1_securities_bn": level1, "level2a_securities_bn": securities - level1,
        "loans_bn": loans, **{f"{t}_loans_bn": c["loan_mix"][t] * loans for t in ("resi", "cre", "ci")},
        "other_assets_bn": other_assets, "unrealized_loss_bn": c["htm_unrealized_loss_bn"],
        "eligible_loans_bn": c["eligible_share_of_loans"] * loans,
        "insured_deposits_bn": c["deposits_bn"] - uninsured, "uninsured_deposits_bn": uninsured,
        "stwf_bn": 0.0,   # short-term borrowings are held as Home Loan Bank advances (owner's choice)
        "fhlb_advances_bn": c["fhlb_advances_bn"], "other_liabilities_bn": other_liab, "equity_bn": c["equity_bn"],
        "lcr_calibration": c["lcr_calibration"],
        # Shares as the 40-bank files carry them (information only).
        "securities_share_of_assets": securities / c["total_assets_bn"],
        "reserves_share_of_assets": c["reserves_bn"] / c["total_assets_bn"],
        "loans_share_of_assets": loans / c["total_assets_bn"],
        "level1_share_of_securities": c["level1_share_of_securities"],
        "unrealized_loss_share_of_securities": c["htm_unrealized_loss_bn"] / securities,
        "eligible_share_of_loans": c["eligible_share_of_loans"],
        "equity_share_of_assets": c["equity_bn"] / c["total_assets_bn"],
        "stwf_share_of_liabilities": 0.0,
        "uninsured_share_of_deposits": c["uninsured_share_of_deposits"],
    }
    return b


def build_svb(rows=1, path=SVB_PATH):
    c = load_svb(path)
    one = svb_balance_sheet(c)
    banks = {k: np.full(rows, float(v)) for k, v in one.items()}
    banks["bank_id"] = np.full(rows, c["bank_id"])
    banks["archetype"] = np.full(rows, c["archetype"])
    banks["lcr_category"] = np.full(rows, c["lcr_category"])
    check_balances(banks)
    return banks, c
