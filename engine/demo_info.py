"""Demo of the information routes (run with `make demo-info`), session M1.5.

SVB-01 under policy A, with one discount window draw forced on day 2 (the bank's
own decision comes in M1.6). Two runs with the same random numbers and the same
market stigma, differing only in the routine borrowing rate r: 0.1 and 2.5.
Each run is paired with a control in which every route is switched off, so the
draw happens but nobody learns of it; the gap in confidence is the effect of
the information. Behavioral settings are M1.10 PLACEHOLDERS.
"""

import numpy as np

from engine.banks import generate_banks
from engine.episode import draw_noise, episode_step, load_yaml, start_episode
from engine.information import (BORROWING_ROUTES, NEVER, draw_info_randoms, load_information_settings,
                                weekly_revealing)

ALL_ROUTES = BORROWING_ROUTES + ("inference", "ratio_disclosure")


def when(t):
    return f"Day {t // 2 + 1:2d} {'am' if t % 2 == 0 else 'pm'}"


def describe(ev, k, info, scen):
    """One event for row k, in plain English."""
    r = ev["route"]
    a = ev["amount"][k] if "amount" in ev else None
    h = info["market_stigma"]["distress_news_shock"]
    if r == "supervisory":
        return f"SUPERVISOR learns of a ${a:.1f}bn discount window draw (supervisory channel: the Fed is the lender)."
    if r == "inference_sale":
        return f"{ev['observer'].upper()} see the bank selling ${a:.1f}bn of securities (inference)."
    if r == "inference_refusal":
        return f"{ev['observer'].upper()} see wholesale/repo lenders refuse ${a:.1f}bn (inference)."
    if r == "ratio_disclosure":
        return (f"MARKET sees the quarterly LCR disclosure: {ev['lcr'][k]:.0%} (prior quarter's average, so it "
                "shows no in-episode draw).")
    text = {"leak": f"MARKET reads a press report naming the bank as a discount window borrower (leak).",
            "announcement": f"MARKET reads the bank's mandatory 8-K: ${a:.1f}bn borrowed from the discount window "
                            "(announcement).",
            "weekly_aggregate": f"MARKET sees the Fed's weekly report: discount window lending up ${a:.1f}bn, no "
                                f"bank named; {ev['revealing'][k]:.0%} revealing (weekly aggregate)."}[r]
    verdict = (f"read as distress -> a {h:.2f} news hit to confidence" if ev["new_distress"][k] else
               "read as distress, but already known as distress: nothing new" if ev["read"][k] else
               "not read as distress: confidence unchanged")
    return f"{text}\n{'':16}Chance read as distress {ev['chance'][k]:.2f}; {verdict}."


def rows_of(banks, i, n):
    """n copies of bank i, as rows."""
    return {k: (np.repeat(v[i:i + 1], n) if isinstance(v, np.ndarray) else v) for k, v in banks.items()}


