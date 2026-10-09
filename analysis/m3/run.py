"""Run the whole M3 grid (session v0.1-C; run plan = Clarification 14; rules = Clarification 31).

    python -m analysis.m3.run            the full run: main grid, every sensitivity, the feature-switch runs
    python -m analysis.m3.run --dry      1% dry run (every 100th batch, full size); prints a time estimate only
    python -m analysis.m3.run --runs 2   a tiny full grid (tests and smoke checks); same code, fewer runs per cell

One "batch" is one (block, setting, scenario, policy, stigma, supervision): every bank x run row at once,
half-day by half-day, using the engine unchanged. Paired runs: within a scenario every batch uses the same news
noise and information/testing draws for each (bank, run) row, and the same per-bank opt-in draws (the policy
table's), whatever the policy, cell or sensitivity.

Writes outputs/raw/<block>__<setting>__<point>__<scenario>.npz (git-ignored): one array per policy x cell x field.
Nothing here summarizes or compares policies; analysis/m3/build.py does that.
"""

import argparse
import copy
import json
import time
from itertools import product
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import yaml

from analysis.m3.stats import effective_setup, FEATURES, combination_rate
from engine.banks import generate_banks
from engine.episode import FAILED, RUNNING, draw_noise, episode_step, load_yaml, start_episode
from engine.funding import load_funding_settings
from engine.information import draw_info_randoms, load_information_settings
from engine.lcr import load_lcr_settings
from engine.outcomes import episode_outcomes
from engine.policies import draw_policy_randoms, load_policies, policy_setup
from engine.run_plan import load_run_plan

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "config" / "analysis" / "m3.yaml"
RAW = ROOT / "outputs" / "raw"
SCENARIOS = ROOT / "config" / "scenarios" / "scenarios.yaml"
BANDS = {"": 0, "pure timing": 1, "partly covered": 2, "not covered": 3, "equity below zero": 4}


def load_settings():
    return yaml.safe_load(SETTINGS.read_text())


# ---------- the tasks ----------

def switch_name(setup):
    """A name for an unnamed switch combination, e.g. SW_1100 = prepositioning and testing on."""
    return "SW_" + "".join("1" if x else "0" for x in setup)


def extra_combinations(pol_cfg):
    """Effective setups not already run as a named policy (Clarification 14 item 5: 8 of them)."""
    every = {effective_setup({f for f, b in zip(FEATURES, bits) if b}) for bits in product([0, 1], repeat=4)}
    named = {effective_setup({f for f, v in p["switches"].items() if v}) for p in pol_cfg["policies"].values()}
    return sorted(every - named)


def tasks(plan, pol_cfg):
    """Every batch in the run plan, as (block, setting, point, scenario, policy, stigma, supervision)."""
    cells = {g: list(product(plan["cells"][g]["stigma"], plan["cells"][g]["supervision"])) for g in plan["cells"]}
    out = [("main", "-", "-", sc, p, x, u) for sc in plan["scenarios"] for p in plan["policies"] for x, u in cells["main"]]
    for s in plan["sensitivities"]:
        pols = plan["policies"] if s["policies"] == "all" else s["policies"]
        for pt, sc, p, (x, u) in product(s["points"], s.get("scenarios", plan["scenarios"]), pols, cells[s["cells"]]):
            out.append(("sens", s["name"], str(pt), sc, p, x, u))
    for setup in extra_combinations(pol_cfg):
        for sc, (x, u) in product(plan["scenarios"], cells[plan["feature_switches"]["cells"]]):
            out.append(("switch", "-", "-", sc, switch_name(setup), x, u))
    return out


# ---------- one setting's configuration (Clarification 31 B5) ----------

