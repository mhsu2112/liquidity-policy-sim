"""Static funding-timing exposure under every policy (session M1.12). No stress episode runs.

For each of the 40 banks under each policy's starting position (engine/policies.py), one
waterfall step with an outflow larger than any bank can pay and no behavior of any kind
(no depositors, lenders, decision or information) measures the capacity in each speed tier:
    same half-day    cash that can pay today
    next day         cash that arrives within the next two half-days
    later            anything slower (e.g. loans not prepositioned, usable from day 11)
The waterfall itself handles overlaps (each security used once, in its stated order).
This is a capacity measurement, the same kind of single forced-withdrawal step used in the
M1.7b wiring tests, not an outcome (project Rule 2).

Run with `make timing-gap` (after the policy-A measurement). Writes outputs/timing_exposure.csv.
"""

import numpy as np

from engine.funding import load_funding_settings, start_state, step
from engine.write_banks import ROOT, write_csv
from engine.write_costs import build_setups
from engine.write_policy_table import POLICY_ORDER

OUT = ROOT / "outputs" / "timing_exposure.csv"


def capacity_by_tier(setup, fs):
    st = start_state(setup["banks"], fs, setup["tested"], setup["placement"])
    everything = {"uninsured_deposits_bn": st["uninsured_deposits_bn"].copy(),
                  "insured_deposits_bn": st["insured_deposits_bn"].copy()}
    rec = step(st, everything)
    same = rec["paid_now"]
    next_day = sum(s[:, 1:3].sum(axis=1) for s in st["incoming"].values())
    later = sum(s[:, 3:].sum(axis=1) for s in st["incoming"].values())
    return same, next_day, later


def main():
    banks, setups = build_setups()
    fs = load_funding_settings()
    cols = {k: [] for k in ("policy", "bank_id", "archetype", "tested", "same_half_day_bn", "next_day_bn",
                            "later_bn", "same_day_share_of_two_days")}
    for name in POLICY_ORDER:
        same, nxt, later = capacity_by_tier(setups[name], fs)
        cols["policy"] += [name] * len(same)
        cols["bank_id"] += list(banks["bank_id"])
        cols["archetype"] += list(banks["archetype"])
        cols["tested"] += ["yes" if x else "no" for x in setups[name]["tested"]]
        cols["same_half_day_bn"] += list(np.round(same, 6))
        cols["next_day_bn"] += list(np.round(nxt, 6))
        cols["later_bn"] += list(np.round(later, 6))
        cols["same_day_share_of_two_days"] += list(np.round(same / (same + nxt), 6))
    write_csv({k: np.array(v) for k, v in cols.items()}, OUT)
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(cols['policy'])} rows, static, no stress run)")


if __name__ == "__main__":
    main()
