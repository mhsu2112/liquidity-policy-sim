"""Checks on the policy switches and the five named policies (session M1.7).

Mechanics only: the rules match the contract (sections 2a, 2c, 2d, 3a) and
Clarification 11, the ratios match hand calculations, balance sheets balance and
the same seed gives the same table. No stress episode runs, and nothing here
asserts that any policy does better or worse than another.
"""

import copy

import numpy as np
import pytest

from engine.balance_sheet import check_balances
from engine.banks import generate_banks
from engine.collateral import SECURITY_CLASSES, fed_loans, loan_capacity, securities_mv
from engine.five_day import five_day_ratio
from engine.funding import load_funding_settings
from engine.information import load_information_settings
from engine.lcr import load_lcr_settings
from engine.lcr_credit import credit, credit_after_draws, credit_limits, opted_in
from engine.policies import draw_policy_randoms, load_policies, policy_setup
from engine.write_policy_table import build_table

CFG = load_policies()
FS = load_funding_settings()
LCR_S = load_lcr_settings()
INFO = load_information_settings()
MARGINS = FS["discount_window"]["margins"]
BANKS = generate_banks()
RANDOMS = draw_policy_randoms(CFG["seed"], len(BANKS["bank_id"]))
POLICIES = ["A", "B", "C", "C_prime", "E"]
TOL = 1e-9  # $1, in $ billions


def setup(name, cfg=CFG, banks=BANKS, randoms=RANDOMS):
    return policy_setup(banks, name, cfg, randoms, FS, LCR_S, INFO)


SETUPS = {name: setup(name) for name in POLICIES}


def with_settings(**changes):
    """A copy of the policy settings with some values changed, e.g. lcr_credit={"uptake": 1.0}."""
    cfg = copy.deepcopy(CFG)
    for section, values in changes.items():
        cfg[section].update(values)
    return cfg


def hand_bank(uninsured=40.0, insured=40.0, loss=0.0):
    """One bank small enough to work by hand ($bn). Total assets 100.

    Assets: reserves 5, Level 1 10, Level 2A 10, loans 60 (20 each resi / CRE / C&I;
    50 eligible), other 15. Liabilities: deposits as given, wholesale 10, equity 10.
    """
    a = lambda x: np.array([float(x)])  # noqa: E731
    other = 100 - 5 - 20 - 60
    return {"bank_id": np.array(["HAND-01"]), "archetype": np.array(["gsib"]),
            "lcr_calibration": a(1.0), "total_assets_bn": a(100),
            "reserves_bn": a(5), "securities_bn": a(20), "level1_securities_bn": a(10),
            "level2a_securities_bn": a(10), "loans_bn": a(60), "resi_loans_bn": a(20),
            "cre_loans_bn": a(20), "ci_loans_bn": a(20), "other_assets_bn": a(other),
            "unrealized_loss_bn": a(loss), "eligible_loans_bn": a(50),
            "insured_deposits_bn": a(insured), "uninsured_deposits_bn": a(uninsured),
            "stwf_bn": a(10), "equity_bn": a(100 - insured - uninsured - 10)}


HAND_IN = {"test_u": np.array([0.99]), "opt_in_u": np.array([0.0])}  # opts in; not tested by chance
LENDABLE_PER_LOAN = (0.80 * 20 + 0.72 * 20 + 0.80 * 20) / 60   # 0.773333


# ---------------------------------------------------------------- switches

def test_named_policies_match_contract_2a():
    # Contract 2a, copied by hand: prepositioning, testing, five-day ratio, LCR credit.
    contract = {"A": (False, False, False, False), "B": (True, True, True, False),
                "C": (False, False, False, True), "E": (True, True, False, False)}
    for name, expected in contract.items():
        sw = CFG["policies"][name]["switches"]
        assert (sw["prepositioning_mandate"], sw["testing_mandate"],
                sw["five_day_ratio"], sw["lcr_credit"]) == expected
    # C' is C's switches with no usage multiple (contract 2d).
    assert CFG["policies"]["C_prime"]["switches"] == CFG["policies"]["C"]["switches"]
    assert CFG["policies"]["C_prime"]["overrides"] == {"usage_multiple": None}


def test_switches_off_leave_the_status_quo():
    # A moves no collateral, adds no reserves, gives no credit and releases nothing.
    a = SETUPS["A"]
    for k in ("fed_loans_from_unpledged_bn", "fed_loans_from_fhlb_bn", "fed_level1_mv_bn", "fed_level2a_mv_bn"):
        assert np.all(a["placement"][k] == 0)
    assert np.all(a["credit_bn"] == 0) and np.all(a["extra_reserves_bn"] == 0)
    for k in ("reserves_bn", "loans_bn", "equity_bn"):
        assert np.array_equal(a["banks"][k], BANKS[k])


