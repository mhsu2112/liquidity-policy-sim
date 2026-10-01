"""Checks on the funding-timing records and rules (session M1.12; Clarification 18).

Mechanics only, policy A for every episode. The static exposure check builds setups and runs one
behavior-free waterfall step; no episode runs under any other policy. Nothing compares policies.
"""

import numpy as np
import pytest

import engine.episode as episode
from analysis.timing_exposure import capacity_by_tier
from analysis.timing_gap import alternative_rules
from engine.banks import generate_banks
from engine.episode import FAILED, RUNNING, draw_noise, episode_step, load_yaml, start_episode
from engine.frozen import frozen_fingerprint
from engine.funding import load_funding_settings
from engine.information import draw_info_randoms
from engine.outcomes import timing_band
from engine.write_costs import build_setups

AGENTS = load_yaml("agents.yaml")
BANKS = generate_banks()


def test_band_by_hand_exhaustive_and_exclusive():
    # Four failed runs, one per band, and one that did not fail.
    st = {"end_state": np.array([FAILED, FAILED, FAILED, FAILED, RUNNING]),
          "owed_at_failure_bn": np.array([3.0, 3.0, 3.0, 3.0, 0.0]),
          "on_way_at_failure_bn": np.array([5.0, 1.0, 0.0, 9.0, 0.0]),
          "equity_at_failure_bn": np.array([1.0, 1.0, 1.0, -0.5, np.nan])}
    assert list(timing_band(st)) == ["pure timing", "partly covered", "not covered", "equity below zero", ""]


def test_failure_records_match_the_failing_half_day():
    # SVB-like banks under a 0.5 shock, policy A: what is recorded at failure equals that half-day's record.
    one = {k: (np.repeat(v[:10], 5) if isinstance(v, np.ndarray) else v) for k, v in BANKS.items()}
    n = len(one["bank_id"])
    st = start_episode(one, 0.5, draw_noise(7, n, 12, AGENTS), info_randoms=draw_info_randoms(7, n))
    recs = [episode_step(st) for _ in range(12)]
    failed = np.flatnonzero(st["end_state"] == FAILED)
    assert failed.size
    for i in failed:
        t = st["end_step"][i]
        assert st["owed_at_failure_bn"][i] == recs[t]["unpaid_end"][i]
        assert st["on_way_at_failure_bn"][i] == recs[t]["on_way_next_day"][i]
        assert st["owed_at_failure_bn"][i] > st["fail_tol_bn"][i] or st["equity_at_failure_bn"][i] < 0


def test_alternative_rules_by_hand():
    # Tolerance 1. Row 0: owed 3 at half-day 0 with 5 coming, paid next half-day -> strict fails at 0,
    # grace never, two strikes never. Row 1: owed 3 twice running with nothing coming -> all fail
    # (strict 0, grace 0, two strikes 1).
    owed = np.array([[3.0, 0.0, 0.0], [3.0, 3.0, 0.0]])
    on_way = np.array([[5.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    equity = np.ones((2, 3))
    st = {"fail_tol_bn": np.array([1.0, 1.0]), "end_state": np.array([FAILED, FAILED])}
    fails, steps = alternative_rules(st, owed, on_way, equity)
    assert list(fails["strict"]) == [True, True]
    assert list(fails["grace"]) == [False, True] and list(fails["two_strikes"]) == [False, True]
    assert steps["strict"][1] == 0 and steps["grace"][1] == 0 and steps["two_strikes"][1] == 1


def test_exposure_is_static(monkeypatch):
    # Building the exposure table never runs an episode under any policy.
    def no_episode(*a, **k):
        raise AssertionError("an episode step ran")
    monkeypatch.setattr(episode, "episode_step", no_episode)
    _, setups = build_setups()
    fs = load_funding_settings()
    for name, s in setups.items():
        same, nxt, later = capacity_by_tier(s, fs)
        assert np.all(same > 0) and np.all(nxt >= 0) and np.all(later >= 0), name


def test_frozen_values_unchanged():
    assert frozen_fingerprint() == "05f9e763efc16772"


# ---------------------------------------------------------------- Amendment 6: grace-rule count

def test_by_next_morning_window():
    # From a morning the window is this afternoon and the next morning (= the next two half-days);
    # from an afternoon it is the next morning only (never more than the next two half-days).
    one = {k: (np.repeat(v[:10], 5) if isinstance(v, np.ndarray) else v) for k, v in BANKS.items()}
    n = len(one["bank_id"])
    st = start_episode(one, 0.5, draw_noise(7, n, 12, AGENTS), info_randoms=draw_info_randoms(7, n))
    recs = [episode_step(st) for _ in range(12)]
    for t, r in enumerate(recs):
        if t % 2 == 0:
            np.testing.assert_array_equal(r["on_way_by_next_morning"], r["on_way_next_day"])
        else:
            assert np.all(r["on_way_by_next_morning"] <= r["on_way_next_day"] + 1e-12)
    for i in np.flatnonzero(st["end_state"] == FAILED):
        assert st["by_next_morning_at_failure_bn"][i] == recs[st["end_step"][i]]["on_way_by_next_morning"][i]


def test_timing_only_flag_by_hand():
    from engine.outcomes import timing_only
    st = {"end_state": np.array([FAILED, FAILED, FAILED, FAILED, RUNNING]),
          "owed_at_failure_bn": np.array([3.0, 3.0, 3.0, 3.0, 3.0]),
          "by_next_morning_at_failure_bn": np.array([3.0, 2.9, 9.0, 9.0, 9.0]),
          "equity_at_failure_bn": np.array([0.0, 1.0, -0.1, 1.0, 1.0])}
    # covered with equity exactly 0: yes; not covered: no; negative equity: no; covered: yes; did not fail: no
    assert list(timing_only(st)) == [True, False, False, True, False]
