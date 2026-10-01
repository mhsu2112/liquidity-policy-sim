"""Demo of a run (run with `make demo-run`), session M1.4.

All 40 banks are run twice in one batch, once under a mild news shock and once
under a severe one, with the same random draws. SVB-01's two episodes are printed
half-day by half-day. Policy A only; behavioral settings are FROZEN at params-frozen (M1.10),
so the numbers show the mechanics working, not a calibrated result.
"""

import numpy as np

from engine.balance_sheet import check_balances
from engine.banks import generate_banks
from engine.episode import draw_noise, episode_step, load_yaml, start_episode

SHOW = "SVB-01"


def stack(banks, copies):
    """Repeat every bank `copies` times (one block per shock), as rows."""
    return {k: (np.tile(v, copies) if isinstance(v, np.ndarray) else v) for k, v in banks.items()}


def bn(x):
    return f"{x:6.1f}"


def main():
    scen = load_yaml("scenarios/demo.yaml")
    banks = generate_banks()
    n = len(banks["bank_id"])
    names = list(scen["shocks"])
    rows = stack(banks, len(names))
    shock = np.repeat([scen["shocks"][k] for k in names], n)
    steps = scen["days"] * 2
    # Same draws for each bank under every shock: draw once per bank, repeat per shock.
    noise = np.tile(draw_noise(scen["seed"], n, steps, load_yaml("agents.yaml")), (len(names), 1))

    st = start_episode(rows, shock, noise, demo=True)   # a demo: no information random numbers needed
    recs = []
    for _ in range(steps):
        recs.append(episode_step(st))
        check_balances(st)

    i0 = int(np.flatnonzero(banks["bank_id"] == SHOW)[0])
    order, lags = st["order"], st["lags"]
    short = {"reserves": "res", "repo_level1": "repoL1", "repo_level2a": "repoL2A", "repo_next_level1": "repoL1+1d",
             "repo_next_level2a": "repoL2A+1d", "sale_level1": "sellL1", "sale_level2a": "sellL2A",
             "fhlb_line": "FHLB", "fhlb_above_line": "FHLB+1d", "dw_tested": "DW", "dw_untested": "DW+1d",
             "dw_level1": "DW-L1", "dw_level2a": "DW-L2A", "dw_unpledged": "DW-loans"}

    print("Run demo (session M1.4): policy A only; behavioral settings FROZEN at params-frozen (M1.10).")
    print(f"All {n} banks x {len(names)} shocks ran together in one batch; every balance sheet balanced every half-day.")
    print("Amounts in $bn. 'Late' = set in motion now, cash arrives later. Depositors still owed = paid late or shortfall.\n")
    for k, name in enumerate(names):
        i = k * n + i0
        print(f"=== {SHOW}, {name} shock (S = {scen['shocks'][name]}): uninsured deposits "
              f"{banks['uninsured_deposits_bn'][i0]:.1f}, insured {banks['insured_deposits_bn'][i0]:.1f}, "
              f"wholesale {banks['stwf_bn'][i0]:.1f}, equity {banks['equity_bn'][i0]:.1f} ===")
        print(f"{'When':12} {'Conf':>5} {'Fast':>6} {'Slow':>6} {'Insrd':>6} {'Repo':>6} {'Whsl':>6} "
              f"{'Short':>6} {'Owed':>6}  Sources used (late marked *)")
        print(f"{'':12} {'':>5} {'--- deposits leaving ---':>20} {'-- refused --':>13}")
        for r in recs:
            t = r["t"]
            used = [f"{short[s]}{'*' if lags[s] else ''} {r[f'used_{s}'][i]:.1f}" for s in order
                    if r[f"used_{s}"][i] >= 0.05]
            when = f"D{t // 2 + 1} {'am' if t % 2 == 0 else 'pm'}"
            print(f"{when:12} {r['confidence'][i]:5.2f} {bn(r['fast_out'][i])} {bn(r['slow_out'][i])} "
                  f"{bn(r['insured_out'][i])} {bn(r['repo_refused'][i])} {bn(r['stwf_refused'][i])} "
                  f"{bn(r['shortfall'][i])} {bn(r['unpaid_end'][i])}  {', '.join(used) or '-'}")
        left = st["uninsured_deposits_bn"][i] / banks["uninsured_deposits_bn"][i0]
        print(f"After {scen['days']} days: {1 - left:.0%} of uninsured deposits gone; equity "
              f"{st['equity_bn'][i]:.1f} (book), {st['equity_bn'][i] - st['unrealized_loss_bn'][i]:.1f} "
              f"(mark-to-market); still owed to depositors {st['unpaid_outflows_bn'][i]:.1f}.\n")


if __name__ == "__main__":
    main()
