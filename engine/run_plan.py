"""Count every run M3 needs, from config/run_plan.yaml (session M1.9, Clarification 14).

Nothing is run here: this only counts. The counts, times the measured cost per
episode from `make benchmark`, give the projected run time.
"""

from itertools import product
from pathlib import Path

import yaml

from engine.banks import load_settings

RUN_PLAN_PATH = Path(__file__).resolve().parent.parent / "config" / "run_plan.yaml"


def load_run_plan(path=RUN_PLAN_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


def cell_count(plan, grid):
    g = plan["cells"][grid]
    return len(g["stigma"]) * len(g["supervision"])


def bank_count(which="all"):
    s = load_settings()
    per = s["banks_per_archetype"]
    return per * len(s["archetypes"]) if which == "all" else per   # one archetype


def effective_setup(sw):
    """What a switch combination actually builds: the five-day ratio always prepositions
    (engine/policies.py), so 'ratio on, mandate off' builds the same setup as both on."""
    return (sw["prepositioning_mandate"] or sw["five_day_ratio"], sw["testing_mandate"], sw["five_day_ratio"],
            sw["lcr_credit"])


def extra_switch_combinations(pol_cfg):
    """Distinct switch combinations not already run as a named policy."""
    names = ("prepositioning_mandate", "testing_mandate", "five_day_ratio", "lcr_credit")
    every = {effective_setup(dict(zip(names, bits))) for bits in product([False, True], repeat=4)}
    named = {effective_setup(p["switches"]) for p in pol_cfg["policies"].values()}
    return sorted(every - named)


def count_runs(plan, pol_cfg):
    """One row per block of runs: (block, setting, points, policies, scenarios, banks, cells, runs)."""
    runs, n_pol = plan["runs_per_cell"], len(plan["policies"])
    n_sc, banks = len(plan["scenarios"]), bank_count()
    rows = [("main grid", "-", 1, n_pol, n_sc, banks, cell_count(plan, "main"),
             n_pol * n_sc * banks * cell_count(plan, "main") * runs)]
    for s in plan["sensitivities"]:
        pol = n_pol if s["policies"] == "all" else len(s["policies"])
        sc = len(s.get("scenarios", plan["scenarios"]))
        b = bank_count(s.get("banks", "all"))
        cells = cell_count(plan, s["cells"])
        rows.append(("sensitivity", s["name"], len(s["points"]), pol, sc, b, cells,
                     len(s["points"]) * pol * sc * b * cells * runs))
    extra = len(extra_switch_combinations(pol_cfg))
    cells = cell_count(plan, plan["feature_switches"]["cells"])
    rows.append(("feature switches", f"{extra} extra combinations", 1, extra, n_sc, banks, cells,
                 extra * n_sc * banks * cells * runs))
    return rows


def totals(rows):
    out = {}
    for block, *_, n in rows:
        out[block] = out.get(block, 0) + n
    out["total"] = sum(r[-1] for r in rows)
    return out
