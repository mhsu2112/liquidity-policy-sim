"""Depositors: fast uninsured, slow uninsured and insured (session M1.4).

Rules from docs/amendments.md Clarification 8. All quantities are arrays with
one entry per row (a row is one bank in one run); no step loops over rows.

Confidence (1 = calm, 0 = panic), each half-day:
    C = 1 - S x (1 + noise) x (1 + g) - c x R, held between 0 and 1
where S is the news shock (fading by half every 2 days), g the share of the
bank's starting book equity gone on a mark-to-market basis, R the share of
starting uninsured deposits withdrawn over the last day, and c the
coordination strength. Unrealized losses matter only once news draws attention
to them, as with SVB, whose losses were public for months before the run.

Withdrawals (Amendment 2, session M1.6b): fast and slow depositors leave at
1 - e^(-a x max(0, theta - C)) of their remaining balance each half-day, so
nobody withdraws while confidence is above the tolerance level theta.

From session M1.5, S also includes the news from a known discount window draw
read as distress (Clarification 9, item 2; engine/information.py). It is zero
until a route reveals a draw and the market reads it as distress.
"""

import numpy as np

from engine.information import distress_news


def start_depositors(st, banks, agents):
    """Split each bank's uninsured deposits into fast and slow groups by type."""
    fast_share = np.array([agents["depositors"]["fast_share_of_uninsured"][a] for a in banks["archetype"]])
    st["fast_uninsured_bn"] = fast_share * banks["uninsured_deposits_bn"]
    st["slow_uninsured_bn"] = banks["uninsured_deposits_bn"] - st["fast_uninsured_bn"]
    st["uninsured_start_bn"] = banks["uninsured_deposits_bn"].copy()
    st["book_equity_start_bn"] = banks["equity_bn"].copy()


def confidence(st, t, agents, behavior):
    c = agents["confidence"]
    half_life = c["shock_half_life_steps"]
    shock_now = st["shock"] * 0.5 ** (t / half_life) + distress_news(st, t, half_life)
    news = shock_now * np.maximum(1 + st["noise"][:, t], 0)
    mtm_equity = st["equity_bn"] - st["unrealized_loss_bn"]
    g = np.clip(1 - mtm_equity / st["book_equity_start_bn"], 0, 1)
    w = c["coordination_window_steps"]
    recent = st["withdrawn_uninsured"][:, max(t - w, 0):t].sum(axis=1)
    coordination = recent / st["uninsured_start_bn"]
    return np.clip(1 - news * (1 + g) - behavior["coordination_strength"]["value"] * coordination, 0, 1)


def leave_share(conf, behavior):
    """Share of a group leaving this half-day: 1 - exp(-a x max(0, theta - confidence)).

    Amendment 2: depositors tolerate small drops in confidence. Above the
    tolerance level theta nobody leaves; below it, the further confidence falls,
    the more leave. Fast and slow depositors both use this rule (slow with their
    lag); insured depositors leave at a fixed fraction of the fast rate.
    """
    sens = behavior["depositor_sensitivity"]
    theta = sens["tolerance_theta"]["value"]
    return 1 - np.exp(-sens["value"] * np.maximum(0.0, theta - conf))


def withdrawals(st, t, agents, behavior):
    """Amounts each group withdraws this half-day; updates the group balances."""
    fast = leave_share(st["confidence"][:, t], behavior)
    lag = behavior["slow_depositor_lag_steps"]["value"]
    # Slow depositors react to confidence `lag` half-days ago; before day 1 it was calm (1).
    slow = leave_share(st["confidence"][:, t - lag], behavior) if t >= lag else np.zeros_like(fast)
    insured = agents["depositors"]["insured_rate_vs_fast"] * fast

    out = {"fast": fast * st["fast_uninsured_bn"], "slow": slow * st["slow_uninsured_bn"],
           "insured": insured * st["insured_deposits_bn"],
           "fast_share": fast, "slow_share": slow, "insured_share": insured}
    st["fast_uninsured_bn"] -= out["fast"]
    st["slow_uninsured_bn"] -= out["slow"]
    st["withdrawn_uninsured"][:, t] = out["fast"] + out["slow"]
    return out
