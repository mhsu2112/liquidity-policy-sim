"""One episode, half-day by half-day (sessions M1.4 to M1.6).

Each half-day, for every row at once (a row is one bank in one run):
  1. observers receive the information events due now (session M1.5);
  2. depositors and lenders judge confidence;
  3. in the morning, wholesale and repo lenders roll or refuse;
  4. fast, slow and insured depositors withdraw;
  5. a forced discount window draw, if the caller asked for one (demo and tests only);
  6. the bank decides whether to borrow from the window (session M1.6, agents/bank.py);
  7. every outflow and repayment goes through the funding waterfall, with the window
     open only for banks that decided to borrow; those banks then ask for the rest of
     their projected gap ahead of need;
  8. what happened (draws, sales, refusals) schedules new information events,
     and same-half-day events are delivered;
  9. end conditions are checked (session M1.6, Clarification 10).

A row that has ended (failed or stabilized) keeps being computed, because
vectorized steps move every row together, but nothing after its end half-day
counts: engine/outcomes.py reads every result at the end half-day.

Every run that is not a demo must supply its random numbers up front
(`info_randoms`, from engine.information.draw_info_randoms); a run without them
raises an error.

From session M1.7b every episode starts from a policy setup (engine/policies.py):
balance sheet, collateral at the Fed, tested status, routine borrowing rate and
Option C's credit (Clarification 12 item 3). Without one, it builds the status quo
(policy A) through the same setup builder. Nothing here knows a policy's name.
"""

from pathlib import Path

import numpy as np
import yaml

from agents.bank import decide
from agents.depositors import confidence, start_depositors, withdrawals
from agents.lenders import morning_decisions
from engine.balance_sheet import ONE_DOLLAR_BN
from engine.funding import force_dw_draw, load_funding_settings, start_state, step
from engine.information import (BORROWING_ROUTES, NEVER, deliver, load_information_settings, no_information_randoms,
                                observe, start_information, tested_recently)
from engine.lcr_credit import credit_after_draws
from engine.policies import policy_setup

CONFIG = Path(__file__).resolve().parent.parent / "config"

# End states (Clarification 10). 0 = still running.
RUNNING, FAILED, STABILIZED, REACHED_END = 0, 1, 2, 3
END_NAMES = {RUNNING: "running", FAILED: "failed", STABILIZED: "stabilized", REACHED_END: "reached the last day"}


def load_yaml(name):
    with open(CONFIG / name) as f:
        return yaml.safe_load(f)


def draw_noise(seed, rows, steps, agents):
    """All random news noise for an episode, made up front: one row per run, one column per half-day.

    Drawing them first means every policy sees exactly the same draws (paired runs),
    and any single row can be re-run alone with its own draws.
    """
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, agents["confidence"]["news_noise_sd"], size=(rows, steps))


