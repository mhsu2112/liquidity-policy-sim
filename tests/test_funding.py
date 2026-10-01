"""Checks on the funding waterfall (session M1.3).

Mechanics only: the order of sources, their limits and delays, losses on
sales, balance sheets that balance, shortfalls that are reported, and banks
computed together giving the same answer as banks computed one at a time.
Nothing here is a stress scenario or a policy comparison.
"""

import copy

import numpy as np
import pytest

from engine.balance_sheet import ONE_DOLLAR_BN, check_balances, mtm_equity
from engine.banks import generate_banks
from engine.funding import load_funding_settings, start_state, step

SETTINGS = load_funding_settings()
BANKS = generate_banks()
TOL = 1e-9


def run(banks=BANKS, outflows=None, steps=24, tested=None, settings=SETTINGS, check=True):
    """Run the waterfall; `outflows` is a list of {line: amount} per step (empty after)."""
    st = start_state(banks, settings, tested)
    recs = []
    for t in range(steps):
        recs.append(step(st, outflows[t] if t < len(outflows) else {}))
        if check:
            check_balances(st)
    return st, recs


def everything_leaves(banks):
    """An outflow far beyond any bank's sources: all deposits leave at once."""
    return [{"uninsured_deposits_bn": banks["uninsured_deposits_bn"],
             "insured_deposits_bn": banks["insured_deposits_bn"]}]


def thirty_pct(banks):
    return [{"uninsured_deposits_bn": 0.3 * banks["total_assets_bn"]}]


# ---------------------------------------------------------------- order

@pytest.mark.parametrize("scenario", [thirty_pct, everything_leaves])
def test_sources_used_in_order(scenario):
    st, recs = run(outflows=scenario(BANKS))
    order = st["order"]
    lags = [st["lags"][k] for k in order]
    assert lags == sorted(lags)  # speed tiers: faster sources always come first
    for r in recs:
        for j, later in enumerate(order):
            used_later = r[f"used_{later}"] > TOL
            for earlier in order[:j]:
                # If a later source gave cash, every earlier one was used to its limit.
                gap = r[f"capacity_{earlier}"] - r[f"used_{earlier}"]
                assert (gap[used_later] < TOL).all(), (earlier, later)


def test_order_within_tiers_follows_brief():
    # Within each speed tier: reserves, then securities (repo or sale; Clarification 6),
    # then Home Loan Bank, then window.
    rank = lambda k: (0 if k == "reserves" else 1 if k.startswith(("sale", "repo")) else  # noqa: E731
                      2 if k.startswith("fhlb") else 3)
    st = start_state(BANKS, SETTINGS)
    by_lag = {}
    for k in st["order"]:
        by_lag.setdefault(st["lags"][k], []).append(rank(k))
    for ranks in by_lag.values():
        assert ranks == sorted(ranks)


# ---------------------------------------------------------------- limits

def test_limits_respected():
    st, recs = run(outflows=everything_leaves(BANKS))
    start = start_state(BANKS, SETTINGS)
    total = lambda k: sum(r[f"used_{k}"] for r in recs)  # noqa: E731

    # Reserves never go below the operating floor to pay an outflow.
    for r in recs:
        assert (r["reserves"] >= st["reserve_floor_bn"] - TOL).all()
    # Home Loan Bank: same day at most the line; in total at most 75% of pledged loans.
    line = np.minimum(SETTINGS["fhlb"]["line_share_of_assets"] * BANKS["total_assets_bn"],
                      start["fhlb_total_left_bn"])
    assert (total("fhlb_line") <= line + TOL).all()
    fhlb_cap = SETTINGS["fhlb"]["advance_rate"] * start["fhlb_pledged_loans_bn"]
    assert (total("fhlb_line") + total("fhlb_above_line") <= fhlb_cap + TOL).all()
    assert (st["fhlb_advances_bn"] <= fhlb_cap + TOL).all()
    # Window: never more than margin x collateral in any pool.
    assert (total("dw_tested") + total("dw_untested") <= start["dw_prepositioned_left_bn"] + TOL).all()
    assert (total("dw_unpledged") <= start["dw_unpledged_left_bn"] + TOL).all()
    m = SETTINGS["discount_window"]["margins"]
    for c in ("level1", "level2a"):
        mv = BANKS[f"{c}_securities_bn"] * (1 - start["loss_rate"])
        assert (total(f"dw_{c}") <= m[c] * mv + TOL).all()
        # Sales plus window pledges never exceed holdings.
        assert (st[f"sold_mv_{c}_bn"] + st[f"dw_pledged_mv_{c}_bn"] <= mv + TOL).all()
        assert (st[f"{c}_securities_bn"] >= -TOL).all()


