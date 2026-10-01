"""Checks on the information routes and the supervisor's dial (session M1.5).

Mechanics only, under policy A for every episode: nobody learns anything except
through a route; routes fire when and as often as the rules say; the contract
3a formulas hold exactly; the stigma link takes no policy; runs repeat from a
seed; rows run together equal rows run alone. No test says any setting is
better or worse than another. Other policies appear only in static
calculations of r (no stress episode), as CLAUDE.md rule 2 allows.
"""

import copy
import inspect

import numpy as np
import pytest

import agents.supervisor as supervisor
import engine.information as information
from engine.balance_sheet import check_balances
from engine.banks import generate_banks
from engine.episode import draw_noise, episode_step, load_yaml, start_episode
from engine.information import (NEVER, draw_info_randoms, effective_stigma, load_information_settings,
                                read_as_distress, weekly_act_step, weekly_revealing)
from engine.policies import routine_rate   # moved here from engine.information in M1.7b (Clarification 12 item 8)

BANKS = generate_banks()
AGENTS = load_yaml("agents.yaml")
INFO = load_information_settings()
SEED = 20261001
I_SVB = int(np.flatnonzero(BANKS["bank_id"] == "SVB-01")[0])
ALL_ROUTES = information.BORROWING_ROUTES + ("inference", "ratio_disclosure")
SPD = 2


def svb(n):
    return {k: (np.repeat(v[I_SVB:I_SVB + 1], n) if isinstance(v, np.ndarray) else v) for k, v in BANKS.items()}


def run(n=1, steps=24, shock=0.0, info=None, draw_at=2, draw_bn=6.0, randoms=None, **kw):
    """SVB-01 copies, calm unless a shock is given, with a forced draw (None = no draw)."""
    noise = np.repeat(draw_noise(SEED, 1, steps, AGENTS), n, axis=0)
    forced = {} if draw_at is None else {draw_at: draw_bn}
    # From M1.6 a run must supply its random numbers; "nothing leaks, nothing is read" was the silent default.
    randoms = ones(n) if randoms is None else randoms
    st = start_episode(svb(n), shock, noise, info=info, forced_draws=forced, info_randoms=randoms, **kw)
    recs = []
    for _ in range(steps):
        recs.append(episode_step(st))
        check_balances(st)
    return st, recs


def ones(n):
    return {"leak_u": np.ones(n), "read_u": np.ones(n), "test_u": np.ones(n)}   # test_u = 1: untested (M1.6)


def zeros(n):
    return {"leak_u": np.zeros(n), "read_u": np.zeros(n), "test_u": np.ones(n)}


def events(st, route, row=0):
    return [ev for ev in st["events"] if ev["route"] == route and ev["mask"][row]]


# ---------------------------------------------------------------- no information without a route

def test_no_information_without_a_route():
    # Every route off, the most stigma possible, and every random number set to trigger.
    st, recs = run(routes_off=ALL_ROUTES, stigma=0.9, randoms=zeros(1))
    assert st["dw_drawn_total_bn"][0] == pytest.approx(6.0)          # the draw did happen
    assert st["events"] == []
    assert not st["supervisor_knows"].any() and (st["market_knows"] == 0).all()
    assert (st["distress_from"] == NEVER).all()
    _, calm = run(draw_at=None, stigma=0.9, randoms=zeros(1))
    np.testing.assert_array_equal([r["confidence"] for r in recs], [r["confidence"] for r in calm])


def test_knowledge_changes_only_with_an_event():
    noise = draw_noise(SEED, 1, 24, AGENTS)
    st = start_episode(svb(1), 0.0, noise, stigma=0.9, info_randoms=zeros(1), forced_draws={2: 6.0})
    for t in range(24):
        before = (st["market_knows"].copy(), st["supervisor_knows"].copy(), st["distress_from"].copy())
        episode_step(st)
        here = {(ev["route"], ev["observer"]) for ev in st["events"] if ev["t"] == t}
        if st["market_knows"][0] != before[0][0] or st["distress_from"][0] != before[2][0]:
            assert any(o == "market" for _, o in here)
        if st["supervisor_knows"][0] != before[1][0]:
            assert ("supervisory", "supervisor") in here