def configure(setting, point, cfg):
    """Settings for one sensitivity point, as copies of the defaults. Returns a dict the batch reads."""
    c = {"fs": load_funding_settings(), "info": load_information_settings(), "lcr": load_lcr_settings(),
         "behavior": load_yaml("params_frozen.yaml"), "pol": load_policies(), "s": None, "hit": None,
         "no_lcr_type": None, "only_type": None}
    info, fs, pol = c["info"], c["fs"], c["pol"]
    if setting == "leak_probability":
        info["routes"]["leak"]["probability"] = float(point)
    elif setting == "leak_lag_days":
        info["routes"]["leak"]["lag_days"] = int(point)
    elif setting == "c_ceiling":
        pol["lcr_credit"]["ceiling"] = float(point)
    elif setting == "c_uptake":
        pol["lcr_credit"]["uptake"] = float(point)
    elif setting == "c_hqla_released":
        pol["lcr_credit"]["release_share"] = float(point)
    elif setting == "c_stress_trigger":
        pol["lcr_credit"]["stress_trigger_fires"] = True
    elif setting == "collateral_margins_pp":
        m = fs["discount_window"]["margins"]
        for k in m:
            m[k] = min(cfg["margins_cap"], m[k] + float(point) / 100)
    elif setting == "depositor_coordination":
        c["behavior"]["coordination_strength"]["value"] *= float(point.lstrip("x"))
    elif setting == "routine_borrowing_strength_s":
        c["s"] = float(point)
    elif setting == "distress_hit_size":
        c["hit"] = float(point)
    elif setting == "b_full_run":
        pol["five_day_ratio"]["runoff_uninsured"] = 1.0
    elif setting == "svb_like_no_lcr":
        c["no_lcr_type"] = c["only_type"] = "svb_like"
    elif setting == "starting_collateral_split":
        side, sign = point.split("_")[0], 1 if "plus" in point else -1
        key = {"fed": "fed_prepositioned", "fhlb": "fhlb_pledged"}[side]
        place = fs["collateral_placement"]
        place[key] += sign * cfg["collateral_split_pp"]
        place["unpledged"] -= sign * cfg["collateral_split_pp"]
    elif setting == "fhlb_line_share":
        fs["fhlb"]["line_share_of_assets"] = float(point)
    elif setting == "repo_line_multiple":
        lines = fs["repo"]["same_day_line_share_of_assets"]
        for k in lines:
            lines[k] *= float(point.lstrip("x"))
    elif setting != "-":
        raise ValueError(f"no override defined for sensitivity {setting!r} (Clarification 31 B5)")
    # Unnamed switch combinations (feature attribution): added to copies of the policy table and the rates.
    for setup in extra_combinations(pol):
        name = switch_name(setup)
        pol["policies"][name] = {"switches": dict(zip(FEATURES, setup))}
        info["routine_borrowing"]["rate_by_policy"][name] = combination_rate(setup, info, pol["lcr_credit"]["uptake"])
    return c


# ---------- one batch ----------

_CACHE = {}


def _rows(runs, conf):
    """Every bank repeated `runs` times (row = bank x runs + run), optionally one bank type only."""
    key = ("rows", runs, conf["only_type"], conf["no_lcr_type"])
    if key not in _CACHE:
        banks = generate_banks()
        if conf["no_lcr_type"]:
            banks["lcr_calibration"] = np.where(banks["archetype"] == conf["no_lcr_type"], np.nan, banks["lcr_calibration"])
        rows = {k: (np.repeat(v, runs) if isinstance(v, np.ndarray) else v) for k, v in banks.items()}
        idx = np.arange(len(rows["bank_id"]))
        if conf["only_type"]:
            idx = idx[rows["archetype"] == conf["only_type"]]
            rows = {k: (v[idx] if isinstance(v, np.ndarray) else v) for k, v in rows.items()}
        _CACHE[key] = (rows, idx)
    return _CACHE[key]


def _draws(scenario, runs, cfg):
    """The scenario's draws over all 40 x runs rows (Clarification 31 B3), plus the policy table's opt-in draws."""
    key = ("draws", scenario, runs)
    if key not in _CACHE:
        n_banks = len(generate_banks()["bank_id"])
        seed = cfg["seeds"][scenario]
        steps = 2 * load_funding_settings()["time"]["days"]
        opt = draw_policy_randoms(load_policies()["seed"], n_banks)["opt_in_u"]
        _CACHE[key] = (draw_noise(seed, n_banks * runs, steps, load_yaml("agents.yaml")),
                       draw_info_randoms(seed, n_banks * runs), np.repeat(opt, runs))
    return _CACHE[key]


