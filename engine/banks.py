"""Draw the 40 synthetic banks from the contract's ranges (session M1.1).

Rules followed (docs/contract.md section 1; docs/amendments.md Clarifications 1-2):
- Every range is drawn uniformly, with the fixed seed in the settings file.
- Securities + reserves + loans may not exceed 100% of assets; a bank whose
  draw does, redraws those three shares. Whatever is left is "other assets".
- Equity and short-term wholesale funding are drawn; everything else on the
  liability side is deposits, split insured / uninsured.
- Level 2A is whatever part of securities is not Level 1.
- LCR category and calibration come straight from the bank's type.

Vectorized: each quantity is an array with one entry per bank, and every step
updates all 40 banks at once. No step loops over individual banks.
"""

from pathlib import Path

import numpy as np
import yaml

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "banks" / "archetypes.yaml"

# The ranges drawn for every bank, in the fixed order they are drawn. Changing
# this order would change which random number each value gets, so it is fixed.
# The three asset shares come first because they may need redrawing (rule 1).
ASSET_SHARES = [
    "securities_share_of_assets",
    "reserves_share_of_assets",
    "loans_share_of_assets",
]
OTHER_DRAWS = [
    "total_assets_bn",
    "level1_share_of_securities",
    "unrealized_loss_share_of_securities",
    "eligible_share_of_loans",
    "equity_share_of_assets",
    "stwf_share_of_liabilities",
    "uninsured_share_of_deposits",
]

# Safety stop for the redraw step, not a model parameter. With the contract's
# ranges a bank needs a handful of redraws at most; hitting this limit would
# mean the ranges cannot fit inside 100% at all.
MAX_REDRAW_ROUNDS = 10_000


def load_settings(path=SETTINGS_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


def _per_bank(settings, key):
    """Spread one setting from each type across that type's banks.

    Returns one value per bank, in bank order (all banks of the first type,
    then the second type, and so on).
    """
    n = settings["banks_per_archetype"]
    return np.repeat(np.array([a[key] for a in settings["archetypes"].values()]), n, axis=0)


def _draw(rng, settings, key, rows=None):
    """Uniform draw within each bank's [low, high] range for one variable."""
    bounds = _per_bank(settings, key)
    if rows is not None:
        bounds = bounds[rows]
    return rng.uniform(bounds[:, 0], bounds[:, 1])


def generate_banks(settings=None):
    """Return the 40 banks as a dict of arrays (one entry per bank), in $bn."""
    if settings is None:
        settings = load_settings()
    rng = np.random.default_rng(settings["seed"])
    n = settings["banks_per_archetype"]
    types = list(settings["archetypes"])

    # Who each bank is: type, readable ID, and LCR treatment by type (rule 3).
    archetype = np.repeat(np.array(types), n)
    prefixes = _per_bank(settings, "id_prefix")
    serial = np.tile(np.arange(1, n + 1), len(types))
    bank_id = np.char.add(np.char.add(prefixes.astype(str), "-"), np.char.zfill(serial.astype(str), 2))

    # Rule 1: draw the three asset shares; any bank whose shares add up to more
    # than 100% of assets redraws all three, until every bank fits.
    shares = {k: _draw(rng, settings, k) for k in ASSET_SHARES}
    for _ in range(MAX_REDRAW_ROUNDS):
        too_big = sum(shares.values()) > 1.0
        if not too_big.any():
            break
        rows = np.flatnonzero(too_big)
        for k in ASSET_SHARES:
            shares[k][rows] = _draw(rng, settings, k, rows)
    else:
        raise RuntimeError("Asset shares could not be made to fit within 100% of assets.")

    d = {k: _draw(rng, settings, k) for k in OTHER_DRAWS}

    # Asset side, at book value.
    assets = d["total_assets_bn"]
    securities = shares["securities_share_of_assets"] * assets
    level1 = d["level1_share_of_securities"] * securities
    loans = shares["loans_share_of_assets"] * assets
    reserves = shares["reserves_share_of_assets"] * assets
    mix = {k: np.array([a["loan_mix"][k] for a in settings["archetypes"].values()]).repeat(n)
           for k in ("resi", "cre", "ci")}

    # Liability side (rule 2): equity and wholesale funding are drawn;
    # deposits are the rest, split by the drawn uninsured share.
    equity = d["equity_share_of_assets"] * assets
    liabilities = assets - equity
    stwf = d["stwf_share_of_liabilities"] * liabilities
    deposits = liabilities - stwf
    uninsured = d["uninsured_share_of_deposits"] * deposits

    # No LCR (a null in the settings) is held as NaN so the column stays
    # numeric; the CSV writes it as "none".
    calibration = np.array([np.nan if a["lcr_calibration"] is None else a["lcr_calibration"]
                            for a in settings["archetypes"].values()]).repeat(n)

    return {
        "bank_id": bank_id,
        "archetype": archetype,
        "lcr_category": _per_bank(settings, "lcr_category").astype(str),
        "lcr_calibration": calibration,
        "total_assets_bn": assets,
        # Assets
        "reserves_bn": reserves,
        "securities_bn": securities,
        "level1_securities_bn": level1,
        "level2a_securities_bn": securities - level1,  # Clarification 2
        "loans_bn": loans,
        "resi_loans_bn": mix["resi"] * loans,
        "cre_loans_bn": mix["cre"] * loans,
        "ci_loans_bn": mix["ci"] * loans,
        "other_assets_bn": assets - securities - reserves - loans,  # not liquid, not collateral
        # Memo items: not separate balance sheet lines
        "unrealized_loss_bn": d["unrealized_loss_share_of_securities"] * securities,
        "eligible_loans_bn": d["eligible_share_of_loans"] * loans,
        # Liabilities and equity
        "insured_deposits_bn": deposits - uninsured,
        "uninsured_deposits_bn": uninsured,
        "stwf_bn": stwf,
        "equity_bn": equity,
        # The drawn shares themselves, on the base the contract states them
        **{k: v for k, v in shares.items()},
        **{k: v for k, v in d.items() if k != "total_assets_bn"},
    }
