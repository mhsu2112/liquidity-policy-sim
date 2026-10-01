"""The four policy switches and the five named policies (session M1.7).

Contract 2a: every policy is a combination of four switches, read from
config/policies/policies.yaml. `policy_setup` builds a bank's starting position
from the switches alone; the only thing that differs between C and C' is a
config value (no usage multiple), not a branch on the policy's name.

The routine borrowing rate r comes from engine/information.py::routine_rate,
which is where contract 3a's per-policy rates already live.

Static only: nothing here runs a stress episode.
"""

from pathlib import Path

import numpy as np
import yaml

from engine.balance_sheet import check_balances
from engine.collateral import loan_capacity, start_placement
from engine.five_day import five_day_ratio, hold_extra_reserves, preposition_least_to_pass
from engine.funding import load_funding_settings
from engine.information import draw_info_randoms, load_information_settings, routine_rate, tested_recently
from engine.lcr import compute_lcr, load_lcr_settings
from engine.lcr_credit import (credit, credit_limits, draw_opt_in_u, lcr_required, opted_in,
                               preposition_for_credit, release_hqla, target_credit, usage_draws)

POLICY_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "policies" / "policies.yaml"
SWITCHES = ("prepositioning_mandate", "testing_mandate", "five_day_ratio", "lcr_credit")


def load_policies(path=POLICY_SETTINGS_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


def switches(name, cfg):
    return cfg["policies"][name]["switches"]


def credit_settings(name, cfg):
    """Contract 2d settings, with any named variant's overrides (C': no usage multiple)."""
    return {**cfg["lcr_credit"], **cfg["policies"][name].get("overrides", {})}


def draw_policy_randoms(seed, rows):
    """The random numbers a policy set-up needs, drawn up front and shared by every policy."""
    return {"test_u": draw_info_randoms(seed, rows)["test_u"], "opt_in_u": draw_opt_in_u(seed, rows)}


def policy_setup(banks, name, cfg=None, randoms=None, fs=None, lcr_s=None, info=None):
    """Each bank's starting position under one named policy. Returns a dict of arrays."""
    cfg = cfg or load_policies()
    fs = fs or load_funding_settings()
    lcr_s = lcr_s or load_lcr_settings()
    info = info or load_information_settings()
    if randoms is None:
        raise ValueError("Supply the random numbers up front (draw_policy_randoms), so every policy shares them.")
    sw, c = switches(name, cfg), credit_settings(name, cfg)
    margins = fs["discount_window"]["margins"]
    n = len(banks["bank_id"])
    zero = np.zeros(n)

    b = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in banks.items()}
    place = start_placement(b, fs)
    out = {"extra_reserves_bn": zero, "five_day_unmet_bn": zero, "five_day_shortfall_bn": zero, "opted_in": np.zeros(n, bool),
           "usage_draw_bn": zero, "credit_bn": zero, "credit_if_trigger_fires_bn": zero,
           "released": {k: zero for k in c["release_order"]}}
    for k in ("ceiling_limit_bn", "usage_limit_bn", "capacity_limit_bn"):
        out[k] = np.full(n, np.nan)

    # B and E: the least collateral that passes the five-day ratio (E uses the same collateral).
    if sw["prepositioning_mandate"] or sw["five_day_ratio"]:
        place, out["five_day_shortfall_bn"] = preposition_least_to_pass(b, place, cfg, margins)
    # B only: any gap collateral cannot close is held as extra reserves.
    if sw["five_day_ratio"]:
        b, place, out["extra_reserves_bn"], out["five_day_unmet_bn"] = hold_extra_reserves(b, place, out["five_day_shortfall_bn"])

    # C and C': LCR credit for banks that opt in.
    net_outflows = compute_lcr(b, lcr_s)["calibrated_outflows_bn"]
    makes_usage_draws = np.zeros(n, bool)
    if sw["lcr_credit"]:
        opt = opted_in(b, randoms["opt_in_u"], c["uptake"])
        place = preposition_for_credit(b, place, net_outflows, opt, c, margins, cfg["prepositioning"]["order"])
        k = c["usage_multiple"]
        draws = usage_draws(target_credit(place, net_outflows, c), opt, k, c)
        limits = credit_limits(place, net_outflows, draws, k, c, c["stress_trigger_fires"])
        stress = credit_limits(place, net_outflows, draws, k, c, trigger_fires=True)
        ordinary = credit(credit_limits(place, net_outflows, draws, k, c, trigger_fires=False), opt)
        out.update(limits, opted_in=opt, usage_draw_bn=draws[:, 0], credit_bn=credit(limits, opt),
                   credit_if_trigger_fires_bn=credit(stress, opt))
        # Release is a steady-state choice, sized on ordinary-course credit (Clarification 11 item 1).
        floor = fs["reserves"]["floor_share_of_assets"] * b["total_assets_bn"]
        b, out["released"] = release_hqla(b, c["release_share"] * ordinary, floor, c["release_order"])
        makes_usage_draws = opt & (k is not None)

    # Tested in the last 90 days (contract 3a, Clarification 11): banks that must test or that
    # make usage draws are tested; everyone else is drawn as in M1.6 at the voluntary rate (A's).
    voluntary = info["routine_borrowing"]["rate_by_policy"]["A"]
    drawn = tested_recently(randoms["test_u"], np.full(n, voluntary))
    out["tested"] = sw["testing_mandate"] | makes_usage_draws | drawn

    out["routine_rate"] = np.full(n, routine_rate(name, info, c["uptake"]))   # uptake is used only for C
    out["test_draws_per_year"] = np.full(n, cfg["testing"]["draws_per_year"] if sw["testing_mandate"] else 0)

    # Ratios, after every balance sheet change.
    lcr = compute_lcr(b, lcr_s)
    out["lcr_without_credit"] = lcr["lcr"]
    out["lcr_reported"] = (lcr["hqla_bn"] + out["credit_bn"]) / lcr["calibrated_outflows_bn"]
    out["buffer_gap"] = out["lcr_reported"] - out["lcr_without_credit"]   # PRD metrics table
    out["lcr_required"] = lcr_required(b)
    out["five_day_ratio"] = five_day_ratio(b, place, cfg, margins)
    out["loan_capacity_bn"] = loan_capacity(place)

    check_balances(b)
    return {"name": name, "switches": sw, "banks": b, "placement": place, **out}
