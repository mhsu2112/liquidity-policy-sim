"""Checks on the borrowing decision, the discount window and end conditions (session M1.6).

Mechanics only, under policy A for every episode: the rule is monotone in its
costs, the window lends with the contract's lags, each end condition fires when
and only when its test is met, random numbers must be supplied, runs repeat
from a seed, balance sheets balance and rows run together equal rows run alone.
No test says any setting or policy does better or worse. Behavioral settings
are M1.10 placeholders; no test depends on their values being "right".
"""

import inspect

import numpy as np
import pytest

import agents.bank as bank
from engine.balance_sheet import check_balances
from engine.banks import generate_banks
from engine.episode import (FAILED, REACHED_END, RUNNING, STABILIZED, _check_end, draw_noise, episode_step,
                            load_yaml, run_episode, start_episode)
from engine.information import NEVER, draw_info_randoms, load_information_settings, no_information_randoms
from engine.information import tested_recently as is_tested   # renamed so pytest doesn't take it for a test
from engine.outcomes import episode_outcomes

BANKS = generate_banks()
AGENTS = load_yaml("agents.yaml")
INFO = load_information_settings()
DECISION = load_yaml("decision.yaml")
SEED = 20261001
STEPS = 60                                     # contract 7: 30 days of two half-days
SHOCKS = (0.05, 0.15, 0.40)                    # the M1.4 demo shocks plus a small one; mechanics only
LEVELS = list(INFO["supervisor"]["levels"])    # strongly penalizes ... strongly encourages


def tile(banks, m):
    """All banks, repeated m times (block by block)."""
    return {k: (np.tile(v, m) if isinstance(v, np.ndarray) else v) for k, v in banks.items()}


def batch(shock, stigma, supervision, banks=BANKS, seed=SEED, **kw):
    """Every bank under each (stigma, supervision) pair in one batch; a bank sees the same draws in every pair."""
    n, m = len(banks["bank_id"]), len(stigma)
    noise = np.tile(draw_noise(seed, n, STEPS, AGENTS), (m, 1))
    rnd = {k: np.tile(v, m) for k, v in draw_info_randoms(seed, n).items()}
    return run_episode(tile(banks, m), shock, noise, info_randoms=rnd, stigma=np.repeat(stigma, n),
                       supervision=np.repeat(np.array(supervision, object), n), **kw)


# ---------------------------------------------------------------- the rule

@pytest.mark.parametrize("shock", SHOCKS)
def test_higher_costs_never_borrow_sooner(shock):
    # Every bank, every stigma grid point x every supervisory level, in one batch.
    grid = INFO["market_stigma"]["grid"]
    pairs = [(s, lv) for s in grid for lv in LEVELS]
    st, _ = batch(shock, [p[0] for p in pairs], [p[1] for p in pairs])
    n = len(BANKS["bank_id"])
    first = st["first_draw_step"].reshape(len(grid), len(LEVELS), n)
    # Stigma rises down axis 0; supervisory cost falls along axis 1 (levels run penalizes -> encourages).
    assert (np.diff(first, axis=0) >= 0).all()          # more stigma: never sooner
    assert (np.diff(first, axis=1) <= 0).all()          # less supervisory cost: never later
    # The check is not empty: banks do borrow. Since Amendment 2 (session M1.6b) no bank borrows under the
    # small shock (confidence stays above the tolerance level), so the guard applies only where borrowing happens.
    # Since params-frozen (M1.10) that is only the 0.40 shock (owner approved).
    if shock >= 0.40:
        assert (first < NEVER).any()


def test_window_closed_when_the_rule_says_wait():
    _, recs = batch(0.15, [0.9], ["strongly_penalizes"])
    for r in recs:
        wait = ~r["decision_borrow"]
        for k in r:
            if k.startswith("used_dw_") or k.startswith("ahead_"):
                assert (r[k][wait] == 0).all(), k
        assert (r["dw_ahead"][wait] == 0).all()


