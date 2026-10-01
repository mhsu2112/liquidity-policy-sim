"""Annual steady-state cost of each policy for each bank (session M1.8).

Every cost is measured against policy A, so A costs zero by construction
(Clarification 13). All annual, in $ millions; balance sheet inputs are in $bn.

    prepositioning  (collateral at the Fed under the policy - under A), by type,
                    x its contract 6 rate. Loans at face value, securities at market
                    value. Negative where a policy leaves less at the Fed than A.
    draws           routine overnight draws a year x size x (primary credit rate -
                    interest on reserves) x 1/360: B, B' and E's four $50m tests;
                    C's ten usage draws a year by banks that opt in.
    extra reserves  B and B''s extra reserves x the loan-to-reserve spread.
    HQLA released   C and C' banks that opt in earn the same spread on what they
                    release into loans: a negative cost.
    one-time loss   unrealized loss realized when securities are released. Reported
                    on its own, never added to the annual cost.

Only the setups' numbers are read: nothing here knows a policy's name.
All banks at once: every quantity is an array with one entry per bank.
"""

from pathlib import Path

import numpy as np
import yaml

from engine.collateral import LOAN_TYPES, SECURITY_CLASSES, fed_loans_of_type

COST_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "costs.yaml"
BP = 1e-4          # one basis point, as a fraction
BN_TO_M = 1000.0   # $bn -> $m


def load_cost_settings(path=COST_SETTINGS_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


def at_fed(place):
    """Collateral at the Fed by type ($bn): loans at face value, securities at market value."""
    out = {t: fed_loans_of_type(place, t) for t in LOAN_TYPES}
    out.update({c: place[f"fed_{c}_mv_bn"] for c in SECURITY_CLASSES})
    return out


def draws_per_year(setup, pol_cfg):
    """Routine draws a year and their size ($bn): tests if the policy mandates them, else usage draws."""
    tests = setup["test_draws_per_year"]
    usage_per_year = 2 * pol_cfg["lcr_credit"]["usage_draws_per_six_months"]   # five every six months
    usage = np.where(setup["usage_draw_bn"] > 0, usage_per_year, 0)
    count = np.where(tests > 0, tests, usage)
    size = np.where(tests > 0, pol_cfg["testing"]["draw_size_bn"], setup["usage_draw_bn"])
    return count, size


def policy_costs(setup, setup_a, cost_cfg, pol_cfg, spread_bp=None):
    """Each cost component for one policy, $m a year per bank (one-time loss in $m)."""
    spread = (cost_cfg["loan_to_reserve_spread_bp"] if spread_bp is None else spread_bp) * BP
    mult = cost_cfg["prepositioning_rate_multiple"]
    mine, base = at_fed(setup["placement"]), at_fed(setup_a["placement"])

    out = {}
    for k in (*SECURITY_CLASSES, *LOAN_TYPES):
        extra = mine[k] - base[k]
        out[f"extra_at_fed_{k}_bn"] = extra
        out[f"prepositioning_{k}_m"] = extra * cost_cfg["prepositioning_bp"][k] * BP * mult * BN_TO_M
    out["prepositioning_m"] = sum(out[f"prepositioning_{k}_m"] for k in (*SECURITY_CLASSES, *LOAN_TYPES))

    count, size = draws_per_year(setup, pol_cfg)
    out["draws_per_year"], out["draw_size_bn"] = count, size
    one_night = cost_cfg["draw_spread_bp"] * BP / cost_cfg["day_count_days"]
    out["draws_m"] = count * size * one_night * BN_TO_M

    out["extra_reserves_bn"] = setup["extra_reserves_bn"]
    out["extra_reserves_m"] = setup["extra_reserves_bn"] * spread * BN_TO_M
    out["hqla_released_bn"] = sum(setup["released"].values())
    out["hqla_released_m"] = 0.0 - out["hqla_released_bn"] * spread * BN_TO_M   # 0.0 - x: never "-0"

    out["annual_cost_m"] = out["prepositioning_m"] + out["draws_m"] + out["extra_reserves_m"] + out["hqla_released_m"]
    # Equity changes only through losses realized on released securities (Clarification 11 item 1).
    out["one_time_loss_m"] = (setup_a["banks"]["equity_bn"] - setup["banks"]["equity_bn"]) * BN_TO_M
    return out