def main():
    scen, info = load_yaml("scenarios/demo_info.yaml"), load_information_settings()
    agents = load_yaml("agents.yaml")
    banks = generate_banks()
    i = int(np.flatnonzero(banks["bank_id"] == scen["bank"])[0])
    steps = 2 * scen["days"]
    names = list(scen["routine_rates"])
    rates = np.array([scen["routine_rates"][k] for k in names])
    m = len(names)

    # Same news noise and same information random numbers in every run (paired).
    noise1 = draw_noise(scen["seed"], 1, steps, agents)
    rnd1 = draw_info_randoms(scen["seed"], 1)
    fd = {2 * (scen["forced_draw"]["day"] - 1): scen["forced_draw"]["amount_bn"]}
    base = dict(stigma=scen["market_stigma"], strength_s=scen["strength_s"], forced_draws=fd)

    # Batch 1, two rows per r: the actual random numbers, and an ILLUSTRATION with the
    # reading number set to 0, so the first route that reveals the draw is read as distress.
    read_u = np.tile([rnd1["read_u"][0], 0.0], m)
    st = start_episode(rows_of(banks, i, 2 * m), scen["shock"], np.repeat(noise1, 2 * m, axis=0),
                       routine=np.repeat(rates, 2), **base,
                       info_randoms={"leak_u": np.repeat(rnd1["leak_u"], 2 * m), "read_u": read_u})
    recs = [episode_step(st) for _ in range(steps)]
    # Batch 2: every route switched off. The draw happens but nobody learns of it.
    ctl = start_episode(rows_of(banks, i, m), scen["shock"], np.repeat(noise1, m, axis=0), routine=rates,
                        info_randoms={k: np.repeat(v, m) for k, v in rnd1.items()}, routes_off=ALL_ROUTES, **base)
    ctl_recs = [episode_step(ctl) for _ in range(steps)]

    a = banks["total_assets_bn"][i]
    unins = banks["uninsured_deposits_bn"][i]
    print("Information routes demo (session M1.5): policy A only; behavioral settings are PLACEHOLDERS (M1.10).")
    print(f"{scen['bank']}: total assets ${a:.1f}bn. No news shock: the bank is calm, so the only news is the draw.")
    print(f"A ${scen['forced_draw']['amount_bn']:.1f}bn discount window draw is FORCED on day "
          f"{scen['forced_draw']['day']} morning (untested prepositioned loans: cash arrives a day later).")
    print(f"Mandatory announcement threshold: 5% of assets = "
          f"${info['routes']['announcement']['materiality_share_of_assets'] * a:.1f}bn, filed 4 business days later.")
    print(f"Market stigma {scen['market_stigma']:.2f} and strength s = {scen['strength_s']} in both runs. Random numbers "
          f"shared by both runs: leak U = {rnd1['leak_u'][0]:.3f} (a leak needs U below "
          f"{info['routes']['leak']['probability']:.2f}); reading U = {rnd1['read_u'][0]:.3f} (read as distress if "
          "below the chance shown).\n")

    for k, name in enumerate(names):
        row, ill = 2 * k, 2 * k + 1
        print(f"=== Run {k + 1}: routine borrowing r = {rates[k]} ({name}) ===")
        print(f"Effective stigma = {scen['market_stigma']:.2f} x e^(-{scen['strength_s']} x {rates[k]}) = "
              f"{st['stigma_eff'][row]:.3f}.  Weekly report revealing: {st['weekly_revealing'][row]:.0%}.")
        costs = ", ".join(f"{lv.replace('_', ' ')} {c:.2f} -> {c * np.exp(-scen['strength_s'] * rates[k]):.3f}"
                          for lv, c in info["supervisor"]["levels"].items())
        print(f"Supervisory and internal cost, before -> after the routine-borrowing effect (same rule): {costs}.")
        print("Who learned what, and when:")
        seen = {}
        for ev in st["events"]:
            if not ev["mask"][row]:
                continue
            key = (ev["route"], ev["observer"])
            seen[key] = seen.get(key, 0) + 1
            if seen[key] == 1:
                print(f"  {when(ev['t'])}   {describe(ev, row, info, scen)}")
        for (route, obs), c in seen.items():
            if c > 1:
                print(f"  (and {c - 1} more half-day(s) of {route.replace('_', ' ')} seen by {obs})")
        if st["leak_u"][row] >= info["routes"]["leak"]["probability"]:
            print("  No leak in this run.")
        print("Confidence each morning, days 1-%d (1 = calm, 0 = panic):" % scen["days"])
        for label, rr, idx in (("this run", recs, row), ("nobody told", ctl_recs, k),
                               ("illustration: read as distress at first chance", recs, ill)):
            path = " ".join(f"{r['confidence'][idx]:.2f}" for r in rr[::2])
            print(f"  {path}   {label}")
        gone = [1 - x["uninsured_deposits_bn"][j] / unins for x, j in ((st, row), (ctl, k), (st, ill))]
        print(f"After {scen['days']} days, uninsured deposits gone: this run {gone[0]:.0%}; nobody told {gone[1]:.0%}; "
              f"illustration {gone[2]:.0%}.")
        first = next((ev for ev in st["events"] if ev["mask"][ill] and "new_distress" in ev and ev["new_distress"][ill]), None)
        if first is not None:
            print(f"  (In the illustration the {first['route'].replace('_', ' ')} on {when(first['t'])} is read as "
                  "distress.)")
        print()

    # The same set-up repeated with fresh information random numbers: how often each happens.
    b = scen["batch_runs"]
    rnd = draw_info_randoms(scen["batch_seed"], b)
    stb = start_episode(rows_of(banks, i, b * m), scen["shock"], np.repeat(noise1, b * m, axis=0),
                        routine=np.repeat(rates, b), **base,
                        info_randoms={kk: np.tile(v, m) for kk, v in rnd.items()})
    for _ in range(steps):
        episode_step(stb)
    print(f"Repeated {b:,} times per r with fresh random numbers (all {b * m:,} runs in one batch, same numbers for both r):")
    for k, name in enumerate(names):
        sl = slice(k * b, (k + 1) * b)
        read = (stb["distress_from"][sl] != NEVER).mean()
        leaked = stb["delivered"]["leak"][sl].mean()
        gone = (1 - stb["uninsured_deposits_bn"][sl] / unins).mean()
        print(f"  r = {rates[k]}: leaked {leaked:.1%}; read as distress {read:.1%} (named route alone "
              f"{stb['stigma_eff'][k * b]:.1%}); average uninsured deposits gone by day {scen['days']}: {gone:.1%}.")


if __name__ == "__main__":
    main()