# ---------------------------------------------------------------- Option B and E

def test_b_ratio_passes_after_prepositioning_and_reserves():
    assert np.all(SETUPS["B"]["five_day_ratio"] >= 1 - TOL)


def test_b_ratio_passes_under_a_full_run():
    # Sensitivity (Decision 2-2): 100% of uninsured deposits. Collateral can't close
    # every gap, so some banks hold extra reserves. Every bank passes, unless it has
    # turned every loan at the Fed into reserves; then the gap left is reported exactly.
    s = setup("B", with_settings(five_day_ratio={"runoff_uninsured": 1.0}))
    assert np.any(s["extra_reserves_bn"] > 0)
    short = s["five_day_unmet_bn"] > TOL
    assert np.all(s["five_day_ratio"][~short] >= 1 - TOL)
    assert np.allclose(fed_loans(s["placement"])[short], 0, atol=1e-9)
    outflows = BANKS["uninsured_deposits_bn"] + BANKS["stwf_bn"]
    assert np.allclose(s["five_day_ratio"][short], 1 - s["five_day_unmet_bn"][short] / outflows[short])
    check_balances(s["banks"])


def test_b_prepositions_the_least_that_passes():
    # A bank that already passes under A moves nothing; any bank that moves collateral
    # stops exactly at 100% (one more dollar less and it would fail).
    a, b = SETUPS["A"], SETUPS["B"]
    moved = fed_loans(b["placement"]) + b["placement"]["fed_level1_mv_bn"] + b["placement"]["fed_level2a_mv_bn"] \
        - fed_loans(a["placement"]) > TOL
    assert np.all(~moved[a["five_day_ratio"] >= 1])
    assert np.allclose(b["five_day_ratio"][moved], 1.0, atol=1e-9)


def test_b_by_hand():
    # Five-day outflows = 40% x 40 + 100% x 10 = 26. Under A: reserves 5 + 30% x 50 x 0.7733 = 16.6.
    # Gap 9.4, met from Level 2A (cheapest first): 9.4 / 0.96 = 9.7917 of Level 2A at the Fed.
    s = policy_setup(hand_bank(), "B", CFG, HAND_IN, FS, LCR_S, INFO)
    assert s["placement"]["fed_level2a_mv_bn"][0] == pytest.approx(9.4 / 0.96)
    assert s["placement"]["fed_level1_mv_bn"][0] == 0
    assert fed_loans(s["placement"])[0] == pytest.approx(15)
    assert s["five_day_ratio"][0] == pytest.approx(1.0)
    assert s["extra_reserves_bn"][0] == 0


def test_b_order_securities_then_unpledged_then_fhlb():
    # Outflows 40% x 75 + 10 = 40; gap 40 - 16.6 = 23.4. Level 2A gives 9.6, Level 1 9.6,
    # then 4.2 of lendable value from unpledged loans; Home Loan Bank loans untouched.
    s = policy_setup(hand_bank(uninsured=75, insured=5), "B", CFG, HAND_IN, FS, LCR_S, INFO)
    p = s["placement"]
    assert p["fed_level2a_mv_bn"][0] == pytest.approx(10) and p["fed_level1_mv_bn"][0] == pytest.approx(10)
    assert p["fed_loans_from_unpledged_bn"][0] == pytest.approx(4.2 / LENDABLE_PER_LOAN)
    assert p["fed_loans_from_fhlb_bn"][0] == 0
    assert s["five_day_ratio"][0] == pytest.approx(1.0)


def test_b_extra_reserves_from_loans_that_are_not_collateral():
    # Full run, uninsured 65: outflows 100% x 65 + 10 = 75. Eligible loans 45 (15 not collateral).
    # All collateral: 5 + 9.6 + 9.6 + 45 x 0.7733 = 59.0. The 16.0 shortfall is run off first from
    # the 15 of loans that are not collateral, then from loans at the Fed, each $1 netting
    # (1 - 0.7733). Total assets unchanged.
    cfg = with_settings(five_day_ratio={"runoff_uninsured": 1.0})
    bank = hand_bank(uninsured=65, insured=15)
    bank["eligible_loans_bn"] = np.array([45.0])
    s = policy_setup(bank, "B", cfg, HAND_IN, FS, LCR_S, INFO)
    shortfall = 75 - (5 + 9.6 + 9.6 + 45 * LENDABLE_PER_LOAN)
    from_fed = (shortfall - 15) / (1 - LENDABLE_PER_LOAN)
    assert s["five_day_shortfall_bn"][0] == pytest.approx(shortfall)
    assert s["extra_reserves_bn"][0] == pytest.approx(15 + from_fed)
    assert s["placement"]["fed_loans_converted_bn"][0] == pytest.approx(from_fed)
    assert s["five_day_unmet_bn"][0] == 0
    assert s["five_day_ratio"][0] == pytest.approx(1.0)
    assert s["banks"]["total_assets_bn"][0] == pytest.approx(100)
    check_balances(s["banks"])


