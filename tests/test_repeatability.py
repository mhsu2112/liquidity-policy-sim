"""Checks on repeatability, batch independence, paired random numbers and the run plan (session M1.9).

Episodes run under policy A only (project Rule 2). The paired-numbers check builds
every policy's setup (static) and runs no episode under any other policy.
Nothing here compares policies.
"""

import inspect

import numpy as np
import pytest

import engine.write_costs as write_costs
from engine.banks import generate_banks
from engine.benchmark import fingerprint
from engine.episode import draw_noise, load_yaml, run_episode
from engine.information import draw_info_randoms
from engine.lcr_credit import draw_opt_in_u
from engine.outcomes import episode_outcomes
from engine.policies import draw_policy_randoms, load_policies
from engine.run_plan import count_runs, extra_switch_combinations, load_run_plan, totals

AGENTS = load_yaml("agents.yaml")
BANKS = generate_banks()
STEPS = 60
SEED = 20261003
M = 10   # 40 banks x 10 = 400 rows
ROWS = {k: (np.tile(v, M) if isinstance(v, np.ndarray) else v) for k, v in BANKS.items()}
N = len(ROWS["bank_id"])
STIGMA = np.resize([0.0, 0.10, 0.20, 0.35, 0.50, 0.70, 0.90], N)
SUPERVISION = np.resize(np.array(["strongly_penalizes", "penalizes", "neutral", "encourages",
                                  "strongly_encourages"], dtype=object), N)
SHOCK = np.resize([0.05, 0.15, 0.40], N)   # mechanics only: three shock sizes, policy A


def batch(seed=SEED, rows=ROWS, idx=None):
    """Run a policy-A batch; `idx` picks rows (with their own random numbers) to run on their own."""
    noise, rnd = draw_noise(seed, N, STEPS, AGENTS), draw_info_randoms(seed, N)
    if idx is not None:
        rows = {k: (v[idx] if isinstance(v, np.ndarray) else v) for k, v in rows.items()}
        noise, rnd = noise[idx], {k: v[idx] for k, v in rnd.items()}
        return run_episode(rows, SHOCK[idx], noise, info_randoms=rnd, stigma=STIGMA[idx],
                           supervision=SUPERVISION[idx])
    return run_episode(rows, SHOCK, noise, info_randoms=rnd, stigma=STIGMA, supervision=SUPERVISION)


def test_same_seed_identical_results():
    st1, recs1 = batch()
    st2, recs2 = batch()
    assert fingerprint([st1, recs1]).hexdigest() == fingerprint([st2, recs2]).hexdigest()
    o1, o2 = episode_outcomes(st1), episode_outcomes(st2)
    for k in o1:
        np.testing.assert_array_equal(o1[k], o2[k])


def test_different_seed_different_results():
    o1, o2 = episode_outcomes(batch()[0]), episode_outcomes(batch(seed=SEED + 1)[0])
    assert not np.array_equal(o1["peak_owed_bn"], o2["peak_owed_bn"])


@pytest.mark.parametrize("i", [0, 137, 399])
def test_one_run_alone_matches_the_same_run_in_a_batch(i):
    st, recs = batch()
    alone_st, alone_recs = batch(idx=[i])
    assert len(alone_recs) == len(recs)
    for r_batch, r_alone in zip(recs, alone_recs):
        for k, v in r_batch.items():
            if isinstance(v, np.ndarray) and v.shape[:1] == (N,):
                np.testing.assert_array_equal(v[[i]], r_alone[k], err_msg=f"half-day {r_batch['t']}: {k}")
    o, oa = episode_outcomes(st), episode_outcomes(alone_st)
    for k in o:
        np.testing.assert_array_equal(o[k][[i]], oa[k], err_msg=k)


def test_every_policy_setup_receives_the_same_random_numbers(monkeypatch):
    # Record the random numbers each policy's setup is given; build setups only (no episode).
    seen = {}
    real = write_costs.policy_setup

    def recording(banks, name, cfg, randoms, *args):
        seen[name] = {k: v.copy() for k, v in randoms.items()}
        return real(banks, name, cfg, randoms, *args)

    monkeypatch.setattr(write_costs, "policy_setup", recording)
    write_costs.build_setups()
    names = list(seen)
    assert set(names) == set(load_policies()["policies"])
    for name in names[1:]:
        for k in seen[names[0]]:
            np.testing.assert_array_equal(seen[name][k], seen[names[0]][k], err_msg=f"{name}: {k}")


def test_random_numbers_depend_on_seed_and_rows_only():
    # No function that draws random numbers can see a policy: only a seed and a row count.
    for fn in (draw_noise, draw_info_randoms, draw_policy_randoms, draw_opt_in_u):
        params = set(inspect.signature(fn).parameters)
        assert not params & {"policy", "name", "policy_name", "setup"}, fn.__name__
    a, b = draw_policy_randoms(SEED, 40), draw_policy_randoms(SEED, 40)
    for k in a:
        np.testing.assert_array_equal(a[k], b[k])


def test_run_plan_counts_by_hand():
    plan, pol = load_run_plan(), load_policies()
    t = totals(count_runs(plan, pol))
    assert t["main grid"] == 6 * 2 * 40 * 35 * 200 == 3_360_000
    per_point = 2 * 40 * 9 * 200   # scenarios x banks x mid-range cells x runs
    by_hand = (8 * 2 * 6 * per_point            # eight settings, 2 points, all six policies
               + 2 * 2 * per_point              # C ceiling
               + 2 * 2 * 2 * 40 * 35 * 200      # C uptake, all 35 cells
               + 2 * 2 * per_point              # C HQLA released
               + 1 * 2 * 1 * 40 * 9 * 200       # stress trigger, S1 only
               + 1 * 3 * per_point              # B full run: B, B', E
               + 1 * 2 * 2 * 10 * 9 * 200       # SVB-like with no LCR: 10 banks
               + 4 * 6 * per_point)             # starting collateral split, four points
    assert t["sensitivity"] == by_hand == 21_320_000
    assert len(extra_switch_combinations(pol)) == 8   # 12 distinct setups less A, B, C, E
    assert t["feature switches"] == 8 * per_point == 1_152_000
    assert t["total"] == 25_832_000