def run_batch(task, runs, cfg):
    """Run one batch; returns {field: array, one entry per row}. The engine is used exactly as in M1."""
    block, setting, point, scenario, policy, stigma, supervision = task
    key = ("conf", setting, point)
    if key not in _CACHE:
        _CACHE[key] = configure(setting, point, cfg)
    conf = _CACHE[key]
    rows, idx = _rows(runs, conf)
    noise, rnd, opt = _draws(scenario, runs, cfg)
    rnd = {k: v[idx] for k, v in rnd.items()}
    setup = policy_setup(rows, policy, conf["pol"], {"test_u": rnd["test_u"], "opt_in_u": opt[idx]},
                         conf["fs"], conf["lcr"], conf["info"])
    shock = yaml.safe_load(SCENARIOS.read_text())[scenario]
    st = start_episode(setup["banks"], shock, noise[idx], funding=conf["fs"], behavior=conf["behavior"],
                       info=conf["info"], stigma=stigma, supervision=supervision, strength_s=conf["s"],
                       distress_shock=conf["hit"], info_randoms=rnd, setup=setup)
    for _ in range(noise.shape[1]):          # stop once every row has ended: nothing after an end counts
        episode_step(st)
        if (st["end_state"] != RUNNING).all():
            break
    o = episode_outcomes(st)
    f4 = np.float32
    return {"failed": st["end_state"] == FAILED, "end_day": o["end_day"].astype(np.int16),
            "uncovered": o["peak_uncovered_bn"].astype(f4), "support": o["official_support_bn"].astype(f4),
            "fhlb": o["fhlb_peak_bn"].astype(f4), "hesitation": o["hesitation_steps"].astype(f4),
            "band": np.array([BANDS[b] for b in o["timing_band"]], np.int8),
            "grace": o["timing_only_upper_bound"].astype(bool),
            "eff_stigma": np.broadcast_to(o["effective_stigma"], idx.shape).astype(f4),
            "r": setup["routine_rate"].astype(f4), "lcr_reported": setup["lcr_reported"].astype(f4),
            "buffer_gap": setup["buffer_gap"].astype(f4), "row": idx.astype(np.int32)}


def _work(args):
    task, runs, cfg = args
    t0 = time.time()
    return task, run_batch(task, runs, cfg), time.time() - t0


# ---------- the run ----------

def group_name(task):
    block, setting, point, scenario = task[:4]
    return f"{block}__{setting}__{point}__{scenario}".replace("/", "_")


def run(runs=None, dry=False, out=RAW, workers=None, log=print):
    cfg, plan, pol_cfg = load_settings(), load_run_plan(), load_policies()
    runs = runs or plan["runs_per_cell"]
    todo = tasks(plan, pol_cfg)
    if dry:
        todo = todo[::round(1 / cfg["dry_run_share"])]
    workers = workers or cfg["workers"]
    t0, results, busy = time.time(), {}, 0.0
    log(f"{len(todo):,} batches x {runs} runs per bank ({'dry run' if dry else 'full run'}), {workers} workers")
    with Pool(workers) as pool:
        for i, (task, res, secs) in enumerate(pool.imap_unordered(_work, [(t, runs, cfg) for t in todo]), 1):
            results[task] = res
            busy += secs
            if i % max(1, len(todo) // 20) == 0 or i == len(todo):
                el = time.time() - t0
                log(f"  {i:,}/{len(todo):,} batches, {el / 60:.1f} min elapsed, ~{el / i * (len(todo) - i) / 60:.1f} min left")
    wall = time.time() - t0
    if dry:
        full = len(tasks(plan, pol_cfg))
        est = wall / len(todo) * full
        log(f"Dry run: {len(todo)} of {full:,} batches in {wall:.0f} s. Estimated full run: {est / 60:.0f} min "
            f"({est * load_run_plan()['timing']['margin'] / 60:.0f} min with the run plan's 1.5x margin; limit "
            f"{plan['timing']['limit_hours']} h).")
        return {"batches": len(todo), "seconds": wall, "estimate_minutes": est / 60}
    save(results, out)
    info = {"batches": len(todo), "runs_per_cell": runs, "episodes": int(sum(len(r["failed"]) for r in results.values())),
            "wall_seconds": round(wall, 1), "cpu_seconds": round(busy, 1), "workers": workers}
    (out / "run_info.json").write_text(json.dumps(info, indent=1) + "\n")
    log(f"Done: {info['episodes']:,} episodes in {wall / 60:.1f} min. Raw outcomes in {out}")
    return info


def save(results, out):
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.npz"):
        old.unlink()
    groups = {}
    for task, res in results.items():
        groups.setdefault(group_name(task), {}).update(
            {f"{task[4]}|{task[5]}|{task[6]}|{k}": v for k, v in res.items()})
    for name, arrays in sorted(groups.items()):
        np.savez_compressed(out / f"{name}.npz", **dict(sorted(arrays.items())))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--runs", type=int, default=None)
    ap.add_argument("--out", default=str(RAW))
    a = ap.parse_args()
    run(a.runs, a.dry, Path(a.out), log=lambda m: print(m, flush=True))


if __name__ == "__main__":
    main()
