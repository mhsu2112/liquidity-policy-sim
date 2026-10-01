"""Checks on depositors, wholesale and repo lenders (session M1.4).

Mechanics only, under policy A: bigger shocks drain faster, fast depositors
move before slow ones, insured depositors follow their fixed ratio, refusals
are repaid, repo lines hold, runs repeat exactly from a seed, balance sheets
balance, and rows computed together match rows computed alone. The behavioral
settings are M1.10 placeholders; no test depends on their values being "right".
"""

import numpy as np
import pytest

from agents.depositors import leave_share
from agents.lenders import refusal_share
from engine.balance_sheet import check_balances
from engine.banks import generate_banks
from engine.episode import draw_noise, episode_step, load_yaml, run_episode, start_episode
from engine.information import no_information_randoms

BANKS = generate_banks()
AGENTS = load_yaml("agents.yaml")
BEHAVIOR = load_yaml("behavior.yaml")
SCEN = load_yaml("scenarios/demo.yaml")
STEPS = 2 * SCEN["days"]
MILD, SEVERE = SCEN["shocks"]["mild"], SCEN["shocks"]["severe"]
NOISE = draw_noise(SCEN["seed"], 40, STEPS, AGENTS)
TOL = 1e-9
# From M1.6 every run supplies its random numbers up front. These tests model no information,
# so they supply "nothing leaks, nothing is read, collateral untested" explicitly (was the silent default).
NO_INFO = no_information_randoms


def run(shock, noise=NOISE, banks=BANKS, check=False):
    st = start_episode(banks, shock, noise, info_randoms=NO_INFO(len(banks["bank_id"])))
    recs = []
    for _ in range(noise.shape[1]):
        recs.append(episode_step(st))
        if check:
            check_balances(st)
    return st, recs


def cumulative(recs, key):
    return np.cumsum([r[key] for r in recs], axis=0)


@pytest.fixture(scope="module")
def mild():
    return run(MILD)


@pytest.fixture(scope="module")
def severe():
    return run(SEVERE)


# ---------------------------------------------------------------- depositors

def test_bigger_shock_faster_outflows(mild, severe):
    out_mild = cumulative(mild[1], "fast_out") + cumulative(mild[1], "slow_out")
    out_severe = cumulative(severe[1], "fast_out") + cumulative(severe[1], "slow_out")
    assert (out_severe >= out_mild - TOL).all()       # never behind, at any half-day, for any bank
    assert (out_severe[3] > out_mild[3]).all()        # ahead by the end of day 2


def test_no_shock_no_run():
    st, recs = run(0.0)
    assert all((r["confidence"] == 1).all() and (r["fast_out"] == 0).all() for r in recs)


def test_fast_depositors_leave_before_slow(severe):
    _, recs = severe
    lag = BEHAVIOR["slow_depositor_lag_steps"]["value"]
    for t in range(lag):
        assert (recs[t]["slow_out"] == 0).all()        # slow depositors cannot move before the lag
    assert (recs[0]["fast_share"] > recs[0]["slow_share"]).all()
    # After the lag, slow depositors respond to confidence `lag` half-days earlier.
    for t in range(lag, STEPS):
        np.testing.assert_allclose(recs[t]["slow_share"], leave_share(recs[t - lag]["confidence"], BEHAVIOR))


def test_insured_follow_their_ratio(severe):
    # Clarification 8: each half-day insured leave at 5% of the fast rate. (Over a long
    # panic this adds up; the size of that effect is reported in Clarification 8.)
    ratio = AGENTS["depositors"]["insured_rate_vs_fast"]
    for r in severe[1]:
        np.testing.assert_allclose(r["insured_share"], ratio * r["fast_share"])
        assert (r["insured_share"] <= ratio).all()       # never more than 5% in a half-day


def test_fast_and_slow_split_by_type():
    st = start_episode(BANKS, 0.0, NOISE, info_randoms=NO_INFO(40))
    for name, share in AGENTS["depositors"]["fast_share_of_uninsured"].items():
        rows = BANKS["archetype"] == name
        np.testing.assert_allclose(st["fast_uninsured_bn"][rows], share * BANKS["uninsured_deposits_bn"][rows])
    np.testing.assert_allclose(st["fast_uninsured_bn"] + st["slow_uninsured_bn"], BANKS["uninsured_deposits_bn"])


# ---------------------------------------------------------------- lenders

def test_refusal_share_band():
    theta, spread = BEHAVIOR["wholesale_roll_threshold"]["value"], AGENTS["lenders"]["cutoff_spread"]
    conf = np.array([1.0, theta + spread, theta, theta - spread, 0.0])
    np.testing.assert_allclose(refusal_share(conf, AGENTS, BEHAVIOR), [0, 0, 0.5, 1, 1])


