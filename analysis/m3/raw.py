"""Read the raw outcomes written by analysis/m3/run.py and average them the way Clarification 31 says.

A "unit" is one (bank, run) row. Where several cells are pooled, each row's values are first averaged over those
cells (every cell reuses the same draws, so cells are not independent); the 90% interval is then taken across rows.
"""

import json
from pathlib import Path

import numpy as np

from engine.banks import generate_banks

MAIN = ("main", "-", "-")


class Raw:
    def __init__(self, folder):
        folder = Path(folder)
        self.info = json.loads((folder / "run_info.json").read_text())
        self.runs = self.info["runs_per_cell"]
        self.banks = generate_banks()
        self.bank_of_row = np.repeat(np.arange(len(self.banks["bank_id"])), self.runs)
        self.type_of_row = self.banks["archetype"][self.bank_of_row]
        self.data = {}
        for f in sorted(folder.glob("*.npz")):
            block, setting, point, scen = f.stem.split("__")
            with np.load(f) as z:
                for k in z.files:
                    pol, x, u, field = k.split("|")
                    self.data.setdefault((block, setting, point, scen, pol, float(x), u), {})[field] = z[k]

    def has(self, setting, point, scen, pol, x, u):
        return ("sens", setting, point, scen, pol, float(x), u) in self.data

    def batch(self, scen, pol, x, u, setting="-", point="-"):
        """One batch's arrays. A sensitivity falls back to the main grid for policies it does not rerun
        (Clarification 14 item 3: identical by construction). SW_ names come from the feature-switch block."""
        if setting != "-" and self.has(setting, point, scen, pol, x, u):
            return self.data[("sens", setting, point, scen, pol, float(x), u)]
        block = "switch" if pol.startswith("SW_") else "main"
        return self.data[(block, "-", "-", scen, pol, float(x), u)]

    def rows_of(self, scen, pol, x, u, setting="-", point="-"):
        return self.batch(scen, pol, x, u, setting, point)["row"]

    def per_row(self, scen, pol, cells, fn, setting="-", point="-", rows=None):
        """Each row's value of fn(batch arrays), averaged over `cells` (NaN ignored). Rows = all rows unless given."""
        n = len(self.bank_of_row)
        total, count = np.zeros(n), np.zeros(n)
        for x, u in cells:
            b = self.batch(scen, pol, x, u, setting, point)
            v = np.asarray(fn(b), float)
            ok = ~np.isnan(v)
            np.add.at(total, b["row"][ok], v[ok])
            np.add.at(count, b["row"][ok], 1)
        with np.errstate(invalid="ignore"):
            out = total / count
        return out if rows is None else out[rows]

    def count(self, scen, pol, cells, fn, setting="-", point="-", rows=None):
        """How many (row, cell) values of fn are defined (not NaN) over `cells`, for the given rows."""
        total = 0
        for x, u in cells:
            b = self.batch(scen, pol, x, u, setting, point)
            keep = np.ones(len(b["row"]), bool) if rows is None else np.isin(b["row"], rows)
            total += int(np.sum(~np.isnan(np.asarray(fn(b), float)[keep])))
        return total

    def type_rows(self, bank_type):
        return np.flatnonzero(self.type_of_row == bank_type)


# Per-row outcome functions (Clarification 31 B4). Each takes one batch's arrays.
OUTCOME = {
    "survival_rate": lambda b: 1.0 - b["failed"],
    "liquidity_shortfall_bn": lambda b: b["uncovered"],
    "support_bn": lambda b: b["support"],
    "fhlb_peak_bn": lambda b: b["fhlb"],
    "effective_stigma": lambda b: b["eff_stigma"],
    "routine_borrowing_per_quarter": lambda b: b["r"],
    "buffer_gap_pp": lambda b: 100.0 * b["buffer_gap"],
    "hesitation_gap_days": lambda b: b["hesitation"] / 2.0,
    "grace": lambda b: b["grace"],
    "borrowed": lambda b: b["support"] > 0,
}


def false_comfort(cfg):
    fc = cfg["false_comfort"]
    return lambda b: (b["lcr_reported"] >= fc["lcr_at_least"]) & b["failed"] & (b["end_day"] <= fc["fail_by_day"])
