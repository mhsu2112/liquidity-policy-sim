"""Checks that episodes start from each policy's setup (session M1.7b, Clarification 12).

Mechanics only. No stress episode runs under any policy but A: every check here
either starts an episode without stepping it, or runs ONE waterfall step with a
forced withdrawal and no depositor or lender behavior at all (engine/funding.py
directly), or one episode step with no shock (nobody withdraws). Nothing compares
policies or prints an outcome.
"""

import ast
from pathlib import Path

import numpy as np
import pytest

from engine.balance_sheet import check_balances
from engine.banks import generate_banks
from engine.episode import draw_noise, episode_step, load_yaml, start_episode
from engine.funding import _capacity, load_funding_settings, start_state, step
from engine.information import draw_info_randoms, load_information_settings, no_information_randoms
from engine.lcr import compute_lcr, load_lcr_settings
from engine.lcr_credit import reported_lcr
from engine.policies import draw_policy_randoms, load_policies, policy_setup
from engine.write_policy_table import POLICY_ORDER, build_table

ROOT = Path(__file__).resolve().parent.parent
CFG = load_policies()
FS = load_funding_settings()
LCR_S = load_lcr_settings()
INFO = load_information_settings()
AGENTS = load_yaml("agents.yaml")
BANKS = generate_banks()
N = len(BANKS["bank_id"])
RANDOMS = draw_policy_randoms(CFG["seed"], N)
SETUPS = {name: policy_setup(BANKS, name, CFG, RANDOMS, FS, LCR_S, INFO) for name in POLICY_ORDER}
TOL = 1e-6


def start(name, **kw):
    """An episode set up under a policy and NOT stepped: no shock, the table's random numbers."""
    return start_episode(BANKS, 0.0, draw_noise(CFG["seed"], N, 4, AGENTS),
                         info_randoms=draw_info_randoms(CFG["seed"], N), setup=SETUPS[name], **kw)


def table_rows(table, name):
    rows = table["policy"] == name
    return {k: v[rows] for k, v in table.items()}


# ---------------------------------------------------------------- starting position

@pytest.mark.parametrize("name", POLICY_ORDER)
def test_episode_starts_from_the_policy_table(name):
    t = table_rows(build_table(), name)
    st = start(name)
    f = lambda col: t[col].astype(float)   # noqa: E731
    np.testing.assert_allclose(st["reserves_bn"], f("reserves_bn"), atol=TOL)
    np.testing.assert_allclose(st["level1_securities_bn"], f("level1_securities_book_bn"), atol=TOL)
    np.testing.assert_allclose(st["level2a_securities_bn"], f("level2a_securities_book_bn"), atol=TOL)
    np.testing.assert_allclose(st["loans_bn"], f("loans_bn"), atol=TOL)
    np.testing.assert_allclose(st["equity_bn"], f("equity_bn"), atol=TOL)
    np.testing.assert_allclose(st["total_assets_bn"], f("total_assets_bn"), atol=TOL)
    np.testing.assert_allclose(st["dw_prepositioned_left_bn"], f("loan_capacity_lendable_bn"), atol=TOL)
    np.testing.assert_allclose(st["dw_prepos_mv_level1_bn"], f("fed_level1_securities_mv_bn"), atol=TOL)
    np.testing.assert_allclose(st["dw_prepos_mv_level2a_bn"], f("fed_level2a_securities_mv_bn"), atol=TOL)
    np.testing.assert_allclose(st["fhlb_pledged_loans_bn"], f("loans_still_at_fhlb_bn"), atol=TOL)
    np.testing.assert_allclose(st["routine_rate"], f("routine_borrowing_rate"), atol=TOL)
    np.testing.assert_allclose(st["credit_left_bn"], f("c_credit_bn"), atol=TOL)
    np.testing.assert_array_equal(st["tested"], t["tested_last_90_days"] == "yes")
    np.testing.assert_array_equal(st["non_compliant"], t["b_non_compliant"] == "yes")


def test_default_episode_is_the_status_quo():
    # With no setup the episode builds policy A through the setup builder: same start as before M1.7b.
    rnd = draw_info_randoms(CFG["seed"], N)
    plain = start_episode(BANKS, 0.0, draw_noise(CFG["seed"], N, 4, AGENTS), info_randoms=rnd)
    a = start("A")
    for k in ("reserves_bn", "dw_prepositioned_left_bn", "dw_unpledged_left_bn", "fhlb_pledged_loans_bn",
              "tested", "routine_rate", "credit_left_bn"):
        np.testing.assert_array_equal(plain[k], a[k])
    assert np.all(plain["credit_left_bn"] == 0) and not plain["non_compliant"].any()


@pytest.mark.parametrize("name", POLICY_ORDER)
def test_balance_sheets_balance_at_start_and_after_one_step(name):
    st = start(name)
    check_balances(st)
    fs = start_state(SETUPS[name]["banks"], FS, SETUPS[name]["tested"], SETUPS[name]["placement"])
    step(fs, {"uninsured_deposits_bn": 0.4 * fs["uninsured_deposits_bn"]})
    check_balances(fs)


