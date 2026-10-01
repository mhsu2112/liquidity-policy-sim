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
"""

import numpy as np

from engine.episode import END_NAMES
from engine.information import NEVER


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
    }
