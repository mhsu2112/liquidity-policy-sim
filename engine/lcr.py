"""The liquidity coverage ratio under current rules (session M1.2).

Follows contract section 7 (HQLA haircuts and the 40% cap) and docs/amendments.md
Clarification 3 (outflow rates, no inflows), with encumbered securities and repo
outflows from Clarification 12. No policy credit of any kind is included here;
Option C's credit is added on top in engine/lcr_credit.py.

All 40 banks are calculated at once: every quantity is an array, one entry per bank.
"""

from pathlib import Path

import numpy as np
import yaml

from engine.balance_sheet import mtm_equity

LCR_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "lcr.yaml"


def load_lcr_settings(path=LCR_SETTINGS_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


def compute_lcr(banks, s=None):
    """Return each step of the LCR calculation as arrays, in $bn unless a ratio."""
    if s is None:
        s = load_lcr_settings()
    h, rates = s["hqla"], s["outflow_rates"]

    # 1. Mark securities to market. The unrealized loss is spread pro rata, so
    #    Level 1 and Level 2A holdings each lose the bank's same percentage.
    loss_rate = banks["unrealized_loss_bn"] / banks["securities_bn"]
    level1_mv = banks["level1_securities_bn"] * (1 - loss_rate)
    level2a_mv = banks["level2a_securities_bn"] * (1 - loss_rate)

    # 1b. Encumbered securities stop counting as HQLA: those pledged for repo
    #     (Clarification 6) and those the window has lent against (Clarification 12
    #     item 5). Zero for a bank that has done neither. Securities prepositioned at
    #     the Fed but not borrowed against stay HQLA (contract 2d).
    for enc in ("repo_pledged_mv", "dw_pledged_mv"):
        level1_mv = level1_mv - banks.get(f"{enc}_level1_bn", 0.0)
        level2a_mv = level2a_mv - banks.get(f"{enc}_level2a_bn", 0.0)

    # 2. Level 1 HQLA: reserves at the Fed plus Level 1 securities, no haircut.
    level1_hqla = (banks["reserves_bn"] + level1_mv) * (1 - h["level1_haircut"])

    # 3. Level 2A after the 15% haircut.
    level2a_after_haircut = level2a_mv * (1 - h["level2a_haircut"])

    # 4. The 40% cap. If Level 2A may be at most 40% of total HQLA, it may be at
    #    most 40/60 (= two-thirds) of Level 1. Anything above that is excluded.
    level2a_cap = level1_hqla * h["level2_cap"] / (1 - h["level2_cap"])
    level2a_counted = np.minimum(level2a_after_haircut, level2a_cap)

    # 5. Total HQLA.
    hqla = level1_hqla + level2a_counted

    # 6-7. Thirty-day outflows at the agreed run-off rates, less inflows
    #      (none are modeled; the 75% inflow cap is kept so the rule is complete).
    #      Repo and discount window loans outstanding are secured funding, at the rate for
    #      their collateral (Clarification 12 item 6; Amendment 4 for window loans against loans).
    outflows = (rates["insured_deposits"] * banks["insured_deposits_bn"]
                + rates["uninsured_deposits"] * banks["uninsured_deposits_bn"]
                + rates["stwf"] * banks["stwf_bn"]
                + rates["repo_level1"] * banks.get("repo_out_level1_bn", 0.0)
                + rates["repo_level2a"] * banks.get("repo_out_level2a_bn", 0.0)
                + rates["dw_level1"] * banks.get("dw_out_level1_bn", 0.0)
                + rates["dw_level2a"] * banks.get("dw_out_level2a_bn", 0.0)
                + rates["dw_loans"] * banks.get("dw_out_loans_bn", 0.0))
    inflows = s["inflows"]["loan_inflow_rate"] * banks["loans_bn"]
    net_outflows = outflows - np.minimum(inflows, s["inflows"]["cap_share_of_outflows"] * outflows)

    # 8. Reduced LCRs (85%, 70%) scale outflows down. Banks with no requirement
    #    get the ratio on unadjusted outflows and are marked "not required".
    required = ~np.isnan(banks["lcr_calibration"])
    factor = np.where(required, banks["lcr_calibration"], s["no_requirement_factor"])
    calibrated_outflows = net_outflows * factor

    # 9. The ratio itself.
    lcr = hqla / calibrated_outflows

    return {
        "level1_securities_mv_bn": level1_mv,
        "level2a_securities_mv_bn": level2a_mv,
        "level1_hqla_bn": level1_hqla,
        "level2a_after_haircut_bn": level2a_after_haircut,
        "level2a_cap_bn": level2a_cap,
        "level2a_counted_bn": level2a_counted,
        "level2a_excluded_by_cap_bn": level2a_after_haircut - level2a_counted,
        "hqla_bn": hqla,
        "gross_outflows_bn": outflows,
        "inflows_bn": inflows,
        "net_cash_outflows_bn": net_outflows,
        "outflow_factor": factor,
        "calibrated_outflows_bn": calibrated_outflows,
        "lcr": lcr,
        "lcr_status": np.where(required, "required", "not required"),
        "meets_100pct": np.where(lcr >= 1.0, "yes", "no"),
        "mtm_equity_bn": mtm_equity(banks),
    }