# ---------------------------------------------------------------- the window on prepositioned securities

def one_step(tested):
    """One waterfall half-day under B's setup: a forced withdrawal of 60% of uninsured deposits.

    No depositors, lenders, decision or information: engine/funding.py alone, window open.
    """
    s = SETUPS["B"]
    st = start_state(s["banks"], FS, np.full(N, tested), s["placement"])
    before = compute_lcr(st, LCR_S)
    rec = step(st, {"uninsured_deposits_bn": 0.6 * st["uninsured_deposits_bn"]})
    return st, rec, before


def test_tested_prepositioned_securities_pay_the_same_half_day():
    st, rec, _ = one_step(tested=True)
    used = rec["used_dw_tested_level1"] + rec["used_dw_tested_level2a"]
    assert (used > 0).any()
    # Same half-day: the loan is booked and the cash has paid the withdrawal this step.
    np.testing.assert_allclose(rec["paid_now"][used > 0] >= used[used > 0], True)
    assert st["lags"]["dw_tested_level1"] == 0 and st["lags"]["dw_tested_level2a"] == 0
    # Order (Clarification 12 item 4): only after the window on tested loans is used up.
    loans_full = np.isclose(rec["used_dw_tested"], rec["capacity_dw_tested"])
    assert np.all(loans_full[used > 0])
    # Never more than what is prepositioned.
    assert np.all(st["dw_prepos_mv_level2a_bn"] >= -TOL) and np.all(st["dw_prepos_mv_level1_bn"] >= -TOL)


def test_untested_prepositioned_securities_wait_a_day():
    st, rec, _ = one_step(tested=False)
    assert np.all(rec["used_dw_tested_level1"] == 0) and np.all(rec["used_dw_tested_level2a"] == 0)
    # They are still offered by the window, but through the next-day securities source (contract 7: 1 day).
    assert st["lags"]["dw_level1"] == 2 and st["lags"]["dw_level2a"] == 2
    s = SETUPS["B"]
    fresh = start_state(s["banks"], FS, np.zeros(N, bool), s["placement"])   # before any withdrawal
    prepos = s["placement"]["fed_level2a_mv_bn"] * FS["discount_window"]["margins"]["level2a"]
    assert np.all(_capacity(fresh, "dw_tested_level2a") == 0)
    assert np.all(_capacity(fresh, "dw_level2a") >= prepos - 1e-9)
    np.testing.assert_allclose(st["incoming"]["dw_level2a"][:, 2], rec["used_dw_level2a"])   # any use arrives next day


def test_pledged_securities_leave_hqla_unpledged_stay():
    st, rec, before = one_step(tested=True)
    after = compute_lcr(st, LCR_S)
    for c in ("level1", "level2a"):
        gone = st[f"repo_pledged_mv_{c}_bn"] + st[f"dw_pledged_mv_{c}_bn"]
        np.testing.assert_allclose(after[f"{c}_securities_mv_bn"], before[f"{c}_securities_mv_bn"] - gone, atol=1e-9)
    # A bank that pledged nothing keeps every prepositioned security in HQLA.
    none = (st["dw_pledged_mv_level2a_bn"] == 0) & (st["repo_pledged_mv_level2a_bn"] == 0)
    assert none.any()
    np.testing.assert_allclose(after["level2a_securities_mv_bn"][none], before["level2a_securities_mv_bn"][none])


def test_repo_outflow_rates_by_collateral():
    # 12 CFR 249.32(j)(1)(i)-(ii): 0% for repo against Level 1, 15% against Level 2A.
    banks = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in BANKS.items()}
    plain = compute_lcr(banks, LCR_S)["gross_outflows_bn"]
    banks["repo_out_level1_bn"] = np.full(N, 10.0)
    banks["repo_out_level2a_bn"] = np.full(N, 20.0)
    np.testing.assert_allclose(compute_lcr(banks, LCR_S)["gross_outflows_bn"], plain + 0.15 * 20.0)
    assert LCR_S["outflow_rates"]["repo_level1"] == 0.0 and LCR_S["outflow_rates"]["repo_level2a"] == 0.15


# ---------------------------------------------------------------- Option C in the episode

def test_stress_trigger_lifts_the_ceiling():
    cfg = {**CFG, "lcr_credit": {**CFG["lcr_credit"], "stress_trigger_fires": True}}
    on = policy_setup(BANKS, "C", cfg, RANDOMS, FS, LCR_S, INFO)
    off = SETUPS["C"]
    np.testing.assert_allclose(on["ceiling_limit_bn"], off["ceiling_limit_bn"] * 0.30 / 0.20)
    np.testing.assert_allclose(on["credit_bn"], off["credit_if_trigger_fires_bn"])
    st = start_episode(BANKS, 0.0, draw_noise(CFG["seed"], N, 4, AGENTS),
                       info_randoms=draw_info_randoms(CFG["seed"], N), setup=on)
    np.testing.assert_allclose(st["credit_left_bn"], on["credit_bn"])
    # Release stays sized on ordinary-course credit (Clarification 11 item 1).
    np.testing.assert_allclose(on["banks"]["reserves_bn"], off["banks"]["reserves_bn"])


