"""Demo of one full episode (run with `make demo-episode`), session M1.6.

Part 1: SVB-01 under policy A, half-day by half-day in plain English: what
depositors and lenders did, what the bank projected, both sides of the
borrowing rule, what it decided, how the window lent, who learned of it, and
how the episode ended.

Part 2: a short table of how the outcome moves across three market stigma
levels and two supervisory settings, all rows in one batch with the same
random numbers. DIV-01 is added for contrast: a slower run, where the rule
can bind. Behavioral settings are FROZEN at params-frozen (M1.10); this shows
mechanics, not results.
"""

import numpy as np

from engine.banks import generate_banks
from engine.demo_info import when
from engine.episode import CONFIG, draw_noise, load_yaml, run_episode
from engine.funding import LABELS
from engine.information import draw_info_randoms, load_information_settings
from engine.outcomes import episode_outcomes
from engine.write_banks import ROOT, stamps, write_csv

OUT = ROOT / "outputs" / "demo_episode.csv"
SETTINGS = [CONFIG / f for f in ("decision.yaml", "information.yaml", "funding.yaml", "agents.yaml", "params_frozen.yaml",
                                 "scenarios/demo_episode.yaml", "banks/archetypes.yaml")]


def rows_of(banks, ids, reps):
    """Each named bank repeated `reps` times, as rows (bank by bank)."""
    idx = np.repeat([int(np.flatnonzero(banks["bank_id"] == b)[0]) for b in ids], reps)
    return {k: (v[idx] if isinstance(v, np.ndarray) else v) for k, v in banks.items()}, idx


def narrate(st, recs, k, info):
    """Part 1: one row, half-day by half-day, up to and including its end."""
    end = st["end_step"][k]
    h = st["distress_shock"] if np.ndim(st["distress_shock"]) == 0 else st["distress_shock"][k]
    for r in recs[:end + 1]:
        t = r["t"]
        g = lambda key: r[key][k]
        dep = g("fast_out") + g("slow_out") + g("insured_out")
        refused = g("repo_refused") + g("stwf_refused")
        print(f"{when(t)}  Confidence {g('confidence'):.2f}. Depositors withdraw ${dep:.1f}bn"
              + (f"; lenders refuse to roll ${refused:.1f}bn" if refused >= 0.05 else "") + ".")
        lhs = g("decision_p_fail")
        rhs = g("decision_stigma_cost") + g("decision_sup_cost")
        print(f"{'':10}Projection (without the window, next two days): gap ${g('decision_gap'):.1f}bn; "
              f"chance of failing {lhs:.0%}.")
        print(f"{'':10}Rule: {lhs:.3f} vs {g('decision_p_known'):.2f} known x {st['stigma_eff'][k]:.3f} stigma x "
              f"{h:.2f} hit = {g('decision_stigma_cost'):.3f}, + supervisory {g('decision_sup_cost'):.3f} "
              f"= {rhs:.3f}  ->  {'BORROW' if g('decision_borrow') else 'wait'}.")
        paid = [f"{LABELS[s.removeprefix('used_')]} {r[s][k]:.1f}" for s in r
                if s.startswith("used_") and r[s][k] >= 0.05]
        if paid:
            print(f"{'':10}Paid from: {', '.join(paid)}.")
        if g("dw_ahead") >= 0.05:
            lag = "the same half-day" if st["tested"][k] else "a day later (collateral untested)"
            print(f"{'':10}Asks the window for ${g('dw_ahead'):.1f}bn ahead of need; cash arrives {lag}.")
        if g("unpaid_end") >= 0.05:
            print(f"{'':10}Still owed at the end of the half-day: ${g('unpaid_end'):.1f}bn "
                  f"(failure tolerance ${st['fail_tol_bn'][k]:.2f}bn).")
        for ev in st["events"]:
            if ev["t"] == t and ev["mask"][k] and not ev["route"].startswith("inference"):
                read = ""
                if "read" in ev:
                    read = " Read as distress." if ev["new_distress"][k] else " Not read as distress."
                print(f"{'':10}{ev['observer'].upper()} learns via {ev['route'].replace('_', ' ')}.{read}")
    print(f"END: {when(end)}: {episode_outcomes(st)['end_state'][k]}. Nothing after this counts.\n")