# ---------------------------------------------------------------- delays

def test_each_source_arrives_exactly_its_lag_later():
    st, recs = run(outflows=everything_leaves(BANKS), steps=24)
    for k, lag in st["lags"].items():
        for t, r in enumerate(recs):
            if lag > 0 and t + lag < len(recs):
                np.testing.assert_allclose(recs[t + lag][f"arrived_{k}"], r[f"used_{k}"], atol=TOL)
        # Nothing ever arrives earlier than its lag allows.
        for t in range(min(lag, len(recs))):
            assert (recs[t][f"arrived_{k}"] == 0).all(), k


# Contract section 7 and Clarification 5, in half-day steps, typed in from the
# documents rather than read from the settings file, so a settings typo is caught.
CONTRACT_LAGS = {"reserves": 0, "fhlb_line": 0, "dw_tested": 0,          # same half-day
                 "repo_level1": 0, "repo_level2a": 0,                     # same half-day (Clarification 6)
                 "repo_next_level1": 2, "repo_next_level2a": 2,           # next day, beyond the line (Clarification 7)
                 "sale_level1": 2, "fhlb_above_line": 2, "dw_untested": 2,  # next day
                 "dw_level1": 2, "dw_level2a": 2,
                 "sale_level2a": 4,                                       # T+2
                 "dw_unpledged": 20,                                      # from day 11
                 # M1.7b (Clarification 12; owner approved adding these): prepositioned and tested securities
                 "dw_tested_level1": 0, "dw_tested_level2a": 0}           # same half-day (contract 7)


def test_lags_match_contract():
    assert start_state(BANKS, SETTINGS)["lags"] == CONTRACT_LAGS


def test_untested_collateral_is_never_same_day():
    _, recs = run(outflows=thirty_pct(BANKS), steps=1)
    assert (recs[0]["used_dw_tested"] == 0).all()  # Clarification 4: starts untested


def test_tested_collateral_is_same_day():
    _, recs = run(outflows=thirty_pct(BANKS), steps=1, tested=np.ones(40, bool))
    r = recs[0]
    assert (r["used_dw_untested"] == 0).all()
    reached = r["capacity_dw_tested"] > 0
    # Banks that got as far as the window drew on it the same half-day.
    reached &= r["used_dw_tested"] > 0
    assert reached.any()
    assert (r["paid_now"][reached] >= r["used_dw_tested"][reached]).all()


def test_unpledged_loans_not_before_day_11():
    st, recs = run(outflows=everything_leaves(BANKS), steps=24)
    assert st["lags"]["dw_unpledged"] == 20
    for t in range(20):
        assert (recs[t]["arrived_dw_unpledged"] == 0).all()
    assert (recs[20]["arrived_dw_unpledged"] > 0).any()  # day 11 morning


# ---------------------------------------------------------------- losses

def hand_bank():
    """A bank simple enough to work by hand ($bn).

    Assets 200: reserves 2 (exactly the 1% floor), Level 1 securities 100 with
    a 10% unrealized loss, 1 of residential loans (none eligible), other 97.
    Liabilities: uninsured 150, insured 20, wholesale 10; equity 20.
    """
    a = lambda x: np.array([float(x)])  # noqa: E731
    return {"bank_id": np.array(["HAND-01"]), "archetype": np.array(["gsib"]),  # type sets the repo line
            "total_assets_bn": a(200), "reserves_bn": a(2),
            "level1_securities_bn": a(100), "level2a_securities_bn": a(0), "securities_bn": a(100),
            "unrealized_loss_bn": a(10), "loans_bn": a(1), "resi_loans_bn": a(1), "cre_loans_bn": a(0),
            "ci_loans_bn": a(0), "eligible_loans_bn": a(0), "other_assets_bn": a(97),
            "uninsured_deposits_bn": a(150), "insured_deposits_bn": a(20), "stwf_bn": a(10),
            "equity_bn": a(20), "lcr_calibration": a(1.0)}


