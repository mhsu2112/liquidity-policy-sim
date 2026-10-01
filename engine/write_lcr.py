"""Write each bank's LCR and its parts (run with `make lcr`).

Produces two files in outputs/:
- banks_lcr.csv: the M1.1 bank columns plus every step of the LCR calculation.
- lcr_worked_examples.xlsx: three banks worked through with live Excel formulas.

Before writing, every balance sheet is checked at book and at market value.
"""

import numpy as np

from engine.balance_sheet import check_balances
from engine.banks import SETTINGS_PATH, generate_banks, load_settings
from engine.lcr import LCR_SETTINGS_PATH, compute_lcr, load_lcr_settings
from engine.lcr_workbook import DEFAULT_WORKBOOK, write_workbook
from engine.write_banks import ROOT, bank_columns, stamps, write_csv

DEFAULT_OUT = ROOT / "outputs" / "banks_lcr.csv"

# Ratio columns are written with more decimals of a fraction; text columns as is.
RATIO_COLUMNS = {"lcr", "outflow_factor"}
TEXT_COLUMNS = {"lcr_status", "meets_100pct"}


def lcr_columns(lcr):
    cols = {}
    for k, v in lcr.items():
        if k in TEXT_COLUMNS:
            cols[k] = v
        elif k in RATIO_COLUMNS:
            cols[k] = np.char.mod("%.6f", v)
        else:
            cols[k] = np.char.mod("%.9f", v)
    return cols


def write_lcr(out_path=DEFAULT_OUT, workbook_path=DEFAULT_WORKBOOK):
    banks = generate_banks(load_settings(SETTINGS_PATH))
    check_balances(banks)
    lcr = compute_lcr(banks, load_lcr_settings(LCR_SETTINGS_PATH))
    n = len(banks["bank_id"])
    cols = {**bank_columns(banks), **lcr_columns(lcr),
            **stamps(n, SETTINGS_PATH, LCR_SETTINGS_PATH)}
    return write_csv(cols, out_path), write_workbook(banks, lcr, workbook_path)


if __name__ == "__main__":
    csv_path, xlsx_path = write_lcr()
    for p in (csv_path, xlsx_path):
        print(f"Wrote {p.relative_to(ROOT)}")