def test_nothing_known_before_the_draw():
    st, _ = run(draw_at=6, stigma=0.9, randoms=zeros(1))
    first = min(ev["t"] for ev in st["events"] if not ev["route"].startswith(("inference", "ratio")))
    assert first == 6
    assert events(st, "supervisory")[0]["t"] == 6                    # supervisor: same half-day


# ---------------------------------------------------------------- leak

def test_leak_probability():
    n = 100_000
    st, _ = run(n=n, steps=4, draw_at=0, randoms=draw_info_randoms(SEED, n))
    share = st["delivered"]["leak"].mean()
    assert share == pytest.approx(INFO["routes"]["leak"]["probability"], abs=0.006)   # ~5 standard errors
    np.testing.assert_array_equal(st["delivered"]["leak"], st["leak_u"] < INFO["routes"]["leak"]["probability"])


@pytest.mark.parametrize("lag_days", [0, 1, 5])
def test_leak_lands_exactly_lag_days_after_first_draw(lag_days):
    info = copy.deepcopy(INFO)
    info["routes"]["leak"]["lag_days"] = lag_days
    st, _ = run(info=info, steps=20, draw_at=3, randoms=zeros(1))
    (ev,) = events(st, "leak")                                        # once, and only once
    assert ev["t"] == 3 + SPD * lag_days


def test_leak_probability_zero_never_leaks():
    info = copy.deepcopy(INFO)
    info["routes"]["leak"]["probability"] = 0.0
    st, _ = run(info=info, randoms=zeros(1))
    assert events(st, "leak") == []


# ---------------------------------------------------------------- weekly aggregate

def test_weekly_reveals_less_when_r_is_high():
    r = np.array([0.0, 0.1, 0.5, 1.0, 2.5, 5.0])
    w = weekly_revealing(r, INFO)
    assert (np.diff(w) < 0).all() and w[0] == 1.0
    wk = INFO["routes"]["weekly_aggregate"]
    np.testing.assert_allclose(w, 1 / (1 + r * wk["banks_in_system"] / wk["weeks_per_quarter"]))


def test_weekly_timing():
    # Day 1 = Monday. A draw through Wednesday (step 5) is in Thursday's report, acted on Friday morning (step 8).
    # A draw on Thursday (step 6) waits for the next Thursday's report (day 11), acted on day 12 morning (step 22).
    np.testing.assert_array_equal(weekly_act_step(np.array([0, 2, 5, 6, 19]), INFO, SPD), [8, 8, 8, 22, 22])
    st, _ = run(draw_at=2, randoms=ones(1))
    assert events(st, "weekly_aggregate")[0]["t"] == 8


# ---------------------------------------------------------------- announcement

def test_announcement_only_when_material_and_after_four_days():
    assets = BANKS["total_assets_bn"][I_SVB]
    thr = INFO["routes"]["announcement"]["materiality_share_of_assets"] * assets
    st, _ = run(draw_bn=0.9 * thr, steps=30, randoms=ones(1))
    assert events(st, "announcement") == []
    st, _ = run(draw_bn=1.1 * thr, steps=30, randoms=ones(1))
    assert events(st, "announcement")[0]["t"] == 2 + SPD * INFO["routes"]["announcement"]["filing_lag_days"]
    # Two draws that cross the threshold together: the clock starts at the second.
    noise = draw_noise(SEED, 1, 30, AGENTS)
    st = start_episode(svb(1), 0.0, noise, info_randoms=ones(1), forced_draws={0: 0.6 * thr, 4: 0.6 * thr})
    for _ in range(30):
        episode_step(st)
    assert events(st, "announcement")[0]["t"] == 4 + SPD * INFO["routes"]["announcement"]["filing_lag_days"]


# ---------------------------------------------------------------- contract 3a formulas