def test_sale_losses_reduce_equity_by_hand():
    s = copy.deepcopy(SETTINGS)
    s["securities"]["price_impact_per_bn"]["level1"] = 0.001  # 1 bp per $1bn, for round numbers
    s["repo"]["haircuts"]["level1"] = 1.0  # repo switched off: this test is about sale arithmetic
    bank = hand_bank()
    # To raise 48.75 the bank sells 50 at market value: 50 - 0.001 x 50^2 / 2 = 48.75.
    # Book value sold: 50 / 0.9 = 55.56, so the realized loss is 5.56 already on the books
    # plus a 1.25 fire-sale discount: equity falls 6.81; mark-to-market equity falls 1.25.
    mtm_before = mtm_equity(bank)[0]
    st, recs = run(bank, [{"uninsured_deposits_bn": 48.75}], steps=3, settings=s)
    r = recs[0]
    assert r["used_sale_level1"][0] == pytest.approx(48.75)
    assert st["sold_mv_level1_bn"][0] == pytest.approx(50)
    assert st["level1_securities_bn"][0] == pytest.approx(100 - 50 / 0.9)
    assert r["realized_loss"][0] == pytest.approx(50 / 0.9 - 50 + 1.25)
    assert st["equity_bn"][0] == pytest.approx(20 - (50 / 0.9 - 50) - 1.25)
    assert mtm_equity(st)[0] == pytest.approx(mtm_before - 1.25)
    # The cash settled T+1 (two half-days later) and paid the waiting depositors.
    assert recs[2]["arrived_sale_level1"][0] == pytest.approx(48.75)
    assert recs[2]["unpaid_end"][0] == pytest.approx(0)


def test_realized_losses_match_equity_change():
    st, recs = run(outflows=everything_leaves(BANKS))
    np.testing.assert_allclose(BANKS["equity_bn"] - st["equity_bn"], sum(r["realized_loss"] for r in recs),
                               atol=ONE_DOLLAR_BN)
    # (While repo always rolls, repo takes every security before any sale, so this
    # scenario realizes no loss; test_sale_losses_reduce_equity_by_hand covers sales.)


# ---------------------------------------------------------------- balance

@pytest.mark.parametrize("scenario", [thirty_pct, everything_leaves])
def test_balance_sheet_balances_after_every_step(scenario):
    run(outflows=scenario(BANKS), steps=30, check=True)  # check_balances raises on any failure


# ---------------------------------------------------------------- shortfall

def test_shortfall_equals_the_excess():
    st, recs = run(outflows=everything_leaves(BANKS), steps=1)
    start = start_state(BANKS, SETTINGS)
    r = recs[0]
    # Every source used to its limit, worked out independently:
    h = SETTINGS["repo"]["haircuts"]
    l1_mv = BANKS["level1_securities_bn"] * (1 - start["loss_rate"])
    l2a_mv = BANKS["level2a_securities_bn"] * (1 - start["loss_rate"])
    everything = (BANKS["reserves_bn"] - start["reserve_floor_bn"]
                  + (1 - h["level1"]) * l1_mv            # all Level 1 repo'd (same day)
                  + (1 - h["level2a"]) * l2a_mv          # all Level 2A repo'd (same day)
                  + start["fhlb_total_left_bn"]
                  + start["dw_prepositioned_left_bn"]
                  + start["dw_unpledged_left_bn"])
    np.testing.assert_allclose(r["shortfall"], r["outflow"] - everything, atol=TOL)
    assert (r["shortfall"] > 0).all()  # all deposits leaving exceeds every bank's sources


def test_shortfall_is_never_hidden():
    # Outflows to date always equal paid now + paid late + still owed.
    _, recs = run(outflows=everything_leaves(BANKS) + thirty_pct(BANKS), steps=30)
    cum_out = cum_now = cum_late = 0
    for r in recs:
        cum_out, cum_now, cum_late = cum_out + r["outflow"], cum_now + r["paid_now"], cum_late + r["paid_late"]
        np.testing.assert_allclose(cum_out, cum_now + cum_late + r["unpaid_end"], atol=ONE_DOLLAR_BN)
        # Still owed is at least this step's shortfall: the shortfall stays on the books.
        assert (r["unpaid_end"] >= r["shortfall"] - TOL).all()


def test_outflow_beyond_balance_is_recorded():
    _, recs = run(outflows=[{"stwf_bn": BANKS["stwf_bn"] + 5}], steps=1)
    np.testing.assert_allclose(recs[0]["outflow_beyond_balance_stwf_bn"], 5)


# ---------------------------------------------------------------- vectorized