def test_e_collateral_equals_b():
    b, e = SETUPS["B"]["placement"], SETUPS["E"]["placement"]
    for k in ("fed_loans_from_unpledged_bn", "fed_loans_from_fhlb_bn", "fed_level1_mv_bn", "fed_level2a_mv_bn"):
        assert np.array_equal(b[k], e[k])
    assert np.all(SETUPS["E"]["extra_reserves_bn"] == 0)   # E has no ratio, so no extra reserves


def test_b_and_e_test_quarterly():
    for name in ("B", "E"):
        s = SETUPS[name]
        assert np.all(s["tested"]) and np.all(s["test_draws_per_year"] == 4)
        assert np.all(s["routine_rate"] == 1.0)


# ---------------------------------------------------------------- Option C and C'

@pytest.mark.parametrize("name", ["C", "C_prime"])
@pytest.mark.parametrize("trigger", [False, True])
@pytest.mark.parametrize("uptake", [0.5, 0.75, 1.0])
def test_credit_never_exceeds_any_limit(name, trigger, uptake):
    s = setup(name, with_settings(lcr_credit={"stress_trigger_fires": trigger, "uptake": uptake}))
    for k in ("ceiling_limit_bn", "usage_limit_bn", "capacity_limit_bn"):
        assert np.all(s["credit_bn"] <= s[k] + TOL)
    assert np.all(s["credit_if_trigger_fires_bn"] <= s["capacity_limit_bn"] + TOL)


@pytest.mark.parametrize("k", [75, 100, 125])
def test_usage_limit_supports_target_under_every_multiple(k):
    s = setup("C", with_settings(lcr_credit={"usage_multiple": k}))
    opt = s["opted_in"]
    assert np.allclose(s["usage_limit_bn"][opt], k * s["usage_draw_bn"][opt])
    assert np.all(s["credit_bn"] <= s["usage_limit_bn"] + TOL)


def test_c_never_credits_hqla_collateral():
    # Put every security at the Fed: credit does not change, and the capacity limit
    # equals loan capacity exactly.
    s = SETUPS["C"]
    place = {k: v.copy() for k, v in s["placement"].items()}
    for c in SECURITY_CLASSES:
        place[f"fed_{c}_mv_bn"] = securities_mv(BANKS, c)
    c_cfg = CFG["lcr_credit"]
    draws = np.repeat(s["usage_draw_bn"][:, None], 5, axis=1)
    net = s["ceiling_limit_bn"] / c_cfg["ceiling"]
    limits = credit_limits(place, net, draws, c_cfg["usage_multiple"], c_cfg, False)
    assert np.array_equal(limits["capacity_limit_bn"], loan_capacity(s["placement"]))
    assert np.allclose(credit(limits, s["opted_in"]), s["credit_bn"])


def test_banks_without_lcr_get_no_credit():
    for name in ("C", "C_prime"):
        s = setup(name, with_settings(lcr_credit={"uptake": 1.0}))
        div = BANKS["archetype"] == "diversified_regional"
        assert np.all(s["credit_bn"][div] == 0) and not s["opted_in"][div].any()
        assert np.all(s["credit_bn"][~div] > 0)   # with full uptake, every LCR bank gets some


def test_c_prime_has_no_usage_draws_and_borrows_at_a_rate():
    cp, a = SETUPS["C_prime"], SETUPS["A"]
    assert np.all(cp["usage_draw_bn"] == 0)
    assert np.all(np.isinf(cp["usage_limit_bn"]))
    assert np.all(cp["routine_rate"] == a["routine_rate"]) and a["routine_rate"][0] == 0.1
    assert np.array_equal(cp["tested"], a["tested"])   # tested drawn as in M1.6, same random numbers


def test_c_opt_in_banks_tested_and_rate():
    c = SETUPS["C"]
    assert np.all(c["tested"][c["opted_in"]])
    assert np.all(c["routine_rate"] == CFG["lcr_credit"]["uptake"] * 2.5)   # contract 3a
    assert np.all(c["usage_draw_bn"][~c["opted_in"]] == 0)