def start_episode(banks, shock, noise, funding=None, agents=None, behavior=None, tested=None,
                  info=None, stigma=0.0, strength_s=None, routine=None, supervision=None,
                  info_randoms=None, routes_off=(), forced_draws=None, decision=None,
                  distress_shock=None, demo=False, setup=None):
    """Set up every row. Options, one value or one per row:

    setup         a policy setup for these rows (engine.policies.policy_setup); default: the status quo

    stigma        market stigma, the chance a known draw is read as distress (contract 5 grid)
    strength_s    routine-borrowing effect strength s (default: config/information.yaml)
    routine       routine borrowing rate r (default: policy A's, contract 3a)
    supervision   supervisor dial level (default: config/information.yaml)
    info_randoms  from engine.information.draw_info_randoms; shared by every policy. REQUIRED
                  unless demo=True (Clarification 10)
    tested        override whether collateral was tested in the last 90 days (tests only);
                  otherwise drawn from info_randoms["test_u"] and r
    distress_shock  the confidence hit of a distress reading (default 0.25; Amendment 1 grid)
    routes_off    route names to switch off (tests only)
    forced_draws  {step: $bn per row}: discount window draws forced at that step (demo and tests)
    """
    n = len(banks["bank_id"])
    if info_randoms is None:
        if not demo:
            raise ValueError("A run must supply its random numbers up front (info_randoms from "
                             "engine.information.draw_info_randoms). Only demos may run without them.")
        info_randoms = no_information_randoms(n)
    if tested is None and "test_u" not in info_randoms:
        raise ValueError("info_randoms lacks test_u (was the collateral tested?); use draw_info_randoms.")

    funding = funding or load_funding_settings()
    info = info or load_information_settings()
    agents = agents or load_yaml("agents.yaml")
    behavior = behavior or load_yaml("params_frozen.yaml")   # frozen in M1.10
    decision = decision or load_yaml("decision.yaml")
    if setup is None:   # the status quo, built by the one setup builder (Clarification 12 item 3)
        test_u = info_randoms.get("test_u", np.ones(n))   # a `tested` override needs no test_u
        setup = policy_setup(banks, "A", randoms={"test_u": test_u}, fs=funding, info=info)
    banks = setup["banks"]
    r = setup["routine_rate"] if routine is None else routine
    if tested is None:
        # The setup's tested status, unless a caller sets r by hand (demos, tests); then it is
        # drawn from that r exactly as in M1.6 (Clarification 10 item 4).
        tested = (setup["tested"] if routine is None
                  else tested_recently(info_randoms["test_u"], np.broadcast_to(np.asarray(r, float), (n,))))

    st = start_state(banks, funding, tested, setup["placement"])
    # Option C's credit (zero under every other policy) and B / B' non-compliance (Amendment 3).
    st["credit_start_bn"] = setup["credit_bn"].copy()
    st["credit_left_bn"] = setup["credit_bn"].copy()
    st["non_compliant"] = setup["non_compliant"].copy()
    st["five_day_gap_bn"] = setup["five_day_unmet_bn"].copy()
    st["five_day_ratio_start"] = setup["five_day_ratio"].copy()
    _, steps = noise.shape
    st.update(agents=agents, behavior=behavior, noise=noise, decision_cfg=decision,
              shock=np.broadcast_to(np.asarray(shock, float), (n,)).copy(),
              confidence=np.ones((n, steps)), withdrawn_uninsured=np.zeros((n, steps)),
              stwf_start_bn=banks["stwf_bn"].copy())
    start_depositors(st, banks, agents)
    start_information(st, info, stigma,
                      info["routine_borrowing"]["strength_s"]["default"] if strength_s is None else strength_s,
                      r, info["supervisor"]["default_level"] if supervision is None else supervision,
                      info_randoms, routes_off, steps)
    if distress_shock is not None:
        st["distress_shock"] = np.broadcast_to(np.asarray(distress_shock, float), (n,)).copy()
    st["forced_draws"] = forced_draws or {}
    _start_tracking(st, decision, n)
    return st


def _start_tracking(st, cfg, n):
    """What the bank remembers between half-days, and what outcomes need (Clarification 10)."""
    end = cfg["end"]
    st["fail_tol_bn"] = end["failure_owed_share_of_assets"] * st["assets_start_bn"]
    st["calm_tol_bn"] = end["calm_outflow_share_of_assets"] * st["assets_start_bn"]
    st["last_outflow_bn"] = np.zeros(n)
    st["calm_streak"] = np.zeros(n, int)
    st["end_state"] = np.full(n, RUNNING)
    st["end_step"] = np.full(n, NEVER)
    st["first_shortfall_seen_step"] = np.full(n, NEVER)
    st["first_borrow_yes_step"] = np.full(n, NEVER)
    for k in ("peak_owed_bn", "peak_uncovered_bn", "dw_agreed_bn", "peak_fhlb_bn"):
        st[k] = np.zeros(n)


def _today_outflows(st, outflows):
    """What will actually leave this half-day (a line can't pay out more than it holds)."""
    n = len(st["bank_id"])
    return sum((np.minimum(np.broadcast_to(np.asarray(a, float), (n,)), st[line]) for line, a in outflows.items()),
               np.zeros(n))


def _check_end(st, t, rec, active):
    """Clarification 10: failure, stabilization, or (after the last step) day 30."""
    cfg = st["decision_cfg"]["end"]
    failed = (rec["unpaid_end"] > st["fail_tol_bn"]) | (st["equity_bn"] < 0)

    look = cfg["confidence_lookback_steps"]
    before = st["confidence"][:, t - look] if t >= look else np.ones(len(failed))   # calm before day 1
    news_pending = np.zeros(len(failed), bool)
    for route in BORROWING_ROUTES:
        news_pending |= (st["due"][route] != NEVER) & (st["due"][route] > t) & ~st["delivered"][route]
    calm = ((rec["outflow"] < st["calm_tol_bn"]) & (rec["unpaid_end"] < ONE_DOLLAR_BN)
            & (st["confidence"][:, t] >= before) & ~news_pending)
    st["calm_streak"] = np.where(calm, st["calm_streak"] + 1, 0)
    stabilized = ~failed & (st["calm_streak"] >= cfg["calm_steps"])

    for mask, state in ((failed, FAILED), (stabilized, STABILIZED)):
        now = active & mask & (st["end_state"] == RUNNING)
        st["end_state"] = np.where(now, state, st["end_state"])
        st["end_step"] = np.where(now, t, st["end_step"])
    if t == st["confidence"].shape[1] - 1:      # last half-day: whoever is still running reached the end
        now = st["end_state"] == RUNNING
        st["end_state"] = np.where(now, REACHED_END, st["end_state"])
        st["end_step"] = np.where(now, t, st["end_step"])


