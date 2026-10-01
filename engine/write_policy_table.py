"""Write each bank's starting position under each policy (run with `make policy-table`).

One row per bank per policy (40 banks x 5 policies = 200 rows) in
outputs/policy_table.csv. Static calculations only: no stress episode runs
(project Rule 2). Policy names: A, B, C, C_prime (C without the usage multiple), E.

Collateral columns are face value (securities at market value) unless they say
"lendable", which is after the Fed's margin (contract 2b).
"""

import numpy as np

from engine.banks import SETTINGS_PATH, generate_banks, load_settings
from engine.collateral import fed_loans
from engine.funding import BEHAVIOR_SETTINGS_PATH, FUNDING_SETTINGS_PATH, load_funding_settings
from engine.information import INFO_SETTINGS_PATH, load_information_settings
from engine.lcr import LCR_SETTINGS_PATH, load_lcr_settings
from engine.policies import POLICY_SETTINGS_PATH, SWITCHES, draw_policy_randoms, load_policies, policy_setup
from engine.write_banks import ROOT, stamps, write_csv

DEFAULT_OUT = ROOT / "outputs" / "policy_table.csv"
POLICY_ORDER = ["A", "B", "C", "C_prime", "E"]


def money(x):
    return np.char.mod("%.6f", np.asarray(x, float))


def ratio(x):
    return np.char.mod("%.6f", np.asarray(x, float))


def yes_no(x):
    return np.where(np.asarray(x, bool), "yes", "no")


def policy_columns(banks, s):
    """The columns for one policy, all banks at once."""
    p, b = s["placement"], s["banks"]
    n = len(banks["bank_id"])
    no_lcr = ~s["lcr_required"]
    cols = {
        "policy": np.full(n, s["name"]),
        "bank_id": banks["bank_id"],
        "archetype": banks["archetype"],
        **{f"switch_{k}": np.full(n, "on" if s["switches"][k] else "off") for k in SWITCHES},
        # Collateral at the Fed and where it came from (Clarifications 4 and 11).
        "fed_loans_from_status_quo_bn": money(p["fed_loans_baseline_bn"]),
        "fed_loans_from_unpledged_bn": money(p["fed_loans_from_unpledged_bn"]),
        "fed_loans_from_fhlb_bn": money(p["fed_loans_from_fhlb_bn"]),
        "fed_loans_turned_into_reserves_bn": money(p["fed_loans_converted_bn"]),
        "fed_loans_total_bn": money(fed_loans(p)),
        "fed_level2a_securities_mv_bn": money(p["fed_level2a_mv_bn"]),
        "fed_level1_securities_mv_bn": money(p["fed_level1_mv_bn"]),
        "loans_still_unpledged_bn": money(p["unpledged_loans_bn"]),
        "loans_still_at_fhlb_bn": money(p["fhlb_loans_bn"]),
        "loan_capacity_lendable_bn": money(s["loan_capacity_bn"]),
        # Testing and routine borrowing (contract 2c, 3a).
        "tested_last_90_days": yes_no(s["tested"]),
        "test_draws_per_year": s["test_draws_per_year"].astype(str),
        "routine_borrowing_rate": ratio(s["routine_rate"]),
        # Option B (contract 2c), reported under every policy.
        "five_day_ratio": ratio(s["five_day_ratio"]),
        "five_day_collateral_shortfall_bn": money(s["five_day_shortfall_bn"]),
        "b_extra_reserves_bn": money(s["extra_reserves_bn"]),
        "b_gap_left_after_all_loans_bn": money(s["five_day_unmet_bn"]),
        # LCR and Option C (contract 2d).
        "lcr_status": np.where(no_lcr, "not required", "required"),
        "lcr_reported": ratio(s["lcr_reported"]),
        "lcr_without_credit": ratio(s["lcr_without_credit"]),
        "buffer_gap": ratio(s["buffer_gap"]),
        "c_opted_in": yes_no(s["opted_in"]),
        "c_ceiling_limit_bn": money(s["ceiling_limit_bn"]),
        "c_usage_limit_bn": np.where(np.isinf(s["usage_limit_bn"]), "no limit", money(s["usage_limit_bn"])),
        "c_capacity_limit_bn": money(s["capacity_limit_bn"]),
        "c_credit_bn": money(s["credit_bn"]),
        "c_credit_if_trigger_fires_bn": money(s["credit_if_trigger_fires_bn"]),
        "c_usage_draw_size_bn": money(s["usage_draw_bn"]),
        **{f"c_hqla_released_{k}_bn": money(v) for k, v in s["released"].items()},
        "c_hqla_released_total_bn": money(sum(s["released"].values())),
        # The balance sheet after the policy.
        "reserves_bn": money(b["reserves_bn"]),
        "level1_securities_book_bn": money(b["level1_securities_bn"]),
        "level2a_securities_book_bn": money(b["level2a_securities_bn"]),
        "loans_bn": money(b["loans_bn"]),
        "equity_bn": money(b["equity_bn"]),
        "total_assets_bn": money(b["total_assets_bn"]),
    }
    # Limits that don't apply to this policy are written blank, not as "nan".
    return {k: np.where(v == "nan", "", v) for k, v in cols.items()}


def build_table(banks=None, cfg=None):
    banks = banks if banks is not None else generate_banks(load_settings(SETTINGS_PATH))
    cfg = cfg or load_policies()
    fs, lcr_s, info = load_funding_settings(), load_lcr_settings(), load_information_settings()
    randoms = draw_policy_randoms(cfg["seed"], len(banks["bank_id"]))   # shared by every policy
    parts = [policy_columns(banks, policy_setup(banks, name, cfg, randoms, fs, lcr_s, info))
             for name in POLICY_ORDER]
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def write_policy_table(out_path=DEFAULT_OUT):
    cols = build_table()
    n = len(cols["policy"])
    cols.update(stamps(n, SETTINGS_PATH, POLICY_SETTINGS_PATH, FUNDING_SETTINGS_PATH,
                       BEHAVIOR_SETTINGS_PATH, LCR_SETTINGS_PATH, INFO_SETTINGS_PATH))
    return write_csv(cols, out_path), n


if __name__ == "__main__":
    path, rows = write_policy_table()
    print(f"Wrote {path.relative_to(ROOT)}: {rows} rows (40 banks x 5 policies). No stress runs.")