def test_same_banks_opt_in_under_c_and_c_prime_and_nested_by_uptake():
    assert np.array_equal(SETUPS["C"]["opted_in"], SETUPS["C_prime"]["opted_in"])
    sets = [opted_in(BANKS, RANDOMS["opt_in_u"], u) for u in (0.5, 0.75, 1.0)]
    assert np.all(sets[0] <= sets[1]) and np.all(sets[1] <= sets[2])


def test_c_by_hand():
    # Net cash outflows = 3% x 40 + 40% x 40 + 100% x 10 = 27.2 (full LCR).
    # 30% x 27.2 = 8.16 is below loan capacity at the Fed (15 x 0.7733 = 11.6), so no extra loans move.
    # Five draws of 8.16 / 75 = 0.1088 each; usage limit 8.16. Credit = min(5.44, 8.16, 11.6) = 5.44.
    # Release 5.44: reserves 5 down to the 1.00 floor gives 4.00, then 1.44 of Level 1 (no loss).
    s = policy_setup(hand_bank(), "C", CFG, HAND_IN, FS, LCR_S, INFO)
    assert s["usage_draw_bn"][0] == pytest.approx(8.16 / 75)
    assert s["usage_limit_bn"][0] == pytest.approx(8.16)
    assert s["credit_bn"][0] == pytest.approx(5.44)
    assert s["credit_if_trigger_fires_bn"][0] == pytest.approx(8.16)
    assert s["released"]["reserves"][0] == pytest.approx(4.0)
    assert s["released"]["level1"][0] == pytest.approx(1.44)
    assert s["banks"]["loans_bn"][0] == pytest.approx(65.44)
    # HQLA after release: 1 + 8.56 + Level 2A 8.5 (cap 6.37 binds) = 15.93; LCR without credit 15.93 / 27.2.
    hqla = 9.56 + min(8.5, 9.56 * 2 / 3)
    assert s["lcr_without_credit"][0] == pytest.approx(hqla / 27.2)
    assert s["lcr_reported"][0] == pytest.approx((hqla + 5.44) / 27.2)
    assert s["buffer_gap"][0] == pytest.approx(5.44 / 27.2)


def test_release_of_securities_realizes_their_loss():
    # With a 10% unrealized loss, 1.44 of Level 1 at market value is 1.6 at book; 0.16 comes off equity.
    s = policy_setup(hand_bank(loss=2.0), "C", CFG, HAND_IN, FS, LCR_S, INFO)
    assert s["released"]["level1"][0] == pytest.approx(1.44)
    assert s["banks"]["level1_securities_bn"][0] == pytest.approx(10 - 1.6)
    assert s["banks"]["equity_bn"][0] == pytest.approx(10 - 0.16)
    check_balances(s["banks"])


def test_credit_falls_by_amount_drawn():
    assert np.allclose(credit_after_draws(np.array([5.0, 5.0, 5.0]), np.array([0.0, 2.0, 9.0])), [5.0, 3.0, 0.0])


def test_no_release_when_share_is_zero():
    s = setup("C", with_settings(lcr_credit={"release_share": 0.0}))
    assert all(np.all(v == 0) for v in s["released"].values())
    assert np.array_equal(s["banks"]["reserves_bn"], BANKS["reserves_bn"])


# ---------------------------------------------------------------- whole table

@pytest.mark.parametrize("name", POLICIES)
def test_balance_sheets_balance(name):
    check_balances(SETUPS[name]["banks"])   # book, total and market value


def test_random_numbers_required():
    with pytest.raises(ValueError):
        policy_setup(BANKS, "C", CFG, None, FS, LCR_S, INFO)


def test_same_seed_same_table():
    t1, t2 = build_table(), build_table()
    assert all(np.array_equal(t1[k], t2[k]) for k in t1)
    assert len(t1["policy"]) == 200


def test_five_day_ratio_reported_the_same_way_for_every_policy():
    # Under A the ratio is reserves + 30% of eligible loans at the Fed, over runnable outflows.
    a = SETUPS["A"]
    by_hand = ((BANKS["reserves_bn"] + 0.30 * BANKS["eligible_loans_bn"] * a["placement"]["lendable_per_loan"])
               / (0.40 * BANKS["uninsured_deposits_bn"] + BANKS["stwf_bn"]))
    assert np.allclose(a["five_day_ratio"], by_hand)
    assert np.allclose(five_day_ratio(a["banks"], a["placement"], CFG, MARGINS), by_hand)
