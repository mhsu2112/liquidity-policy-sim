"""The four policy switches and the six named policies (sessions M1.7, M1.7b).

Contract 2a: every policy is a combination of four switches, read from
config/policies/policies.yaml. `policy_setup` builds a bank's starting position
from the switches alone. Named variants differ only by config values: C' has no
usage multiple; B' counts loans only toward the five-day ratio and moves C&I first
(Amendment 3). No branch anywhere tests a policy's name.

This module is the ONLY place a policy name enters the model (Clarification 12 item 8).
Everything downstream (the episode, the waterfall, the bank's decision, the information
routes) receives the setup's numbers, never a name.

Static only: nothing here runs a stress episode.
"""

from pathlib import Path

import numpy as np
import yaml

from engine.balance_sheet import check_balances
from engine.collateral import LOAN_TYPES, loan_capacity, start_placement, total
from engine.five_day import five_day_ratio, hold_extra_reserves, preposition_least_to_pass
from engine.funding import load_funding_settings
from engine.information import draw_info_randoms, load_information_settings, tested_recently
from engine.lcr import compute_lcr, load_lcr_settings
from engine.lcr_credit import (credit, credit_limits, draw_opt_in_u, lcr_required, opted_in,
                               preposition_for_credit, release_hqla, target_credit, usage_draws)

POLICY_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "policies" / "policies.yaml"
SWITCHES = ("prepositioning_mandate", "testing_mandate", "five_day_ratio", "lcr_credit")