def test_all_banks_together_equal_one_at_a_time():
    flows = thirty_pct(BANKS) + [{"uninsured_deposits_bn": 0.1 * BANKS["total_assets_bn"]}]
    together, recs = run(outflows=flows, steps=8)
    for i in range(40):
        one = {k: (v[[i]] if isinstance(v, np.ndarray) else v) for k, v in BANKS.items()}
        alone, recs1 = run(one, [{k: v[[i]] for k, v in f.items()} for f in flows], steps=8)
        for k in ("reserves_bn", "equity_bn", "unpaid_outflows_bn", "fhlb_advances_bn", "dw_loans_bn",
                  "level1_securities_bn", "level2a_securities_bn"):
            assert alone[k][0] == together[k][i], (BANKS["bank_id"][i], k)
        for t in range(8):
            assert recs1[t]["shortfall"][0] == recs[t]["shortfall"][i]


# ---------------------------------------------------------------- repo (session M1.3b, Clarification 6)

def test_repo_after_reserves_before_fhlb_line():
    st = start_state(BANKS, SETTINGS)
    order = st["order"]
    assert order.index("reserves") < order.index("repo_level1") < order.index("repo_level2a") \
        < order.index("fhlb_line") < order.index("dw_tested")
    # And in the numbers: repo gives cash only once reserves above the floor are used up,
    # and the line only once repo is used up.
    _, recs = run(outflows=thirty_pct(BANKS), steps=1)
    r = recs[0]
    repo_used = (r["used_repo_level1"] + r["used_repo_level2a"]) > TOL
    assert repo_used.any()
    assert (r["capacity_reserves"][repo_used] - r["used_reserves"][repo_used] < TOL).all()
    line_used = r["used_fhlb_line"] > TOL
    for k in ("repo_level1", "repo_level2a"):
        assert (r[f"capacity_{k}"][line_used] - r[f"used_{k}"][line_used] < TOL).all()


def repo_bank():
    """Hand bank with 100 of Level 1 and 100 of Level 2A, no unrealized loss, reserves at the floor."""
    b = hand_bank()
    b.update({k: np.array([v]) for k, v in {
        "level1_securities_bn": 100.0, "level2a_securities_bn": 100.0, "securities_bn": 200.0,
        "unrealized_loss_bn": 0.0, "other_assets_bn": 0.0, "total_assets_bn": 203.0,
        "reserves_bn": 2.03, "equity_bn": 23.03}.items()})
    return b


def test_repo_haircuts_applied():
    st, recs = run(repo_bank(), [{"uninsured_deposits_bn": 150.0}], steps=3)
    r = recs[0]
    # Same day, repo is capped at the GSIB line: 20% x 203 = 40.6 (Clarification 7).
    line = 0.20 * 203
    assert r["used_repo_level1"][0] == pytest.approx(line)
    assert r["paid_now"][0] == pytest.approx(line)
    # The rest comes next day. In total 100 of Level 1 raises 98, and
    # Level 2A covers what is left at a 5% haircut (Clarification 6).
    assert r["used_repo_level1"][0] + r["used_repo_next_level1"][0] == pytest.approx(98)
    assert r["used_repo_next_level2a"][0] == pytest.approx(150 - 98)
    assert st["repo_pledged_mv_level1_bn"][0] == pytest.approx(100)
    assert st["repo_pledged_mv_level2a_bn"][0] == pytest.approx((150 - 98) / 0.95)
    assert recs[2]["arrived_repo_next_level1"][0] == pytest.approx(98 - line)
    assert st["repo_bn"][0] == pytest.approx(150)  # all booked once the next-day cash arrived


def test_repo_realizes_no_loss():
    st0 = start_state(BANKS, SETTINGS)
    st, recs = run(outflows=thirty_pct(BANKS), steps=4)
    assert (sum(r["used_repo_level1"] for r in recs) > 0).all()  # every bank used repo
    for k in ("equity_bn", "unrealized_loss_bn", "level1_securities_bn", "level2a_securities_bn"):
        np.testing.assert_array_equal(st[k], st0[k])
    assert all((r["realized_loss"] == 0).all() for r in recs)


def test_repo_securities_cannot_be_used_twice():
    st, _ = run(outflows=everything_leaves(BANKS), steps=4)
    for c in ("level1", "level2a"):
        mv = BANKS[f"{c}_securities_bn"] * (1 - st["loss_rate"])
        used = st[f"repo_pledged_mv_{c}_bn"] + st[f"dw_pledged_mv_{c}_bn"] + st[f"sold_mv_{c}_bn"]
        assert (used <= mv + TOL).all()