def test_effective_stigma_and_supervisory_cost_follow_section_3a():
    r = np.array([0.0, 0.1, 1.0, 2.5])
    for s in INFO["routine_borrowing"]["strength_s"]["grid"]:
        for sigma in INFO["market_stigma"]["grid"]:
            np.testing.assert_allclose(effective_stigma(sigma, s, r), sigma * np.exp(-s * r))
        for cost in INFO["supervisor"]["levels"].values():
            np.testing.assert_allclose(supervisor.effective_supervisory_cost(cost, s, r), cost * np.exp(-s * r))
    # Both fall as r rises when s > 0, and by exactly the same factor; s = 0 leaves both unchanged.
    stig, sup = effective_stigma(0.5, 0.3, r), supervisor.effective_supervisory_cost(0.15, 0.3, r)
    assert (np.diff(stig) < 0).all() and (np.diff(sup) < 0).all()
    np.testing.assert_allclose(stig / 0.5, sup / 0.15)
    np.testing.assert_allclose(effective_stigma(0.5, 0.0, r), 0.5)
    np.testing.assert_allclose(supervisor.effective_supervisory_cost(0.15, 0.0, r), 0.15)


def test_episode_uses_section_3a_values():
    r = np.array([0.1, 2.5])
    st = start_episode(svb(2), 0.0, draw_noise(SEED, 2, 2, AGENTS), stigma=0.5, strength_s=0.3, routine=r,
                       supervision="penalizes", info_randoms=ones(2))
    np.testing.assert_allclose(st["stigma_eff"], 0.5 * np.exp(-0.3 * r))
    np.testing.assert_allclose(st["sup_cost_eff"], INFO["supervisor"]["levels"]["penalizes"] * np.exp(-0.3 * r))


def test_routine_rates_match_contract_3a():
    assert [routine_rate(p, INFO) for p in ("A", "C_prime", "B", "E")] == [0.1, 0.1, 1.0, 1.0]
    assert routine_rate("C", INFO, uptake=0.75) == pytest.approx(1.875)


# ---------------------------------------------------------------- same link for every policy

def test_stigma_link_takes_no_policy():
    # The functions that turn r into stigma, cost and confidence never see a policy name.
    fns = [information.effective_stigma, information.weekly_revealing, information.read_as_distress,
           information.distress_news, information.start_information, information.observe, information.deliver,
           supervisor.level_cost, supervisor.effective_supervisory_cost, supervisor.routine_discount]
    for fn in fns:
        assert "policy" not in inspect.signature(fn).parameters, fn.__name__


def test_same_inputs_same_reading_whatever_the_policy():
    # Static calculation: every policy, at the same r, gets exactly the same answer.
    u = draw_info_randoms(SEED, 1000)["read_u"]
    for r in (0.1, 1.0, 2.5):
        expected = read_as_distress(effective_stigma(0.5, 0.3, r), weekly_revealing(r, INFO), u)
        for policy, uptake in (("A", None), ("C_prime", None), ("B", None), ("E", None), ("C", r / 2.5)):
            rp = routine_rate(policy, INFO, uptake)
            if rp == pytest.approx(r):
                got = read_as_distress(effective_stigma(0.5, 0.3, rp), weekly_revealing(rp, INFO), u)
                np.testing.assert_array_equal(got, expected)


# ---------------------------------------------------------------- the distress reading

def test_distress_reading_once_and_only_when_read():
    # Reading number 0: read as distress at the first route that reveals the draw (the weekly report, step 8).
    st, recs = run(stigma=0.5, randoms={"leak_u": np.ones(1), "read_u": np.zeros(1), "test_u": np.ones(1)})
    assert st["distress_from"][0] == 8
    assert sum(ev["new_distress"][0] for ev in st["events"] if "new_distress" in ev) == 1
    _, calm = run(stigma=0.5, randoms=ones(1))                       # reading number 1: never read as distress
    assert all(r["confidence"][0] == 1.0 for r in calm)
    conf = np.array([r["confidence"][0] for r in recs])
    assert (conf[:8] == 1.0).all() and conf[8] < 1.0
    # Stigma 0: revealed, never read as distress.
    st0, _ = run(stigma=0.0, randoms=zeros(1))
    assert (st0["distress_from"] == NEVER).all() and st0["market_knows"][0] == 1.0