def load_policies(path=POLICY_SETTINGS_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


def routine_rate(name, info, uptake=None):
    """Contract 3a: routine draws per bank per quarter under a named policy.

    C: uptake x 2.5 (five usage draws per six months by banks that opt in);
    every other policy: its fixed rate in config/information.yaml.
    """
    rb = info["routine_borrowing"]
    if name == "C":
        return uptake * rb["c_usage_draws_per_quarter"]
    return rb["rate_by_policy"][name]


def policy_settings(name, cfg):
    """The settings one named policy runs on: its switches, plus the shared settings with any
    named variant's overrides applied (C': no usage multiple; B': loans only, C&I first)."""
    entry = cfg["policies"][name]
    ov = entry.get("overrides", {})
    return {"switches": entry["switches"],
            "counts": ov.get("five_day_counts", cfg["five_day_ratio"]["counts"]),
            "order": ov.get("prepositioning_order", cfg["prepositioning"]["order"]),
            "credit": {**cfg["lcr_credit"], **{k: v for k, v in ov.items() if k in cfg["lcr_credit"]}}}


def draw_policy_randoms(seed, rows):
    """The random numbers a policy set-up needs, drawn up front and shared by every policy."""
    return {"test_u": draw_info_randoms(seed, rows)["test_u"], "opt_in_u": draw_opt_in_u(seed, rows)}


def policy_setup(banks, name, cfg=None, randoms=None, fs=None, lcr_s=None, info=None):
    """Each bank's starting position under one named policy. Returns a dict of arrays.

    `randoms` comes from draw_policy_randoms; opt-in numbers are needed only with LCR credit on.
    """
    cfg = cfg or load_policies()
    fs = fs or load_funding_settings()
    lcr_s = lcr_s or load_lcr_settings()
    info = info or load_information_settings()
    if randoms is None:
        raise ValueError("Supply the random numbers up front (draw_policy_randoms), so every policy shares them.")
    ps = policy_settings(name, cfg)
    sw, c, counts = ps["switches"], ps["credit"], ps["counts"]
    margins = fs["discount_window"]["margins"]
    n = len(banks["bank_id"])
    zero = np.zeros(n)

    b = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in banks.items()}
    place = start_placement(b, fs)
    out = {"extra_reserves_bn": zero, "five_day_unmet_bn": zero, "five_day_shortfall_bn": zero,
           "opted_in": np.zeros(n, bool), "usage_draw_bn": zero, "credit_bn": zero,
           "credit_if_trigger_fires_bn": zero, "released": {k: zero for k in c["release_order"]}}
    for k in ("ceiling_limit_bn", "usage_limit_bn", "capacity_limit_bn"):
        out[k] = np.full(n, np.nan)

    # B, B' and E: the least collateral that passes the five-day ratio (E uses B's collateral).
    if sw["prepositioning_mandate"] or sw["five_day_ratio"]:
        place, out["five_day_shortfall_bn"] = preposition_least_to_pass(b, place, cfg, margins, ps["order"], counts)
    # B and B': any gap collateral cannot close is held as extra reserves; a bank still short
    # after turning every loan into reserves runs non-compliant (Amendment 3 item 2).
    if sw["five_day_ratio"]:
        b, place, out["extra_reserves_bn"], out["five_day_unmet_bn"] = hold_extra_reserves(
            b, place, out["five_day_shortfall_bn"])
    out["non_compliant"] = out["five_day_unmet_bn"] > 0

    # C and C': LCR credit for banks that opt in.
    net_outflows = compute_lcr(b, lcr_s)["calibrated_outflows_bn"]
    makes_usage_draws = np.zeros(n, bool)
    if sw["lcr_credit"]:
        opt = opted_in(b, randoms["opt_in_u"], c["uptake"])
        place = preposition_for_credit(b, place, net_outflows, opt, c, margins, cfg["prepositioning"]["order"])
        k = c["usage_multiple"]
        draws = usage_draws(target_credit(place, net_outflows, c), opt, k, c)
        # The stress trigger switch (contract 2d, S1): on means it fires on day 1, so the 30% ceiling applies.
        limits = credit_limits(place, net_outflows, draws, k, c, c["stress_trigger_fires"])
        stress = credit_limits(place, net_outflows, draws, k, c, trigger_fires=True)
        ordinary = credit(credit_limits(place, net_outflows, draws, k, c, trigger_fires=False), opt)
        out.update(limits, opted_in=opt, usage_draw_bn=draws[:, 0], credit_bn=credit(limits, opt),
                   credit_if_trigger_fires_bn=credit(stress, opt))
        # Release is a steady-state choice, sized on ordinary-course credit (Clarification 11 item 1).
        # The new loans keep the bank's mix and eligible share, and start pledged nowhere.
        floor = fs["reserves"]["floor_share_of_assets"] * b["total_assets_bn"]
        released_total = c["release_share"] * ordinary
        eligible_share = b["eligible_loans_bn"] / b["loans_bn"]
        place = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in place.items()}
        for t in LOAN_TYPES:
            place[f"unpledged_{t}_bn"] += released_total * eligible_share * b[f"{t}_loans_bn"] / b["loans_bn"]
        b, out["released"] = release_hqla(b, released_total, floor, c["release_order"])
        makes_usage_draws = opt & (k is not None)

    # Tested in the last 90 days (contract 3a, Clarification 11): banks that must test or that
    # make usage draws are tested; everyone else is drawn as in M1.6 at the voluntary rate (A's).
    voluntary = info["routine_borrowing"]["rate_by_policy"]["A"]
    drawn = tested_recently(randoms["test_u"], np.full(n, voluntary))
    out["tested"] = sw["testing_mandate"] | makes_usage_draws | drawn

    out["routine_rate"] = np.full(n, routine_rate(name, info, c["uptake"]))   # uptake is used only for C
    out["test_draws_per_year"] = np.full(n, cfg["testing"]["draws_per_year"] if sw["testing_mandate"] else 0)

    # Ratios, after every balance sheet change. The five-day ratio is the policy's own measure
    # (loans only under B'); it is reported under every policy.
    lcr = compute_lcr(b, lcr_s)
    out["lcr_without_credit"] = lcr["lcr"]
    out["lcr_reported"] = (lcr["hqla_bn"] + out["credit_bn"]) / lcr["calibrated_outflows_bn"]
    out["buffer_gap"] = out["lcr_reported"] - out["lcr_without_credit"]   # PRD metrics table
    out["lcr_required"] = lcr_required(b)
    out["five_day_counts"] = counts
    out["five_day_ratio"] = five_day_ratio(b, place, cfg, margins, counts)
    out["loan_capacity_bn"] = loan_capacity(place)

    check_balances(b)
    return {"name": name, "switches": sw, "banks": b, "placement": with_totals(place), **out}


def with_totals(place):
    """The final placement plus totals over loan types, for the table and readers.

    Computed once, from the final placement, so they can't go stale. The waterfall reads
    the per-type lines, never these totals.
    """
    p = dict(place)
    for k in ("baseline", "from_unpledged", "from_fhlb", "converted"):
        p[f"fed_loans_{k}_bn"] = total(place, "fed_{}_" + k + "_bn")
    p["unpledged_loans_bn"] = total(place, "unpledged_{}_bn")
    p["fhlb_loans_bn"] = total(place, "fhlb_{}_bn")
    return p
