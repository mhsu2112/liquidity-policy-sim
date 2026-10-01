"""One episode, half-day by half-day: behavior feeding the funding waterfall (session M1.4).

Each half-day, for every row at once (a row is one bank in one run):
  1. depositors and lenders judge confidence;
  2. in the morning, wholesale and repo lenders roll or refuse;
  3. fast, slow and insured depositors withdraw;
  4. every outflow and repayment goes through the funding waterfall.

Policy A only. No supervisor, information routes, borrowing decision or end
conditions yet (sessions M1.5 and M1.6).
"""

from pathlib import Path

import numpy as np
import yaml

from agents.depositors import confidence, start_depositors, withdrawals
from agents.lenders import morning_decisions
from engine.funding import load_funding_settings, start_state, step

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


def start_episode(banks, shock, noise, funding=None, agents=None, behavior=None, tested=None):
    funding = funding or load_funding_settings()
    agents = agents or load_yaml("agents.yaml")
    behavior = behavior or load_yaml("behavior.yaml")
    st = start_state(banks, funding, tested)
    n, steps = noise.shape
    st.update(agents=agents, behavior=behavior, noise=noise,
              shock=np.broadcast_to(np.asarray(shock, float), (n,)).copy(),
              confidence=np.ones((n, steps)), withdrawn_uninsured=np.zeros((n, steps)),
              stwf_start_bn=banks["stwf_bn"].copy())
    start_depositors(st, banks, agents)
    return st


def episode_step(st):
    """Move every row forward one half-day; returns the record for this half-day."""
    t, agents, behavior = st["t"], st["agents"], st["behavior"]
    n = len(st["bank_id"])

    conf = confidence(st, t, agents, behavior)
    st["confidence"][:, t] = conf

    outflows = {}
    refused = np.zeros(n)
    if t % st["settings"]["time"]["steps_per_day"] == agents["lenders"]["decide_at_step_of_day"]:
        refused, outflows = morning_decisions(st, conf, agents, behavior)

    dep = withdrawals(st, t, agents, behavior)
    outflows["uninsured_deposits_bn"] = dep["fast"] + dep["slow"]
    outflows["insured_deposits_bn"] = dep["insured"]

    rec = step(st, outflows)
    rec.update(confidence=conf, refusal_share=refused,
               fast_out=dep["fast"], slow_out=dep["slow"], insured_out=dep["insured"],
               fast_share=dep["fast_share"], slow_share=dep["slow_share"], insured_share=dep["insured_share"],
               repo_refused=rec.get("outflow_repo_out_level1_bn", np.zeros(n))
               + rec.get("outflow_repo_out_level2a_bn", np.zeros(n)),
               stwf_refused=rec.get("outflow_stwf_bn", np.zeros(n)))
    return rec


def run_episode(banks, shock, noise, **kwargs):
    """Run every half-day in `noise`; returns the final state and the list of records."""
    st = start_episode(banks, shock, noise, **kwargs)
    return st, [episode_step(st) for _ in range(noise.shape[1])]