def test_credit_falls_by_amount_drawn_in_the_episode():
    # One episode step with no shock (nobody withdraws, no lender refuses) and a forced draw of $2bn.
    st = start("C", forced_draws={0: 2.0})
    st["info_cfg"] = INFO
    st.update({k: v for k, v in no_information_randoms(N).items() if k in ("leak_u", "read_u")})
    credit0 = st["credit_left_bn"].copy()
    episode_step(st)
    drawn = st["dw_drawn_total_bn"]
    assert np.all(drawn > 0)
    np.testing.assert_allclose(st["credit_left_bn"], np.maximum(credit0 - drawn, 0))
    # The reported LCR counts only the credit left.
    lcr = compute_lcr(st, LCR_S)
    np.testing.assert_allclose(reported_lcr(st, LCR_S), (lcr["hqla_bn"] + st["credit_left_bn"]) / lcr["calibrated_outflows_bn"])


def test_disclosed_lcr_includes_credit():
    st = start("C")
    lcr = compute_lcr(st, LCR_S)
    np.testing.assert_allclose(st["lcr_start"], (lcr["hqla_bn"] + SETUPS["C"]["credit_bn"]) / lcr["calibrated_outflows_bn"])
    np.testing.assert_allclose(st["five_day_ratio_start"], SETUPS["C"]["five_day_ratio"])


# ---------------------------------------------------------------- only the setup builder knows a name

POLICY_NAMES = {name for name in CFG["policies"]}
BUILDER = ROOT / "engine" / "policies.py"
TABLE_WRITER = ROOT / "engine" / "write_policy_table.py"   # lists the names to write one table; holds no rule


def model_files():
    return sorted(p for d in ("engine", "agents") for p in (ROOT / d).glob("*.py"))


def test_no_function_takes_a_policy_name_outside_the_setup_builder():
    for path in model_files():
        if path == BUILDER:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.Lambda)):
                args = [a.arg for a in node.args.args + node.args.kwonlyargs]
                assert not {"policy", "policy_name"} & set(args), f"{path.name}: {getattr(node, 'name', 'lambda')}"


def test_policy_names_appear_only_as_the_setup_builders_argument():
    for path in model_files():
        if path in (BUILDER, TABLE_WRITER):
            continue
        tree = ast.parse(path.read_text())
        allowed = set()
        for node in ast.walk(tree):   # a name passed straight to policy_setup(...) is the one allowed use
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "policy_setup":
                allowed |= {id(a) for a in node.args}
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for c in [node.left, *node.comparators]:
                    assert not (isinstance(c, ast.Constant) and c.value in POLICY_NAMES), \
                        f"{path.name} line {node.lineno} compares to a policy name"
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) != "policy_setup":
                for a in node.args:
                    assert not (isinstance(a, ast.Constant) and a.value in POLICY_NAMES and id(a) not in allowed), \
                        f"{path.name} line {node.lineno} passes a policy name to {ast.unparse(node.func)}"


# ---------------------------------------------------------------- Amendment 4: window loans in the LCR

def test_window_loan_outflow_rates_by_collateral():
    # Amendment 4: 0% against Level 1, 15% against Level 2A, 25% against loans (12 CFR 249.32(j)(1)(i)-(iii)).
    banks = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in BANKS.items()}
    plain = compute_lcr(banks, LCR_S)["gross_outflows_bn"]
    banks.update(dw_out_level1_bn=np.full(N, 10.0), dw_out_level2a_bn=np.full(N, 20.0),
                 dw_out_loans_bn=np.full(N, 40.0))
    np.testing.assert_allclose(compute_lcr(banks, LCR_S)["gross_outflows_bn"], plain + 0.15 * 20 + 0.25 * 40)
    assert LCR_S["outflow_rates"]["dw_loans_grid"] == [0.0, 0.25, 1.0]
    for rate in LCR_S["outflow_rates"]["dw_loans_grid"]:   # sensitivity points
        s = {**LCR_S, "outflow_rates": {**LCR_S["outflow_rates"], "dw_loans": rate}}
        np.testing.assert_allclose(compute_lcr(banks, s)["gross_outflows_bn"], plain + 0.15 * 20 + rate * 40)


@pytest.mark.parametrize("name", ["A", "B"])
def test_window_loans_by_collateral_add_up(name):
    # One waterfall step (no behavior), then a forced draw ahead of need: the three
    # collateral lines always add up to the window loans booked, and balance sheets balance.
    from engine.funding import force_dw_draw
    s = SETUPS[name]
    st = start_state(s["banks"], FS, np.ones(N, bool), s["placement"])
    step(st, {"uninsured_deposits_bn": 0.6 * st["uninsured_deposits_bn"]})
    force_dw_draw(st, 5.0)
    by_collateral = st["dw_out_level1_bn"] + st["dw_out_level2a_bn"] + st["dw_out_loans_bn"]
    np.testing.assert_allclose(by_collateral, st["dw_loans_bn"])
    assert (st["dw_out_loans_bn"] > 0).any()
    check_balances(st)
