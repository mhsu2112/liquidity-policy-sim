"""Checks on the 40 synthetic banks (session M1.1).

Mechanics only: the right number of banks, every value inside its contract
range, balance sheets that balance, identical output from the same seed, and
the LCR treatment the contract assigns. Nothing here compares policies.
"""

import numpy as np
import pytest

from engine.banks import generate_banks, load_settings
from engine.write_banks import write_banks

SETTINGS = load_settings()
BANKS = generate_banks(SETTINGS)
ONE_DOLLAR_BN = 1e-9  # balance-sheet tolerance: $1, expressed in $ billions


def test_forty_banks_ten_per_type():
    assert len(BANKS["bank_id"]) == 40
    assert len(set(BANKS["bank_id"])) == 40  # every ID is unique
    types, counts = np.unique(BANKS["archetype"], return_counts=True)
    assert sorted(types) == sorted(["svb_like", "diversified_regional", "regional_cat3", "gsib"])
    assert (counts == 10).all()


# Every range in contract section 1b, checked against the value actually used.
# Level 2A is checked too, even though it is not drawn (Clarification 2).
RANGE_CHECKS = {
    "total_assets_bn": BANKS["total_assets_bn"],
    "uninsured_share_of_deposits": BANKS["uninsured_deposits_bn"]
        / (BANKS["uninsured_deposits_bn"] + BANKS["insured_deposits_bn"]),
    "securities_share_of_assets": BANKS["securities_bn"] / BANKS["total_assets_bn"],
    "level1_share_of_securities": BANKS["level1_securities_bn"] / BANKS["securities_bn"],
    "level2a_share_of_securities": BANKS["level2a_securities_bn"] / BANKS["securities_bn"],
    "unrealized_loss_share_of_securities": BANKS["unrealized_loss_bn"] / BANKS["securities_bn"],
    "reserves_share_of_assets": BANKS["reserves_bn"] / BANKS["total_assets_bn"],
    "loans_share_of_assets": BANKS["loans_bn"] / BANKS["total_assets_bn"],
    "eligible_share_of_loans": BANKS["eligible_loans_bn"] / BANKS["loans_bn"],
    "stwf_share_of_liabilities": BANKS["stwf_bn"] / (BANKS["total_assets_bn"] - BANKS["equity_bn"]),
    "equity_share_of_assets": BANKS["equity_bn"] / BANKS["total_assets_bn"],
}


@pytest.mark.parametrize("variable", RANGE_CHECKS)
def test_every_value_inside_its_contract_range(variable):
    values = RANGE_CHECKS[variable]
    tiny = 1e-12  # allows for rounding in the last decimal place only
    for name, arch in SETTINGS["archetypes"].items():
        low, high = arch[variable]
        mine = values[BANKS["archetype"] == name]
        assert (mine >= low - tiny).all() and (mine <= high + tiny).all(), (name, variable)


def test_loan_mix_matches_contract():
    for name, arch in SETTINGS["archetypes"].items():
        rows = BANKS["archetype"] == name
        for k in ("resi", "cre", "ci"):
            share = BANKS[f"{k}_loans_bn"][rows] / BANKS["loans_bn"][rows]
            np.testing.assert_allclose(share, arch["loan_mix"][k])


def test_every_balance_sheet_balances():
    b = BANKS
    assets = (b["reserves_bn"] + b["level1_securities_bn"] + b["level2a_securities_bn"]
              + b["resi_loans_bn"] + b["cre_loans_bn"] + b["ci_loans_bn"] + b["other_assets_bn"])
    liabilities_and_equity = (b["insured_deposits_bn"] + b["uninsured_deposits_bn"]
                              + b["stwf_bn"] + b["equity_bn"])
    assert np.abs(assets - b["total_assets_bn"]).max() < ONE_DOLLAR_BN
    assert np.abs(liabilities_and_equity - b["total_assets_bn"]).max() < ONE_DOLLAR_BN
    # Clarification 1, rule 1: no bank holds negative "other assets".
    assert (b["other_assets_bn"] >= 0).all()
    # Every line is a positive amount (other assets may be zero).
    for k, v in b.items():
        if k.endswith("_bn") and k != "other_assets_bn":
            assert (v > 0).all(), k


def test_written_file_balances(tmp_path):
    # The same check on the CSV, after numbers are written as text.
    import csv
    path, _ = write_banks(tmp_path / "banks.csv")
    rows = list(csv.DictReader(open(path)))
    assert len(rows) == 40
    for r in rows:
        a = sum(float(r[f"{k}_bn"]) for k in ["reserves", "level1_securities", "level2a_securities",
                                              "resi_loans", "cre_loans", "ci_loans", "other_assets"])
        le = sum(float(r[f"{k}_bn"]) for k in ["insured_deposits", "uninsured_deposits", "stwf", "equity"])
        total = float(r["total_assets_bn"])
        assert abs(a - total) < 10 * ONE_DOLLAR_BN and abs(le - total) < 10 * ONE_DOLLAR_BN
        assert r["git_commit"] and r["config_hash"] and r["jev_estimate_version"]


def test_same_seed_gives_identical_file(tmp_path):
    first = write_banks(tmp_path / "first.csv")[0].read_bytes()
    second = write_banks(tmp_path / "second.csv")[0].read_bytes()
    assert first == second


def test_different_seed_gives_different_banks():
    # Confirms the seed is actually used, so the identical-file check means something.
    other = dict(SETTINGS, seed=SETTINGS["seed"] + 1)
    assert not np.array_equal(generate_banks(other)["total_assets_bn"], BANKS["total_assets_bn"])


# Contract section 1c, typed in from the contract text rather than read from
# the settings file, so a typo in the settings file is caught.
CONTRACT_1C = {
    "gsib": ("I-II", 1.00),
    "regional_cat3": ("III", 0.85),
    "svb_like": ("IV", 0.70),
    "diversified_regional": ("IV", None),
}


def test_lcr_treatment_matches_contract():
    assert SETTINGS["seed"] == 20260923  # contract section 1
    for name, (category, calibration) in CONTRACT_1C.items():
        rows = BANKS["archetype"] == name
        assert (BANKS["lcr_category"][rows] == category).all(), name
        if calibration is None:
            assert np.isnan(BANKS["lcr_calibration"][rows]).all(), name
        else:
            assert (BANKS["lcr_calibration"][rows] == calibration).all(), name
