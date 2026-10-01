"""The bank's borrow-or-not decision (session M1.6).

Each half-day, once it knows today's withdrawals and lender refusals, the bank
applies the PRD rule (docs/PRD.md, "How stigma enters the model"):

    borrow if  P(fail without the window) x 1
             > P(draw becomes known) x P(read as distress) x h  +  supervisory cost

Every term is in units of the bank's loss if it fails (= 1), the unit of the
supervisor's dial (Clarification 9, item 3). h is the confidence hit a distress
reading causes (0.25, swept under Amendment 1): confidence runs from 1 (calm) to
0 (full panic, what failure looks like), so the bank prices a reading at h of a
failure (Clarification 10).

The bank's projection is its own quick estimate, not a rerun of the waterfall:
it assumes each coming half-day loses as much as the larger of this half-day and
the last, and counts only cash that can arrive in time without the window (a
payment made late is a failure under the strict test). Collateral capacity comes
from the waterfall's own functions, so the rules exist once.

Nothing here takes a policy name. A policy can change only the inputs: effective
stigma and supervisory cost (through r) and which collateral is ready.
Everything is an array with one entry per row (one bank in one run).
"""

import numpy as np

from engine.funding import _capacity
from engine.information import NEVER

ERF_A = (0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429)  # Abramowitz & Stegun 7.1.26
ERF_P = 0.3275911                                                              # (error below 1.5e-7)


def normal_cdf(x):
    """Chance a standard normal draw is below x. Written out so numpy alone can do it for every row at once."""
    z = np.abs(np.asarray(x, float)) / np.sqrt(2)
    k = 1 / (1 + ERF_P * z)
    erf = 1 - sum(a * k ** (i + 1) for i, a in enumerate(ERF_A)) * np.exp(-z * z)
    return 0.5 * (1 + np.sign(x) * erf)


def cash_in_time(st, k):
    """Cash the bank can have by k half-days from now WITHOUT the discount window.

    Reserves above the floor, repo, securities sales and the Home Loan Bank, each
    counted only if its lag (config/funding.yaml) is at most k, plus cash already
    on its way by then. Repo and sales draw on the same securities, so for each
    class the bank counts the better of the two, and same-day repo never more
    than the line.
    """
    t, lags = st["t"], st["lags"]
    ok = lambda name: lags[name] <= k
    cap = lambda name: _capacity(st, name) if ok(name) else 0.0

    same_day = np.minimum(cap("repo_level1") + cap("repo_level2a"), st["repo_access"] * st["repo_line_left_bn"])
    later = sum(np.maximum(cap(f"repo_next_{c}"), cap(f"sale_{c}")) for c in ("level1", "level2a"))
    securities = np.maximum(same_day, later)
    arriving = sum(sched[:, t:t + k + 1].sum(axis=1) for sched in st["incoming"].values())
    return cap("reserves") + securities + cap("fhlb_line") + cap("fhlb_above_line") + arriving


def project(st, today_out, cfg):
    """The bank's projection over the horizon. Returns arrays per row.

    need_k = owed already + today's outflows + k x (expected outflow per coming half-day)
    gap    = the largest of need_k - cash_k (central projection)
    p_fail = chance that, with future outflows uncertain by +/- forecast_sd, some
             need_k exceeds cash_k by more than the failure tolerance
    """
    p = cfg["projection"]
    tol = st["fail_tol_bn"]
    per_step = np.maximum(today_out, st["last_outflow_bn"])
    known = st["unpaid_outflows_bn"] + today_out
    gap = np.full(len(known), -np.inf)
    request = np.zeros(len(known))
    z_min = np.full(len(known), np.inf)           # how many standard deviations of room are left
    certain_fail = np.zeros(len(known), bool)
    for k in range(p["horizon_steps"]):           # a short loop over the horizon, never over rows
        cash = cash_in_time(st, k)
        future = k * per_step
        room = cash + tol - known - future
        gap = np.maximum(gap, known + future - cash)
        request = np.maximum(request, known + future * (1 + p["request_at_sd"] * p["forecast_sd"]) - cash)
        if k == 0:
            certain_fail = room < 0                # today's payments can't be met on time: no uncertainty left
        else:
            # Outflows run (1 + e) x the central projection, e ~ normal(0, forecast_sd), the same e for every k.
            # Failure at k needs e x future > room, i.e. e above room / future, i.e. z = room / sd standard deviations.
            sd = p["forecast_sd"] * future
            z = np.divide(room, sd, out=np.where(room >= 0, np.inf, -np.inf), where=sd > 0)
            z_min = np.minimum(z_min, z)
    p_fail = np.where(certain_fail, 1.0, 1 - normal_cdf(np.clip(z_min, -40, 40)))
    return {"gap": np.maximum(gap, 0), "request": np.maximum(request, 0), "p_fail": p_fail,
            "shortfall_seen": gap > tol}


def chance_known(st, request):
    """P(the borrowing becomes known to the market), from the M1.5 routes only.

    1 if total borrowing would reach the materiality line (the 8-K names it);
    otherwise, for a first draw, leak chance x 1 + (1 - leak chance) x weekly report's revealing share;
    otherwise 0: the leak and weekly routes were already set off by the first draw.
    """
    rt, off = st["info_cfg"]["routes"], st["routes_off"]
    leak = 0.0 if "leak" in off else rt["leak"]["probability"]
    weekly = 0.0 if "weekly_aggregate" in off else st["weekly_revealing"]
    first = st["first_draw_step"] == NEVER
    threshold = rt["announcement"]["materiality_share_of_assets"] * st["assets_start_bn"]
    material = ((st["material_step"] == NEVER) & (st["dw_drawn_total_bn"] + request >= threshold)
                & ("announcement" not in off))
    return np.where(material, 1.0, np.where(first, leak + (1 - leak) * weekly, 0.0))


def decide(st, today_out, cfg):
    """Apply the PRD rule. Same function, same inputs, for every policy."""
    proj = project(st, today_out, cfg)
    known = chance_known(st, proj["request"])
    already_distressed = st["distress_from"] != NEVER     # one reading per episode: nothing more to lose
    stigma_cost = np.where(already_distressed, 0.0, known * st["stigma_eff"] * st["distress_shock"])
    borrow = proj["p_fail"] > stigma_cost + st["sup_cost_eff"]
    return {**proj, "p_known": known, "stigma_cost": stigma_cost, "sup_cost": st["sup_cost_eff"].copy(),
            "borrow": borrow}