def test_normal_curve_hand_values():
    np.testing.assert_allclose(bank.normal_cdf(np.array([0.0, 1.6448536, -1.959964, 40.0, -40.0])),
                               [0.5, 0.95, 0.025, 1.0, 0.0], atol=2e-7)


def test_p_fail_matches_hand_formula():
    # One calm SVB-01 row, then a projection with a stated outflow: P = 1 - Phi(min over k of room / (sd x future)).
    i = int(np.flatnonzero(BANKS["bank_id"] == "SVB-01")[0])
    one = {k: (v[[i]] if isinstance(v, np.ndarray) else v) for k, v in BANKS.items()}
    st = start_episode(one, 0.0, draw_noise(SEED, 1, STEPS, AGENTS), info_randoms=no_information_randoms(1))
    p = DECISION["projection"]
    today = np.array([5.0])
    proj = bank.project(st, today, DECISION)
    room = [bank.cash_in_time(st, k)[0] + st["fail_tol_bn"][0] - today[0] - k * today[0]
            for k in range(p["horizon_steps"])]
    assert room[0] >= 0                                  # today alone can be met, so P is not certain
    z = min(room[k] / (p["forecast_sd"] * k * today[0]) for k in range(1, p["horizon_steps"]))
    assert proj["p_fail"][0] == pytest.approx(1 - bank.normal_cdf(z), abs=1e-12)
    # If today alone can't be met on time, failure without the window is certain.
    too_much = bank.cash_in_time(st, 0)[0] + st["fail_tol_bn"][0] + 1.0
    assert bank.project(st, np.array([too_much]), DECISION)["p_fail"][0] == 1.0


def test_chance_known_follows_the_routes():
    i = int(np.flatnonzero(BANKS["bank_id"] == "SVB-01")[0])
    one = {k: (v[[i]] if isinstance(v, np.ndarray) else v) for k, v in BANKS.items()}
    st = start_episode(one, 0.0, draw_noise(SEED, 1, STEPS, AGENTS), info_randoms=no_information_randoms(1),
                       stigma=0.5)
    thr = INFO["routes"]["announcement"]["materiality_share_of_assets"] * st["assets_start_bn"][0]
    leak = INFO["routes"]["leak"]["probability"]
    small, big = np.array([0.5 * thr]), np.array([1.01 * thr])
    assert bank.chance_known(st, big)[0] == 1.0                                       # the 8-K names it
    assert bank.chance_known(st, small)[0] == pytest.approx(leak + (1 - leak) * st["weekly_revealing"][0])
    st["first_draw_step"][:] = 0                                                      # already borrowed once
    assert bank.chance_known(st, small)[0] == 0.0
    st["distress_from"][:] = 0                                                        # already read as distress
    assert bank.decide(st, np.array([1.0]), DECISION)["stigma_cost"][0] == 0.0


def test_no_policy_enters_the_decision():
    for fn in (bank.decide, bank.project, bank.chance_known, bank.cash_in_time, start_episode, episode_step):
        assert "policy" not in inspect.signature(fn).parameters, fn.__name__


def test_amendment_1_grid_in_config():
    ms = INFO["market_stigma"]
    assert ms["distress_news_shock_grid"] == [0.10, 0.25, 0.40] and ms["distress_news_shock"] == 0.25


# ---------------------------------------------------------------- the window

CONTRACT_DW_LAGS = {"dw_tested": 0, "dw_untested": 2, "dw_level1": 2, "dw_level2a": 2, "dw_unpledged": 20}


