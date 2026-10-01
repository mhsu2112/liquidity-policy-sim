"""Demo of the funding waterfall (run with `make demo-waterfall`).

All 40 banks face the same outflow: $10bn of uninsured deposits leave on the
morning of day 1, and $40bn that afternoon. The run continues to the end of
day 3 so late cash can be seen arriving. The account is printed for SVB-01
and GSIB-01 only.

This is a mechanical demonstration under the status quo (policy A). It is not
a stress scenario and it compares no policies.
"""

import numpy as np

from engine.balance_sheet import check_balances
from engine.banks import generate_banks
from engine.funding import LABELS, start_state, step

OUTFLOWS_BN = [10.0, 40.0]  # session M1.3 brief: $10bn, then $40bn
DAYS_SHOWN = 3
SHOW = ["SVB-01", "GSIB-01"]


def when(t):
    return f"Day {t // 2 + 1} {'morning' if t % 2 == 0 else 'afternoon'}"


def money(x):
    # Small amounts in millions, so nothing real is rounded away to "$0.0bn".
    return f"${x * 1000:,.0f}m" if 0 < abs(x) < 0.1 else f"${x:,.1f}bn"


def describe(st, rec, i):
    """One bank's half-day in plain English."""
    t, lines = rec["t"], []
    head = f"{when(t)}: "
    head += f"{money(rec['outflow'][i])} of deposits left." if rec["outflow"][i] > 0 else "no new outflow."
    lines.append(head)
    if rec["arrived"][i] > 0:
        parts = [f"{money(rec[f'arrived_{k}'][i])} {LABELS[k]}" for k in st["order"]
                 if rec[f"arrived_{k}"][i] > 0]
        lines.append(f"  Cash arrived: {', '.join(parts)}. "
                     f"{money(rec['paid_late'][i])} of it paid depositors who were waiting.")
    now = [f"{money(rec[f'used_{k}'][i])} {LABELS[k]}" for k in st["order"]
           if st["lags"][k] == 0 and rec[f"used_{k}"][i] > 0]
    late = [f"{money(rec[f'used_{k}'][i])} {LABELS[k]} (arrives {when(t + st['lags'][k])})"
            for k in st["order"] if st["lags"][k] > 0 and rec[f"used_{k}"][i] > 0]
    if now:
        lines.append(f"  Paid now from: {', '.join(now)}.")
    if late:
        lines.append(f"  Not enough cash today, so these were set in motion and depositors wait: {'; '.join(late)}.")
    if rec["realized_loss"][i] > 0:
        lines.append(f"  Selling securities realized a loss of {money(rec['realized_loss'][i])}, which cuts equity.")
    lines.append(f"  Shortfall (no source could cover it): {money(rec['shortfall'][i])}. "
                 f"Still owed to depositors: {money(rec['unpaid_end'][i])}. "
                 f"Reserves {money(st['reserves_bn'][i])}; equity {money(st['equity_bn'][i])}.")
    return "\n".join(lines)


def main():
    banks = generate_banks()
    st = start_state(banks)
    rows = {b: int(np.flatnonzero(banks["bank_id"] == b)[0]) for b in SHOW}
    start = {b: (st["reserves_bn"][i], st["equity_bn"][i]) for b, i in rows.items()}
    log = {b: [] for b in SHOW}
    for t in range(DAYS_SHOWN * st["settings"]["time"]["steps_per_day"]):
        out = OUTFLOWS_BN[t] if t < len(OUTFLOWS_BN) else 0.0
        rec = step(st, {"uninsured_deposits_bn": out})  # all 40 banks at once
        check_balances(st)  # stops with an error if any balance sheet fails to balance
        for b, i in rows.items():
            log[b].append(describe(st, rec, i))

    print("Funding waterfall demo (sessions M1.3, M1.3b): status quo, repo always rolls, "
          "no borrowing decision, no stigma.")
    print("All 40 banks were run together; every balance sheet balanced after every half-day.\n")
    for b, i in rows.items():
        res, eq = start[b]
        print(f"=== {b} ({banks['archetype'][i]}): total assets {money(banks['total_assets_bn'][i])}, "
              f"reserves {money(res)} (floor {money(st['reserve_floor_bn'][i])}), equity {money(eq)} ===")
        print("\n".join(log[b]))
        print()


if __name__ == "__main__":
    main()
