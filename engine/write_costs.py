"""Write each policy's annual cost for each bank (run with `make costs`).

Produces two files in outputs/:
- costs.csv: one row per bank per policy (40 x 6 = 240), each cost component in
  its own column, annual $m relative to policy A, plus the totals at each point
  of the loan-to-reserve spread sweep (contract 6: 200 / 250 / 300 bp).
- cost_worked_example.xlsx: two banks under B, B' and C with live formulas.

Static only: no stress episode runs. No ranking or summary across policies is
made; costs are reported alongside outcomes in M3 (contract section 4).
"""

import numpy as np

from engine.banks import SETTINGS_PATH, generate_banks, load_settings
from engine.cost_workbook import DEFAULT_WORKBOOK, write_cost_workbook
from engine.costs import COST_SETTINGS_PATH, load_cost_settings, policy_costs
from engine.funding import BEHAVIOR_SETTINGS_PATH, FUNDING_SETTINGS_PATH, load_funding_settings
from engine.information import INFO_SETTINGS_PATH, load_information_settings
from engine.lcr import LCR_SETTINGS_PATH, load_lcr_settings
from engine.policies import POLICY_SETTINGS_PATH, draw_policy_randoms, load_policies, policy_setup
from engine.write_banks import ROOT, stamps, write_csv
from engine.write_policy_table import POLICY_ORDER

DEFAULT_OUT = ROOT / "outputs" / "costs.csv"
COUNT_COLUMNS = {"draws_per_year"}


def build_setups(banks=None, pol_cfg=None):
    """Every policy's setup, with the policy table's random numbers (shared by every policy)."""
    banks = banks if banks is not None else generate_banks(load_settings(SETTINGS_PATH))
    pol_cfg = pol_cfg or load_policies()
    fs, lcr_s, info = load_funding_settings(), load_lcr_settings(), load_information_settings()
    randoms = draw_policy_randoms(pol_cfg["seed"], len(banks["bank_id"]))
    return banks, {name: policy_setup(banks, name, pol_cfg, randoms, fs, lcr_s, info) for name in POLICY_ORDER}


def cost_columns(banks, name, setup, setup_a, cost_cfg, pol_cfg):
    n = len(banks["bank_id"])
    c = policy_costs(setup, setup_a, cost_cfg, pol_cfg)
    cols = {"policy": np.full(n, name), "bank_id": banks["bank_id"], "archetype": banks["archetype"],
            "c_opted_in": np.where(setup["opted_in"], "yes", "no")}
    for k, v in c.items():
        cols[k] = v.astype(int).astype(str) if k in COUNT_COLUMNS else np.char.mod("%.6f", v + 0.0)
    # The spread sweep moves only extra reserves and released HQLA (Clarification 13).
    for bp in cost_cfg["loan_to_reserve_spread_grid_bp"]:
        cols[f"annual_cost_at_{bp}bp_spread_m"] = np.char.mod(
            "%.6f", policy_costs(setup, setup_a, cost_cfg, pol_cfg, spread_bp=bp)["annual_cost_m"] + 0.0)
    return cols


def build_cost_table(banks=None, setups=None, cost_cfg=None, pol_cfg=None):
    pol_cfg = pol_cfg or load_policies()
    if setups is None:
        banks, setups = build_setups(banks, pol_cfg)
    cost_cfg = cost_cfg or load_cost_settings()
    parts = [cost_columns(banks, name, setups[name], setups["A"], cost_cfg, pol_cfg) for name in POLICY_ORDER]
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def write_costs(out_path=DEFAULT_OUT, workbook_path=DEFAULT_WORKBOOK):
    pol_cfg, cost_cfg = load_policies(), load_cost_settings()
    banks, setups = build_setups(pol_cfg=pol_cfg)
    cols = build_cost_table(banks, setups, cost_cfg, pol_cfg)
    n = len(cols["policy"])
    cols.update(stamps(n, SETTINGS_PATH, POLICY_SETTINGS_PATH, COST_SETTINGS_PATH, FUNDING_SETTINGS_PATH,
                       BEHAVIOR_SETTINGS_PATH, LCR_SETTINGS_PATH, INFO_SETTINGS_PATH))
    return write_csv(cols, out_path), write_cost_workbook(banks, setups, cost_cfg, pol_cfg, workbook_path), n


if __name__ == "__main__":
    csv_path, xlsx_path, rows = write_costs()
    print(f"Wrote {csv_path.relative_to(ROOT)}: {rows} rows (40 banks x {len(POLICY_ORDER)} policies), "
          f"annual $m relative to policy A. No stress runs, no ranking.")
    print(f"Wrote {xlsx_path.relative_to(ROOT)}: worked examples with live formulas.")
