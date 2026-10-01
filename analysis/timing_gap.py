"""How often failures come from funding that was agreed but arrives the next day (session M1.12).

Policy A only (project Rule 2): S1 and S2 x 40 banks x 35 stigma-supervision cells x 200 runs,
plus the three validation banks at the tuning cell. Frozen settings, unchanged.

For every failed run it reads the timing band recorded at failure (engine/outcomes.py):
"pure timing", "partly covered", "not covered" or "equity below zero". It also asks, of the
same recorded runs, when each would fail under two alternative failure rules (report only;
the engine keeps the strict rule of Clarification 10 item 6):
    grace        fail only if owed exceeds cash already arriving by the next day
    two strikes  fail only if owed is above the tolerance at the end of two half-days in a row
Both are more lenient than the strict rule, so only runs that fail under it can fail under them.
Caveat: the bank's own borrowing decision assumes the strict rule, so this is an upper bound.

Run with `make timing-gap`. Writes outputs/timing_gap.csv and outputs/timing_gap_summary.json.
"""

import json

import numpy as np
import yaml

from engine.banks import generate_banks
from engine.episode import FAILED, draw_noise, episode_step, load_yaml, start_episode
from engine.frozen import frozen_fingerprint
from engine.information import draw_info_randoms
from engine.outcomes import timing_band
from engine.policies import policy_setup
from engine.write_banks import ROOT, write_csv
from validation.banks import midpoint_bank, remove_from_window
from validation.checks import CHECKS_PATH, SCENARIOS_PATH
from validation.svb_bank import build_svb
from validation.tune import load_tuning

SETTINGS_PATH = ROOT / "config" / "analysis" / "timing_gap.yaml"
OUT_CSV = ROOT / "outputs" / "timing_gap.csv"
OUT_JSON = ROOT / "outputs" / "timing_gap_summary.json"
BANDS = ("pure timing", "partly covered", "not covered", "equity below zero")


def load(path):
    with open(path) as f:
        return yaml.safe_load(f)


def run_batch(banks, shock, noise, rnd, stigma, supervision, cell, tested=None, adjust=None, inject=None):
    """Policy-A episodes, keeping only what the timing analysis needs at each half-day."""
    n, steps = noise.shape
    setup = policy_setup(banks, "A", randoms={"test_u": rnd["test_u"]})
    if adjust:
        setup["placement"] = adjust(setup["placement"], setup["banks"])
    st = start_episode(setup["banks"], shock, noise, info_randoms=rnd, stigma=stigma, supervision=supervision,
                       strength_s=cell["strength_s"], distress_shock=cell["distress_hit"], setup=setup, tested=tested)
    owed, on_way, equity = (np.zeros((n, steps)) for _ in range(3))
    for t in range(steps):
        if inject:
            inject(st, t)
        r = episode_step(st)
        owed[:, t], on_way[:, t], equity[:, t] = r["unpaid_end"], r["on_way_next_day"], st["equity_bn"]
    return st, owed, on_way, equity


def first_step(cond):
    """First half-day each row meets `cond` (rows x steps); a large number if never."""
    never = cond.shape[1] + 1000
    return np.where(cond.any(axis=1), cond.argmax(axis=1), never)


def alternative_rules(st, owed, on_way, equity):
    """Failure half-day under the strict, grace and two-strike rules (only strict failures can fail)."""
    tol = st["fail_tol_bn"][:, None]
    broke = equity < 0
    strict = first_step((owed > tol) | broke)
    grace = first_step((owed - on_way > tol) | broke)
    over = owed > tol
    two = np.zeros_like(over)
    two[:, 1:] = over[:, 1:] & over[:, :-1]
    strikes = first_step(two | broke)
    failed = st["end_state"] == FAILED
    horizon = owed.shape[1]
    return {name: failed & (steps < horizon) for name, steps in
            (("strict", strict), ("grace", grace), ("two_strikes", strikes))}, \
        {"grace": grace, "two_strikes": strikes, "strict": strict}


def summarise(st, owed, on_way, equity, mask):
    failed = (st["end_state"] == FAILED) & mask
    bands = timing_band(st)
    fails, steps = alternative_rules(st, owed, on_way, equity)
    n_fail = int(failed.sum())
    out = {"runs": int(mask.sum()), "failed_share": float(failed.sum() / max(mask.sum(), 1))}
    for b in BANDS:
        out[f"band_{b.replace(' ', '_')}_share_of_failures"] = float(((bands == b) & failed).sum() / max(n_fail, 1))
    out["median_owed_at_failure_bn"] = float(np.median(st["owed_at_failure_bn"][failed])) if n_fail else 0.0
    out["median_on_way_at_failure_bn"] = float(np.median(st["on_way_at_failure_bn"][failed])) if n_fail else 0.0
    for name in ("grace", "two_strikes"):
        f = fails[name] & mask
        out[f"failed_share_under_{name}"] = float(f.sum() / max(mask.sum(), 1))
        later = f & failed
        out[f"median_half_days_later_under_{name}"] = (
            float(np.median(steps[name][later] - steps["strict"][later])) if later.any() else 0.0)
    return out


