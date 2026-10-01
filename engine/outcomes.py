"""Outcomes of an episode, one row per run (session M1.6, Clarification 10).

Every result is read at the row's end half-day: nothing after a bank fails or
stabilizes counts (engine/episode.py keeps computing ended rows only because
every row moves together).

    end_state           failed / stabilized / reached the last day
    end_day             day the episode ended (1 = first day)
    shortfall_seen      first half-day the bank's projection showed a shortfall
                        without the window (above the failure tolerance)
    first_borrowed      first half-day the window actually lent to the bank
    hesitation_steps    first_borrowed - shortfall_seen, in half-days
                        (blank if either never happened)
    peak_owed_bn        shortfall: the largest amount still owed at the end of a half-day
    peak_uncovered_bn   the part of that no source could cover at all, even late
    official_support_bn discount window lending agreed by the end, including cash
                        still on its way (window loans are not repaid within an
                        episode). Home Loan Bank advances are shown separately and
                        not counted as official support (Clarification 10)
    effective_stigma    market stigma x e^(-s x r) (contract 3a)
    non_compliant       B / B' only: the bank started below its five-day ratio, with
                        the gap shown (Amendment 3 item 2)
    c_credit_left_bn    Option C's credit at the end, after every window draw (contract 2d)
    timing_band         for a failed run, why it failed (session M1.12; Clarification 18):
                        "pure timing" (owed no more than cash already agreed and arriving by the
                        next day, equity positive), "partly covered", "not covered", or
                        "equity below zero"; blank if the run did not fail
    timing_only_upper_bound  Amendment 6 grace-rule count: a failed run whose unpaid amount at
                        failure is covered by cash already agreed and arriving by the next
                        morning, with equity >= 0. An UPPER BOUND on timing-only failures;
                        never used in the lead / tie / trade-off rule or to score a hypothesis
"""

import numpy as np

from engine.episode import END_NAMES, FAILED
from engine.information import NEVER
from engine.lcr_credit import credit_after_draws


def _step_or_nan(steps, end_step):
    """A step number, or NaN if it never happened or came after the end."""
    s = np.asarray(steps, float)
    return np.where((steps == NEVER) | (steps > end_step), np.nan, s)


def episode_outcomes(st):
    """Dict of arrays, one entry per row."""
    end = st["end_step"]
    spd = st["settings"]["time"]["steps_per_day"]
    seen = _step_or_nan(st["first_shortfall_seen_step"], end)
    borrowed = _step_or_nan(st["first_draw_step"], end)
    return {
        "bank_id": st["bank_id"],
        "end_state": np.array([END_NAMES[s] for s in st["end_state"]]),
        "end_step": end,
        "end_day": end // spd + 1,
        "shortfall_seen_step": seen,
        "first_borrowed_step": borrowed,
        "first_rule_said_borrow_step": _step_or_nan(st["first_borrow_yes_step"], end),
        "hesitation_steps": borrowed - seen,
        "peak_owed_bn": st["peak_owed_bn"],
        "peak_owed_share_of_assets": st["peak_owed_bn"] / st["assets_start_bn"],
        "peak_uncovered_bn": st["peak_uncovered_bn"],
        "official_support_bn": st["dw_agreed_bn"],
        "fhlb_peak_bn": st["peak_fhlb_bn"],
        "effective_stigma": st["stigma_eff"],
        "effective_supervisory_cost": st["sup_cost_eff"],
        "collateral_tested": st["tested"],
        "non_compliant": st["non_compliant"],
        "five_day_gap_bn": st["five_day_gap_bn"],
        "c_credit_start_bn": st["credit_start_bn"],
        "c_credit_left_bn": credit_after_draws(st["credit_start_bn"], st["dw_agreed_bn"]),   # draws up to the end
        "owed_at_failure_bn": st["owed_at_failure_bn"],
        "on_way_at_failure_bn": st["on_way_at_failure_bn"],
        "timing_band": timing_band(st),
        "timing_only_upper_bound": timing_only(st),
    }


def timing_only(st):
    """Amendment 6: failed, and the unpaid amount was covered by cash arriving by the next morning, equity >= 0."""
    return ((st["end_state"] == FAILED) & (st["owed_at_failure_bn"] <= st["by_next_morning_at_failure_bn"])
            & (st["equity_at_failure_bn"] >= 0))


def timing_band(st):
    """Why a failed run failed: one of four bands, exhaustive and exclusive; blank if it did not fail."""
    failed = st["end_state"] == FAILED
    owed, on_way, equity = st["owed_at_failure_bn"], st["on_way_at_failure_bn"], st["equity_at_failure_bn"]
    band = np.where(equity < 0, "equity below zero",
                    np.where(owed <= on_way, "pure timing",
                             np.where(on_way > 0, "partly covered", "not covered")))
    return np.where(failed, band, "")
