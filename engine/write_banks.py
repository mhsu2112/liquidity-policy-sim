"""Write the 40 synthetic banks to outputs/banks.csv (run with `make banks`).

One row per bank. Each balance sheet line appears as a dollar amount ($bn)
and as a share of total assets, so each side of the balance sheet sums to 100%.
The contract's own drawn shares (e.g. uninsured share of *deposits*) follow, so
each can be checked against its range in contract section 1b.

Every row carries three stamps so a file can always be traced to the exact
code and settings that made it: the git commit, a hash of the settings file,
and the Jev-estimate version (not used for the bank population).
"""

import csv
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np

from engine.banks import SETTINGS_PATH, generate_banks, load_settings

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "outputs" / "banks.csv"

# Balance sheet lines, written as $bn and as a share of total assets.
ASSET_LINES = ["reserves", "level1_securities", "level2a_securities",
               "resi_loans", "cre_loans", "ci_loans", "other_assets"]
LIABILITY_LINES = ["insured_deposits", "uninsured_deposits", "stwf", "equity"]
# Subtotals and memo items: helpful for reading, not separate lines.
MEMO_LINES = ["securities", "loans", "unrealized_loss", "eligible_loans"]
# The shares exactly as drawn, on the base the contract states them.
DRAWN_SHARES = ["securities_share_of_assets", "level1_share_of_securities",
                "unrealized_loss_share_of_securities", "reserves_share_of_assets",
                "loans_share_of_assets", "eligible_share_of_loans",
                "stwf_share_of_liabilities", "equity_share_of_assets",
                "uninsured_share_of_deposits"]


def git_commit():
    """Current commit, marked -dirty if there are uncommitted changes."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    commit = git("rev-parse", "--short=12", "HEAD") or "unknown"
    return commit + ("-dirty" if git("status", "--porcelain") else "")


def settings_hash(path=SETTINGS_PATH):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def write_banks(out_path=DEFAULT_OUT, settings_path=SETTINGS_PATH):
    banks = generate_banks(load_settings(settings_path))
    assets = banks["total_assets_bn"]
    stamps = {"git_commit": git_commit(), "config_hash": settings_hash(settings_path),
              "jev_estimate_version": "not used"}

    # Build each column as text, all banks at once; then write rows.
    cols = {
        "bank_id": banks["bank_id"],
        "archetype": banks["archetype"],
        "lcr_category": banks["lcr_category"],
        "lcr_calibration": np.where(np.isnan(banks["lcr_calibration"]), "none",
                                    np.char.mod("%.2f", banks["lcr_calibration"])),
        "total_assets_bn": np.char.mod("%.9f", assets),
    }
    for line in ASSET_LINES + LIABILITY_LINES + MEMO_LINES:
        cols[f"{line}_bn"] = np.char.mod("%.9f", banks[f"{line}_bn"])
        cols[f"{line}_share_of_assets"] = np.char.mod("%.6f", banks[f"{line}_bn"] / assets)
    for k in DRAWN_SHARES:
        cols[f"drawn_{k}"] = np.char.mod("%.6f", banks[k])
    for k, v in stamps.items():
        cols[k] = np.full(len(assets), v)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols.keys())
        w.writerows(zip(*cols.values()))
    return out_path, len(assets)


if __name__ == "__main__":
    path, count = write_banks(*(sys.argv[1:2]))
    print(f"Wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}: "
          f"{count} synthetic banks, one row each.")