def main():
    scen = load_yaml("scenarios/demo_episode.yaml")
    agents, info = load_yaml("agents.yaml"), load_information_settings()
    banks = generate_banks()
    steps = 2 * scen["days"]

    print("Episode demo (session M1.6): policy A only. Behavioral settings FROZEN at params-frozen (M1.10):")
    print("this shows the machinery working, not how any bank or policy would fare.")
    print("Disclosure: the project's sponsor publicly advocated a version of Option B (see README).\n")

    # ---- Part 1
    one, _ = rows_of(banks, [scen["bank"]], 1)
    st, recs = run_episode(one, scen["shock"], draw_noise(scen["seed"], 1, steps, agents),
                           info_randoms=draw_info_randoms(scen["seed"], 1), stigma=scen["market_stigma"],
                           supervision=scen["supervision"])
    print(f"=== Part 1: {scen['bank']}, a news shock of {scen['shock']} on day 1, market stigma "
          f"{scen['market_stigma']}, supervision '{scen['supervision']}' ===")
    print(f"Total assets ${one['total_assets_bn'][0]:.1f}bn; uninsured deposits ${one['uninsured_deposits_bn'][0]:.1f}bn. "
          f"Collateral tested in the last 90 days: {'yes' if st['tested'][0] else 'no'} (drawn up front at r = "
          f"{st['routine_rate'][0]}).")
    print("Fails if more than 0.1% of starting assets is still owed at the end of a half-day, or equity goes negative.\n")
    narrate(st, recs, 0, info)

    # ---- Part 2: every combination for both banks in one batch, same random numbers for a bank's rows
    sig, sup = scen["table"]["stigma"], scen["table"]["supervision"]
    combos = [(s, v) for s in sig for v in sup]
    m = len(combos)
    ids = [scen["bank"], scen["table"]["contrast_bank"]]
    rows, _ = rows_of(banks, ids, m)
    noise = np.repeat(draw_noise(scen["seed"], len(ids), steps, agents), m, axis=0)
    rnd = {k: np.repeat(v, m) for k, v in draw_info_randoms(scen["seed"], len(ids)).items()}
    shock = np.repeat([scen["shock"], scen["table"]["contrast_shock"]], m)
    stb, _ = run_episode(rows, shock, noise, info_randoms=rnd, stigma=np.tile([c[0] for c in combos], len(ids)),
                         supervision=np.tile(np.array([c[1] for c in combos], object), len(ids)),
                         stop_when_all_ended=True)
    o = episode_outcomes(stb)
    fmt = lambda x: "never" if np.isnan(x) else when(int(x))
    print("=== Part 2: how the outcome moves with stigma and supervision (same random numbers in every row) ===")
    print(f"{'Bank':8} {'Shock':>5} {'Stigma':>6} {'Eff.':>5} {'Supervision':11} {'Cost':>5}  {'End':22} "
          f"{'Gap seen':10} {'Borrowed':10} {'Wait':>4} {'Owed':>6} {'Window':>6}")
    for j in range(len(o["bank_id"])):
        hes = "" if np.isnan(o["hesitation_steps"][j]) else f"{o['hesitation_steps'][j]:.0f}"
        print(f"{o['bank_id'][j]:8} {shock[j]:5.2f} {combos[j % m][0]:6.2f} {o['effective_stigma'][j]:5.3f} "
              f"{combos[j % m][1]:11} {o['effective_supervisory_cost'][j]:5.3f}  "
              f"{o['end_state'][j] + ', ' + when(o['end_step'][j]):22} {fmt(o['shortfall_seen_step'][j]):10} "
              f"{fmt(o['first_borrowed_step'][j]):10} {hes:>4} {o['peak_owed_bn'][j]:6.1f} "
              f"{o['official_support_bn'][j]:6.1f}")
    print("Wait = half-days from the projection first showing a gap to the first window loan (negative: borrowed "
          "before the central projection showed a gap).\nOwed = largest amount still owed at the end of a half-day "
          "($bn). Window = discount window lending agreed ($bn, official support).")

    cols = {k: (np.char.mod("%.6f", v) if np.asarray(v).dtype.kind == "f" else v) for k, v in o.items()}
    cols = {"shock": np.char.mod("%.2f", shock), "market_stigma": np.char.mod("%.2f", stb["market_stigma"]),
            "supervision": np.tile(np.array([c[1] for c in combos]), len(ids)), **cols,
            **stamps(len(o["bank_id"]), *SETTINGS)}
    path = write_csv(cols, OUT)
    print(f"\nWrote {path.relative_to(ROOT)} (open in Excel).")


if __name__ == "__main__":
    main()