def main():
    cfg, sc, cell = load(SETTINGS_PATH), load(SCENARIOS_PATH), load_tuning()["tuning_cell"]
    agents = load_yaml("agents.yaml")
    steps = 2 * load_yaml("funding.yaml")["time"]["days"]
    banks = generate_banks()
    runs, nb = cfg["runs"], len(banks["bank_id"])
    rows = {k: (np.repeat(v, runs) if isinstance(v, np.ndarray) else v) for k, v in banks.items()}
    archetype = np.repeat(banks["archetype"], runs)
    grid = load(ROOT / "config" / "run_plan.yaml")["cells"]["main"]
    csv_rows, summary = [], {"fingerprint": frozen_fingerprint(), "runs_per_cell": runs, "scenarios": {}}
    for scen in ("S1", "S2"):
        seed = cfg["seeds"][scen]
        noise = draw_noise(seed, nb * runs, steps, agents)       # paired: same draws in every cell
        rnd = draw_info_randoms(seed, nb * runs)
        pooled = []
        for stigma in grid["stigma"]:
            for sup in grid["supervision"]:
                st, owed, on_way, equity = run_batch(rows, sc[scen], noise, rnd, stigma, sup, cell)
                pooled.append((st, owed, on_way, equity))
                for a in dict.fromkeys(banks["archetype"]):
                    s = summarise(st, owed, on_way, equity, archetype == a)
                    csv_rows.append({"scenario": scen, "stigma": stigma, "supervision": sup, "archetype": a, **s})
        summary["scenarios"][scen] = {}
        for a in [*dict.fromkeys(banks["archetype"]), "all"]:
            # Pool every cell: add up counts across cells for this archetype.
            parts = [summarise(st, o, w, e, (archetype == a) if a != "all" else np.ones(len(archetype), bool))
                     for st, o, w, e in pooled]
            summary["scenarios"][scen][a] = pool(parts)
        print(f"{scen}: done ({len(pooled)} cells)")

    vb = {}
    vcfg = load(CHECKS_PATH)
    svb, svb_cfg = build_svb(runs)
    for name, bank, kw in [
        ("SVB (validation)", svb, {"tested": np.full(runs, svb_cfg["tested"])}),
        ("Signature-like", midpoint_bank("SIG-VAL", "svb_like", 110, 0.90, runs),
         {"adjust": lambda p, b: remove_from_window(p, b, vcfg["signature"]["capital_call_loans_bn"])}),
        ("First Republic-like", midpoint_bank("FRC-VAL", "diversified_regional", 212.6, 0.68, runs),
         {"inject": consortium(vcfg["first_republic"])})]:
        seed = cfg["seeds"]["validation"]
        st, o, w, e = run_batch(bank, sc["S1"], draw_noise(seed, runs, steps, agents), draw_info_randoms(seed, runs),
                                cell["stigma"], cell["supervision"], cell, **kw)
        vb[name] = summarise(st, o, w, e, np.ones(runs, bool))
    summary["validation_banks_S1"] = vb

    write_csv({k: np.array([r[k] for r in csv_rows]) for k in csv_rows[0]}, OUT_CSV)
    OUT_JSON.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {OUT_CSV.relative_to(ROOT)} and {OUT_JSON.relative_to(ROOT)}")


def consortium(c):
    arrive = (c["consortium_day"] - 1) * 2

    def inject(st, t):
        if t == arrive:
            for k in ("uninsured_deposits_bn", "reserves_bn", "total_assets_bn"):
                st[k] += c["consortium_deposit_bn"]
    return inject


def pool(parts):
    """Combine per-cell summaries into one, weighting by runs (shares) and failures (band shares)."""
    runs = sum(p["runs"] for p in parts)
    fails = [p["failed_share"] * p["runs"] for p in parts]
    out = {"runs": runs, "failed_share": sum(fails) / max(runs, 1)}
    for k in parts[0]:
        if k.startswith("band_"):
            out[k] = sum(p[k] * f for p, f in zip(parts, fails)) / max(sum(fails), 1)
        elif k.startswith("failed_share_under_"):
            out[k] = sum(p[k] * p["runs"] for p in parts) / max(runs, 1)
        elif k.startswith("median_"):
            vals = [p[k] for p, f in zip(parts, fails) if f > 0]
            out[k] = float(np.median(vals)) if vals else 0.0   # median of cell medians
    return out


if __name__ == "__main__":
    main()