@pytest.mark.parametrize("tested", [False, True])
def test_window_cash_arrives_with_the_contract_lag(tested):
    n = len(BANKS["bank_id"])
    noise = draw_noise(SEED, n, STEPS, AGENTS)
    st = start_episode(BANKS, 0.4, noise, info_randoms=draw_info_randoms(SEED, n), tested=np.full(n, tested),
                       supervision="strongly_encourages")
    recs = [episode_step(st) for _ in range(STEPS)]
    assert st["lags"] == {**st["lags"], **CONTRACT_DW_LAGS}
    seen = 0
    for t, r in enumerate(recs):
        for s, lag in CONTRACT_DW_LAGS.items():
            sent = r[f"used_{s}"] + r.get(f"ahead_{s}", 0.0)
            seen += (sent > 0).sum()
            if lag == 0:
                assert (r[f"arrived_{s}"] == 0).all()   # same half-day cash is booked at once, never "arriving"
            elif t + lag < STEPS:
                np.testing.assert_allclose(recs[t + lag][f"arrived_{s}"], sent, atol=1e-12)
    assert seen > 0
    if not tested:
        assert all((r["used_dw_tested"] == 0).all() and (r["ahead_dw_tested"] == 0).all() for r in recs)


def test_tested_share_matches_r():
    u = draw_info_randoms(SEED, 100_000)["test_u"]
    for r in (0.1, 1.0, 2.5):
        assert is_tested(u, r).mean() == pytest.approx(1 - np.exp(-r), abs=0.005)
    # The same number under every policy: tested at r = 0.1 means tested at any higher r.
    assert (is_tested(u, 1.0) | ~is_tested(u, 0.1)).all()


def test_tested_drawn_up_front_from_r():
    n = 40
    rnd = draw_info_randoms(SEED, n)
    st = start_episode(BANKS, 0.0, draw_noise(SEED, n, 2, AGENTS), info_randoms=rnd)
    np.testing.assert_array_equal(st["tested"], rnd["test_u"] < 1 - np.exp(-INFO["routine_borrowing"]["rate_by_policy"]["A"]))


# ---------------------------------------------------------------- end conditions

def calm_state(n=1):
    i = int(np.flatnonzero(BANKS["bank_id"] == "SVB-01")[0])
    one = {k: (np.repeat(v[i:i + 1], n) if isinstance(v, np.ndarray) else v) for k, v in BANKS.items()}
    return start_episode(one, 0.0, draw_noise(SEED, n, STEPS, AGENTS), info_randoms=no_information_randoms(n))


def fake_rec(st, owed=0.0, outflow=0.0):
    n = len(st["bank_id"])
    return {"unpaid_end": np.full(n, owed), "outflow": np.full(n, outflow)}


def test_failure_on_owed_above_tolerance_only():
    st = calm_state(2)
    tol = st["fail_tol_bn"][0]
    rec = {"unpaid_end": np.array([1.01 * tol, 0.99 * tol]), "outflow": np.zeros(2)}
    _check_end(st, 10, rec, np.ones(2, bool))
    assert list(st["end_state"]) == [FAILED, RUNNING] and st["end_step"][0] == 10


def test_failure_on_negative_equity():
    st = calm_state(2)
    st["equity_bn"][0] = -0.01
    _check_end(st, 3, fake_rec(st), np.ones(2, bool))
    assert list(st["end_state"]) == [FAILED, RUNNING]


def test_stabilizes_after_six_calm_half_days_only():
    st = calm_state()
    calm_n = DECISION["end"]["calm_steps"]
    for t in range(calm_n - 1):
        _check_end(st, t, fake_rec(st), np.ones(1, bool))
    assert st["end_state"][0] == RUNNING
    _check_end(st, calm_n - 1, fake_rec(st, outflow=2 * st["calm_tol_bn"][0]), np.ones(1, bool))   # not calm: resets
    assert st["end_state"][0] == RUNNING and st["calm_streak"][0] == 0
    for t in range(calm_n, 2 * calm_n):
        _check_end(st, t, fake_rec(st), np.ones(1, bool))
    assert st["end_state"][0] == STABILIZED and st["end_step"][0] == 2 * calm_n - 1


def test_no_stabilization_while_news_pending_or_confidence_falling():
    st = calm_state(2)
    st["due"]["announcement"][0] = 100                  # an 8-K still to be filed
    st["confidence"][1, :] = 1.0
    st["confidence"][1, 6:] = 0.99                      # below its level three days earlier
    for t in range(6, 6 + DECISION["end"]["calm_steps"]):
        _check_end(st, t, fake_rec(st), np.ones(2, bool))
    assert list(st["end_state"]) == [RUNNING, RUNNING]


