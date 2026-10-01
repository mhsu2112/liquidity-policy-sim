"""Mechanics checks on the M1.11 validation banks (Clarification 16). No check result is asserted here.

The banks match Clarification 16's stated totals and balance; Signature's capital-call and CRE loans
are out of the window pools only; the S2 shock is Amendment 5's; the frozen values are untouched.
"""

import numpy as np
import pytest
import yaml

from engine.balance_sheet import check_balances
from engine.collateral import loan_capacity, total
from engine.frozen import frozen_fingerprint
from engine.policies import policy_setup
from validation.banks import midpoint_bank, remove_from_window
from validation.checks import CHECKS_PATH, SCENARIOS_PATH

CFG = yaml.safe_load(open(CHECKS_PATH))


@pytest.mark.parametrize("key, bank_id", [("signature", "SIG-VAL"), ("first_republic", "FRC-VAL")])
def test_banks_match_clarification_16(key, bank_id):
    c = CFG[key]
    b = midpoint_bank(bank_id, c["archetype"], c["total_assets_bn"], c["uninsured_share_of_deposits"], 3)
    check_balances(b)
    assert b["total_assets_bn"][0] == pytest.approx(c["total_assets_bn"])
    deposits = b["insured_deposits_bn"] + b["uninsured_deposits_bn"]
    np.testing.assert_allclose(b["uninsured_deposits_bn"] / deposits, c["uninsured_share_of_deposits"])


def test_signature_loans_out_of_the_window_only():
    c = CFG["signature"]
    b = midpoint_bank("SIG-VAL", c["archetype"], c["total_assets_bn"], c["uninsured_share_of_deposits"], 1)
    place = policy_setup(b, "A", randoms={"test_u": np.ones(1)})["placement"]
    p = remove_from_window(place, b, c["capital_call_loans_bn"])
    assert p["fed_cre_baseline_bn"][0] == 0 and p["unpledged_cre_bn"][0] == 0
    usable = (b["ci_loans_bn"][0] - c["capital_call_loans_bn"]) / b["ci_loans_bn"][0]
    assert p["fed_ci_baseline_bn"][0] == pytest.approx(place["fed_ci_baseline_bn"][0] * usable)
    assert total(p, "fhlb_{}_bn")[0] == pytest.approx(total(place, "fhlb_{}_bn")[0])   # Home Loan Bank unchanged
    assert loan_capacity(p)[0] < loan_capacity(place)[0]


def test_scenario_shocks_and_frozen_values_unchanged():
    sc = yaml.safe_load(open(SCENARIOS_PATH))
    assert sc == {"S1": 0.50, "S2": 0.45}            # Clarification 15 item 1; Amendment 5
    assert frozen_fingerprint() == "05f9e763efc16772"
