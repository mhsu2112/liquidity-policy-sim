"""One episode, half-day by half-day: behavior feeding the funding waterfall (session M1.4).

Each half-day, for every row at once (a row is one bank in one run):
  1. observers receive the information events due now (session M1.5);
  2. depositors and lenders judge confidence;
  3. in the morning, wholesale and repo lenders roll or refuse;
  4. fast, slow and insured depositors withdraw;
  5. a forced discount window draw, if the caller asked for one (demo only);
  6. every outflow and repayment goes through the funding waterfall;
  7. what happened (draws, sales, refusals) schedules new information events,
     and same-half-day events are delivered.

Policy A only. No borrowing decision or end conditions yet (session M1.6).
"""

from pathlib import Path

import numpy as np
import yaml

from agents.depositors import confidence, start_depositors, withdrawals
from agents.lenders import morning_decisions
from engine.funding import force_dw_draw, load_funding_settings, start_state, step
from engine.information import deliver, load_information_settings, observe, routine_rate, start_information

CONFIG = Path(__file__).resolve().parent.parent / "config"


def load_yaml(name):
    with open(CONFIG / name) as f:
        return yaml.safe_load(f)


def draw_noise(seed, rows, steps, agents):
    """All random draws for an episode, made up front: one row per run, one column per half-day.

    Drawing them first means every policy sees exactly the same draws (paired runs),
    and any single row can be re-run alone with its own draws.
    """
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, agents["confidence"]["news_noise_sd"], size=(rows, steps))


def start_episode(banks, shock, noise, funding=None, agents=None, behavior=None, tested=None,
                  info=None, stigma=0.0, strength_s=None, routine=None, supervision=None,
                  info_randoms=None, routes_off=(), forced_draws=None):
    """Set up every row. Information options (session M1.5), one value or one per row:

    stigma        market stigma, the chance a known draw is read as distress (contract 5 grid;
                  0 = none, which keeps M1.4 callers unchanged)
    strength_s    routine-borrowing effect strength s (default: config/information.yaml)
    routine       routine borrowing rate r (default: policy A's, contract 3a)
    supervision   supervisor dial level (default: config/information.yaml)
    info_randoms  from engine.information.draw_info_randoms; shared by every policy
    routes_off    route names to switch off (tests only)
    forced_draws  {step: $bn per row}: discount window draws forced at that step (demo only;
                  the bank's own decision comes in M1.6)
    """
    funding = funding or load_funding_settings()
    info = info or load_information_settings()
    agents = agents or load_yaml("agents.yaml")
    behavior = behavior or load_yaml("behavior.yaml")
    st = start_state(banks, funding, tested)
    n, steps = noise.shape
    st.update(agents=agents, behavior=behavior, noise=noise,
              shock=np.broadcast_to(np.asarray(shock, float), (n,)).copy(),
              confidence=np.ones((n, steps)), withdrawn_uninsured=np.zeros((n, steps)),
              stwf_start_bn=banks["stwf_bn"].copy())
    start_depositors(st, banks, agents)
    start_information(st, info, stigma,
                      info["routine_borrowing"]["strength_s"]["default"] if strength_s is None else strength_s,
                      routine_rate("A", info) if routine is None else routine,
                      info["supervisor"]["default_level"] if supervision is None else supervision,
                      info_randoms, routes_off, steps)
    st["forced_draws"] = forced_draws or {}
    return st


def episode_step(st):
    """Move every row forward one half-day; returns the record for this half-day."""
    t, agents, behavior = st["t"], st["agents"], st["behavior"]
    n = len(st["bank_id"])

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

    rec = step(st, outflows)

    # Information: today's draws (forced or by the waterfall), sales and refusals.
    drawn = forced + sum(v for k, v in rec.items() if k.startswith("used_dw_"))
    sold = rec["used_sale_level1"] + rec["used_sale_level2a"]
    refused_bn = sum(v for k, v in rec.items() if k.startswith("outflow_repo_out_") or k == "outflow_stwf_bn")
    observe(st, t, drawn, sold, np.zeros(n) + refused_bn)
    deliver(st, t, "end")
    rec.update(confidence=conf, refusal_share=refused,
               fast_out=dep["fast"], slow_out=dep["slow"], insured_out=dep["insured"],
               fast_share=dep["fast_share"], slow_share=dep["slow_share"], insured_share=dep["insured_share"],
               repo_refused=rec.get("outflow_repo_out_level1_bn", np.zeros(n))
               + rec.get("outflow_repo_out_level2a_bn", np.zeros(n)),
               stwf_refused=rec.get("outflow_stwf_bn", np.zeros(n)),
               dw_drawn=drawn, forced_draw=forced, market_knows=st["market_knows"].copy(),
               supervisor_knows=st["supervisor_knows"].copy(), distress_on=st["distress_from"] <= t)
    return rec


def run_episode(banks, shock, noise, **kwargs):
    """Run every half-day in `noise`; returns the final state and the list of records."""
    st = start_episode(banks, shock, noise, **kwargs)
    return st, [episode_step(st) for _ in range(noise.shape[1])]