def test_inference_timing():
    # A shocked bank sells securities and is refused funding: lenders see it the same half-day, depositors the next.
    st, recs = run(shock=0.4, draw_at=None, randoms=ones(1))
    for kind in ("sale", "refusal"):
        lend = {ev["t"] for ev in events(st, f"inference_{kind}") if ev["observer"] == "lenders"}
        dep = {ev["t"] for ev in events(st, f"inference_{kind}") if ev["observer"] == "depositors"}
        assert lend, kind
        assert dep == {t + 1 for t in lend if t + 1 < len(recs)}
    sold = {t for t, r in enumerate(recs) if r["used_sale_level1"][0] + r["used_sale_level2a"][0] > 0}
    assert sold == {ev["t"] for ev in events(st, "inference_sale") if ev["observer"] == "lenders"}


def test_ratio_disclosure_day_and_who():
    noise = draw_noise(SEED, 40, 32, AGENTS)
    st = start_episode(BANKS, 0.0, noise, info_randoms=ones(40))
    for _ in range(32):
        episode_step(st)
    (ev,) = [e for e in st["events"] if e["route"] == "ratio_disclosure"]
    assert ev["t"] == SPD * (INFO["routes"]["ratio_disclosure"]["day"] - 1)
    np.testing.assert_array_equal(ev["mask"], BANKS["archetype"] != "diversified_regional")


# ---------------------------------------------------------------- repeatability and vectorization

def test_same_seed_same_result():
    a, ra = run(n=50, stigma=0.5, randoms=draw_info_randoms(7, 50))
    b, rb = run(n=50, stigma=0.5, randoms=draw_info_randoms(7, 50))
    for x, y in zip(ra, rb):
        for k in x:
            np.testing.assert_array_equal(x[k], y[k])
    assert len(a["events"]) == len(b["events"])
    for e, f in zip(a["events"], b["events"]):
        assert (e["t"], e["route"]) == (f["t"], f["route"]) and (e["mask"] == f["mask"]).all()


def test_info_randoms_leave_news_noise_unchanged():
    # The information numbers come from their own stream: M1.4's news noise is untouched.
    rng = np.random.default_rng(SEED)
    np.testing.assert_array_equal(draw_noise(SEED, 3, 4, AGENTS),
                                  rng.normal(0.0, AGENTS["confidence"]["news_noise_sd"], size=(3, 4)))


def test_rows_together_equal_rows_alone():
    n = 6
    r = np.array([0.1, 2.5, 1.0, 0.1, 2.5, 1.0])
    sigma = np.array([0.9, 0.9, 0.5, 0.2, 0.5, 0.0])
    rnd = draw_info_randoms(11, n)
    rnd["read_u"][:3] = 0.0                                           # make sure some rows are read as distress
    together, rt = run(n=n, shock=0.05, stigma=sigma, routine=r, randoms=rnd)
    for j in range(n):
        alone, ra = run(n=1, shock=0.05, stigma=sigma[j], routine=r[j],
                        randoms={k: v[j:j + 1] for k, v in rnd.items()})
        np.testing.assert_allclose([x["confidence"][j] for x in rt], [x["confidence"][0] for x in ra])
        assert together["distress_from"][j] == alone["distress_from"][0]
        assert together["market_knows"][j] == alone["market_knows"][0]


def test_forced_draw_books_on_arrival():
    st, recs = run(draw_at=2, randoms=ones(1))
    # Untested prepositioned loans: one day's lag, so the loan and the cash arrive at step 4.
    assert recs[3]["arrived_dw_untested"][0] == 0 and recs[4]["arrived_dw_untested"][0] == pytest.approx(6.0)
    assert st["dw_loans_bn"][0] == pytest.approx(6.0)