def test_calm_bank_stabilizes_on_day_3_and_others_reach_the_end():
    n = len(BANKS["bank_id"])
    st, _ = run_episode(BANKS, 0.0, draw_noise(SEED, n, STEPS, AGENTS), info_randoms=draw_info_randoms(SEED, n))
    o = episode_outcomes(st)
    assert (st["end_state"] == STABILIZED).all() and (o["end_day"] == 3).all()
    st2 = calm_state()
    _check_end(st2, STEPS - 1, fake_rec(st2, outflow=1.0), np.ones(1, bool))   # still running on the last half-day
    assert st2["end_state"][0] == REACHED_END and st2["end_step"][0] == STEPS - 1


def test_nothing_after_the_end_counts():
    st, recs = batch(0.40, [0.35], ["neutral"])
    o = episode_outcomes(st)
    failed = st["end_state"] == FAILED
    assert failed.any()
    for j in np.flatnonzero(failed):
        e = st["end_step"][j]
        assert o["peak_owed_bn"][j] == pytest.approx(max(r["unpaid_end"][j] for r in recs[:e + 1]))
        assert o["official_support_bn"][j] == pytest.approx(sum(r["dw_drawn"][j] for r in recs[:e + 1]))


# ---------------------------------------------------------------- random numbers, repeatability, balance

def test_run_without_random_numbers_raises():
    with pytest.raises(ValueError, match="random numbers"):
        start_episode(BANKS, 0.1, draw_noise(SEED, 40, 4, AGENTS))
    with pytest.raises(ValueError, match="test_u"):
        start_episode(BANKS, 0.1, draw_noise(SEED, 40, 4, AGENTS),
                      info_randoms={"leak_u": np.ones(40), "read_u": np.ones(40)})
    start_episode(BANKS, 0.1, draw_noise(SEED, 40, 4, AGENTS), demo=True)   # demos may


def test_same_seed_same_result():
    a = episode_outcomes(batch(0.15, [0.35], ["neutral"])[0])
    b = episode_outcomes(batch(0.15, [0.35], ["neutral"])[0])
    c = episode_outcomes(batch(0.15, [0.35], ["neutral"], seed=SEED + 1)[0])
    for k in a:
        np.testing.assert_array_equal(a[k], b[k])
    assert not all(np.array_equal(a[k], c[k]) for k in a)


@pytest.mark.parametrize("shock", SHOCKS)
def test_balance_sheets_balance_every_half_day(shock):
    n = len(BANKS["bank_id"])
    st = start_episode(BANKS, shock, draw_noise(SEED, n, STEPS, AGENTS), info_randoms=draw_info_randoms(SEED, n),
                       stigma=0.35)
    for _ in range(STEPS):
        episode_step(st)
        check_balances(st)


def test_rows_together_equal_rows_alone():
    pairs = [(0.1, "encourages"), (0.9, "penalizes")]
    together, _ = batch(0.15, [p[0] for p in pairs], [p[1] for p in pairs])
    to = episode_outcomes(together)
    n = len(BANKS["bank_id"])
    noise, rnd = draw_noise(SEED, n, STEPS, AGENTS), draw_info_randoms(SEED, n)
    for j in range(0, 2 * n, 7):                         # a spread of rows, each run on its own
        i, (sig, sup) = j % n, pairs[j // n]
        one = {k: (v[[i]] if isinstance(v, np.ndarray) else v) for k, v in BANKS.items()}
        alone, _ = run_episode(one, 0.15, noise[[i]], info_randoms={k: v[[i]] for k, v in rnd.items()},
                               stigma=sig, supervision=sup)
        ao = episode_outcomes(alone)
        for k in to:
            np.testing.assert_array_equal(ao[k][0], to[k][j], err_msg=f"{k} row {j}")