def test_refusals_trigger_repayment(mild):
    st0 = start_episode(BANKS, MILD, NOISE, info_randoms=NO_INFO(40))
    st = start_episode(BANKS, MILD, NOISE, info_randoms=NO_INFO(40))
    daily = AGENTS["lenders"]["stwf_maturing_share_per_day"] * BANKS["stwf_bn"]
    refused_any = False
    for t in range(STEPS):
        repo_before = {c: st[f"repo_out_{c}_bn"].copy() for c in ("level1", "level2a")}
        pledged_before = {c: st[f"repo_pledged_mv_{c}_bn"].copy() for c in ("level1", "level2a")}
        stwf_before = st["stwf_bn"].copy()
        r = episode_step(st)
        if t % 2:  # lenders decide only in the morning
            assert (r["refusal_share"] == 0).all() and (r["repo_refused"] == 0).all()
            continue
        share = r["refusal_share"]
        refused_any |= (share > 0).any()
        # Unsecured: the refused share of what matures today is repaid through the waterfall.
        np.testing.assert_allclose(r["stwf_refused"], share * np.minimum(daily, stwf_before), atol=TOL)
        for c in ("level1", "level2a"):
            # Repo is overnight: the refused share of the whole book is repaid ...
            repaid = r.get(f"outflow_repo_out_{c}_bn", 0 * share)
            np.testing.assert_allclose(repaid, share * repo_before[c], atol=TOL)
            # ... and exactly its collateral comes back (cash / (1 - haircut)).
            h = st["settings"]["repo"]["haircuts"][c]
            new = r[f"used_repo_{c}"] / (1 - h) + r[f"used_repo_next_{c}"] / (1 - h)
            np.testing.assert_allclose(st[f"repo_pledged_mv_{c}_bn"],
                                       pledged_before[c] - repaid / (1 - h) + new, atol=1e-8)
        # Repayments are outflows the waterfall must fund: they count toward what is owed.
        assert (r["outflow"] >= r["stwf_refused"] + r["repo_refused"] - TOL).all()
        # Lenders above their cut-off band refuse nothing.
        calm = r["confidence"] >= BEHAVIOR["wholesale_roll_threshold"]["value"] + AGENTS["lenders"]["cutoff_spread"]
        assert (share[calm] == 0).all()
    assert refused_any
    assert (st["stwf_bn"] <= st0["stwf_bn"] + TOL).all()


def test_repo_lines_respected(mild, severe):
    lines = np.array([load_yaml("funding.yaml")["repo"]["same_day_line_share_of_assets"][a]
                      for a in BANKS["archetype"]]) * BANKS["total_assets_bn"]
    for st, recs in (mild, severe):
        same_day = sum(r["used_repo_level1"] + r["used_repo_level2a"] for r in recs)
        assert (same_day <= lines + TOL).all()
        for t, r in enumerate(recs):
            # New repo only from lenders still willing (Clarification 8): none on a
            # morning when every lender refuses.
            if t % 2 == 0:
                all_refuse = r["refusal_share"] == 1
                for k in ("repo_level1", "repo_level2a", "repo_next_level1", "repo_next_level2a"):
                    assert (r[f"used_{k}"][all_refuse] == 0).all()
            # Next-day repo arrives exactly two half-days later.
            if t + 2 < len(recs):
                for c in ("level1", "level2a"):
                    np.testing.assert_allclose(recs[t + 2][f"arrived_repo_next_{c}"], r[f"used_repo_next_{c}"])


# ---------------------------------------------------------------- reproducibility and structure

def test_same_seed_same_result():
    a = run(SEVERE, draw_noise(SCEN["seed"], 40, STEPS, AGENTS))
    b = run(SEVERE, draw_noise(SCEN["seed"], 40, STEPS, AGENTS))
    c = run(SEVERE, draw_noise(SCEN["seed"] + 1, 40, STEPS, AGENTS))
    for k in ("uninsured_deposits_bn", "equity_bn", "unpaid_outflows_bn", "repo_bn", "confidence"):
        np.testing.assert_array_equal(a[0][k], b[0][k])
    assert not np.array_equal(a[0]["confidence"], c[0]["confidence"])


@pytest.mark.parametrize("shock", [MILD, SEVERE])
def test_balance_sheets_balance(shock):
    run(shock, check=True)  # check_balances raises if any row is out by $1 or more


def test_all_rows_together_equal_each_row_alone():
    # 40 banks x 2 shocks in one batch, against each row run on its own with its own draws.
    rows = {k: (np.tile(v, 2) if isinstance(v, np.ndarray) else v) for k, v in BANKS.items()}
    noise = np.tile(NOISE, (2, 1))
    shock = np.repeat([MILD, SEVERE], 40)
    together, _ = run_episode(rows, shock, noise, info_randoms=NO_INFO(80))
    for i in range(80):
        one = {k: (v[[i]] if isinstance(v, np.ndarray) else v) for k, v in rows.items()}
        alone, _ = run_episode(one, shock[[i]], noise[[i]], info_randoms=NO_INFO(1))
        for k in ("uninsured_deposits_bn", "insured_deposits_bn", "stwf_bn", "repo_bn", "equity_bn",
                  "unpaid_outflows_bn", "reserves_bn"):
            assert alone[k][0] == together[k][i], (i, k)
        np.testing.assert_array_equal(alone["confidence"][0], together["confidence"][i])