def episode_step(st):
    """Move every row forward one half-day; returns the record for this half-day."""
    t, agents, behavior = st["t"], st["agents"], st["behavior"]
    n = len(st["bank_id"])
    active = st["end_state"] == RUNNING        # rows whose episode has not ended

    deliver(st, t, "start")
    conf = confidence(st, t, agents, behavior)
    st["confidence"][:, t] = conf

    outflows = {}
    refused = np.zeros(n)
    if t % st["settings"]["time"]["steps_per_day"] == agents["lenders"]["decide_at_step_of_day"]:
        refused, outflows = morning_decisions(st, conf, agents, behavior)

    dep = withdrawals(st, t, agents, behavior)
    outflows["uninsured_deposits_bn"] = dep["fast"] + dep["slow"]
    outflows["insured_deposits_bn"] = dep["insured"]

    forced = np.zeros(n)
    if t in st["forced_draws"]:
        forced = sum(force_dw_draw(st, st["forced_draws"][t]).values())

    # The borrowing decision (M1.6). If yes, the window is open to the waterfall this
    # half-day, after private sources as always; then the bank asks for the rest of its
    # projected gap ahead of need (the request already counts private sources in time).
    today_out = _today_outflows(st, outflows)
    dec = decide(st, today_out, st["decision_cfg"])
    rec = step(st, outflows, dw_allowed=dec["borrow"])
    st["last_outflow_bn"] = rec["outflow"].copy()
    in_waterfall = sum(v for k, v in rec.items() if k.startswith("used_dw_"))
    asked = np.where(dec["borrow"], np.maximum(dec["request"] - in_waterfall, 0), 0.0)
    ahead_by = force_dw_draw(st, asked, t=t)   # step() has moved st["t"] on; the draw is today's
    ahead = sum(ahead_by.values())

    # Information: today's draws (forced, asked ahead, or by the waterfall), sales and refusals.
    drawn = forced + ahead + in_waterfall
    sold = rec["used_sale_level1"] + rec["used_sale_level2a"]
    refused_bn = sum(v for k, v in rec.items() if k.startswith("outflow_repo_out_") or k == "outflow_stwf_bn")
    observe(st, t, drawn, sold, np.zeros(n) + refused_bn)
    deliver(st, t, "end")
    # Contract 2d: Option C's credit falls by every dollar actually borrowed at the window.
    st["credit_left_bn"] = credit_after_draws(st["credit_start_bn"], st["dw_drawn_total_bn"])

    # What outcomes need, counted only while the row's episode is running.
    st["first_shortfall_seen_step"] = np.where(active & dec["shortfall_seen"] & (st["first_shortfall_seen_step"] == NEVER),
                                               t, st["first_shortfall_seen_step"])
    st["first_borrow_yes_step"] = np.where(active & dec["borrow"] & (st["first_borrow_yes_step"] == NEVER),
                                           t, st["first_borrow_yes_step"])
    for k, v in (("peak_owed_bn", rec["unpaid_end"]), ("peak_uncovered_bn", rec["shortfall"]),
                 ("dw_agreed_bn", st["dw_drawn_total_bn"]), ("peak_fhlb_bn", st["fhlb_advances_bn"])):
        st[k] = np.where(active, np.maximum(st[k], v), st[k])
    _check_end(st, t, rec, active)

    rec.update(confidence=conf, refusal_share=refused,
               fast_out=dep["fast"], slow_out=dep["slow"], insured_out=dep["insured"],
               fast_share=dep["fast_share"], slow_share=dep["slow_share"], insured_share=dep["insured_share"],
               repo_refused=rec.get("outflow_repo_out_level1_bn", np.zeros(n))
               + rec.get("outflow_repo_out_level2a_bn", np.zeros(n)),
               stwf_refused=rec.get("outflow_stwf_bn", np.zeros(n)),
               dw_drawn=drawn, dw_ahead=ahead, **{f"ahead_{k}": v for k, v in ahead_by.items()}, forced_draw=forced, market_knows=st["market_knows"].copy(),
               supervisor_knows=st["supervisor_knows"].copy(), distress_on=st["distress_from"] <= t,
               active=active, end_state=st["end_state"].copy(),
               **{f"decision_{k}": v for k, v in dec.items()})
    return rec


def run_episode(banks, shock, noise, stop_when_all_ended=False, **kwargs):
    """Run every half-day in `noise`; returns the final state and the list of records.

    With stop_when_all_ended, the loop stops once every row has failed or
    stabilized (results are unchanged: nothing after a row's end counts).
    """
    st = start_episode(banks, shock, noise, **kwargs)
    recs = []
    for _ in range(noise.shape[1]):
        recs.append(episode_step(st))
        if stop_when_all_ended and (st["end_state"] != RUNNING).all():
            break
    return st, recs
