"""Information routes: who learns what, through which route, and when (session M1.5).

Rules from docs/contract.md sections 3 and 3a and docs/amendments.md Clarification 9.
Observers are the market (depositors and wholesale lenders, who read the same
public news), the two market groups separately for inference, and the supervisor.
An observer's knowledge changes ONLY in `deliver`, and `deliver` acts only on
events a route has scheduled. There is no other path.

Routes that reveal discount window borrowing (each fires at most once per episode,
for the bank's first draw; later routes add nothing the observer does not know):
    supervisory       the supervisor, the same half-day (Fed lends; daily FR 2052a)
    leak              the market, named, `lag` days after the first draw, with a
                      chance drawn up front
    announcement      the market, named, 4 business days after total borrowing
                      reaches 5% of starting total assets (mandatory 8-K)
    weekly_aggregate  the market, unnamed: the Friday morning after the Thursday
                      report that first covers the draw; only partly revealing

Routes that reveal other things (recorded, no confidence effect in M1.5):
    inference         securities sold or funding refused: lenders the same
                      half-day, depositors the next
    ratio_disclosure  the quarterly LCR (prior quarter, so start-of-episode
                      values) for banks with an LCR requirement

How a known draw moves confidence (Clarification 9, item 2): a route that reveals
the draw is read as distress if U < effective stigma x how revealing the route is,
with U one random number per run drawn up front. The first distress reading adds a
news shock of fixed size, which fades and is amplified like the opening news
(agents/depositors.py). Nothing here takes a policy name: a policy can act only
through the routine borrowing rate r.

Everything is an array with one entry per row (one bank in one run).
"""

from pathlib import Path

import numpy as np
import yaml

from agents.supervisor import effective_supervisory_cost, level_cost, routine_discount
from engine.lcr import compute_lcr

INFO_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "information.yaml"
NEVER = np.iinfo(np.int64).max // 4      # a step number meaning "not scheduled"
BORROWING_ROUTES = ("supervisory", "leak", "announcement", "weekly_aggregate")
MARKET_ROUTES = ("leak", "announcement", "weekly_aggregate")
INFERENCE_KINDS = ("sale", "refusal")
INFERENCE_OBSERVERS = ("lenders", "depositors")


def load_information_settings(path=INFO_SETTINGS_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------- static rules (no episode needed)

def effective_stigma(sigma, s, r):
    """Contract 3a: effective stigma = market stigma x e^(-s x r)."""
    return np.asarray(sigma, float) * routine_discount(s, r)


def weekly_revealing(r, cfg):
    """How strongly the weekly aggregate points at this bank: 1 / (1 + other borrowers that week).

    Other borrowers that week = r x banks in the system / weeks in a quarter.
    Observers spread suspicion evenly across everyone who borrowed.
    """
    w = cfg["routes"]["weekly_aggregate"]
    others = np.asarray(r, float) * w["banks_in_system"] / w["weeks_per_quarter"]
    return 1.0 / (1.0 + others)


def read_as_distress(stigma_eff, revealing, read_u):
    """Clarification 9, item 2: the same function for every policy."""
    return np.asarray(read_u) < np.asarray(stigma_eff) * np.asarray(revealing)


def draw_info_randoms(seed, rows):
    """The random numbers per run used by the routes and the window, drawn up front.

    leak_u and read_u (M1.5) come from a separate stream from the news noise (a
    child of the same seed), so adding them left every M1.4 result unchanged.
    test_u (M1.6: was the bank's collateral tested in the last 90 days?) comes
    from a second child stream, so it leaves leak_u and read_u unchanged.
    All are shared by every policy.
    """
    children = np.random.SeedSequence(seed).spawn(2)   # child 0 is the M1.5 stream, unchanged
    rng = np.random.default_rng(children[0])
    out = {"leak_u": rng.random(rows), "read_u": rng.random(rows)}
    out["test_u"] = np.random.default_rng(children[1]).random(rows)
    return out


def no_information_randoms(rows):
    """Random numbers meaning "nothing leaks, nothing is read as distress, collateral untested".

    For checks of depositor and lender mechanics that model no information
    (the M1.4 tests). Supplied explicitly, never as a silent default.
    """
    return {"leak_u": np.ones(rows), "read_u": np.ones(rows), "test_u": np.ones(rows)}


def tested_recently(test_u, r):
    """Clarification 10: collateral tested in the last 90 days if U_test < 1 - e^(-r).

    r is routine draws per bank per quarter (contract 3a); treating draws as random
    over time, the chance of at least one in the last quarter is 1 - e^(-r).
    The same U_test is used under every policy, so a bank tested at a low r is
    also tested at any higher r.
    """
    return np.asarray(test_u) < 1 - np.exp(-np.asarray(r, float))


def weekly_act_step(d, cfg, spd):
    """Step at which the market acts on the first weekly report covering a draw made at step d."""
    w = cfg["routes"]["weekly_aggregate"]
    first, every, off = w["first_release_day"], w["every_days"], w["covers_through_day_offset"]
    # Report on day D covers steps up to spd x (D + off) - 1; find the first D >= that.
    k = np.maximum(np.ceil(((d + 1) / spd - off - first) / every), 0).astype(np.int64)
    release_day = first + every * k
    return spd * release_day - 1 + w["acts_on_offset_steps"]   # after the close on the release day


# ---------------------------------------------------------------- set-up

def start_information(st, cfg, stigma, s, r, supervision, randoms, routes_off, steps):
    """Add the information state to an episode. `routes_off` switches routes off (tests only)."""
    n = len(st["bank_id"])
    arr = lambda x: np.broadcast_to(np.asarray(x, float), (n,)).copy()
    rt = cfg["routes"]
    spd = st["settings"]["time"]["steps_per_day"]
    st["info_cfg"], st["routes_off"] = cfg, set(routes_off)
    st["routine_rate"] = arr(r)
    st["strength_s"] = arr(s)
    st["market_stigma"] = arr(stigma)
    st["stigma_eff"] = effective_stigma(st["market_stigma"], st["strength_s"], st["routine_rate"])
    st["weekly_revealing"] = weekly_revealing(st["routine_rate"], cfg)
    st["sup_cost"] = level_cost(np.broadcast_to(np.asarray(supervision, object), (n,)), cfg["supervisor"])
    st["sup_cost_eff"] = effective_supervisory_cost(st["sup_cost"], st["strength_s"], st["routine_rate"])
    st["distress_shock"] = cfg["market_stigma"]["distress_news_shock"]

    # engine/episode.py refuses to start a non-demo run without these (M1.6).
    randoms = randoms or no_information_randoms(n)
    st["leak_u"], st["read_u"] = randoms["leak_u"].copy(), randoms["read_u"].copy()

    st["assets_start_bn"] = st["total_assets_bn"].copy()
    st["dw_drawn_total_bn"] = np.zeros(n)
    st["first_draw_step"] = np.full(n, NEVER)
    st["material_step"] = np.full(n, NEVER)
    st["due"] = {k: np.full(n, NEVER) for k in BORROWING_ROUTES}
    st["delivered"] = {k: np.zeros(n, bool) for k in BORROWING_ROUTES}

    # What each observer knows. market_knows: 0 = nothing, 1 = named borrowing;
    # in between = only the weekly aggregate, as revealing as it is.
    st["supervisor_knows"] = np.zeros(n, bool)
    st["market_knows"] = np.zeros(n)
    st["distress_from"] = np.full(n, NEVER)          # step from which the distress reading moves confidence
    st["sees_distress_signs"] = {o: np.zeros(n, bool) for o in INFERENCE_OBSERVERS}
    inf = rt["inference"]
    width = steps + max(inf["lenders_lag_steps"], inf["depositors_lag_steps"]) + 1
    st["inference_due"] = {(o, k): np.zeros((n, width)) for o in INFERENCE_OBSERVERS for k in INFERENCE_KINDS}

    st["disclosure_step"] = spd * (rt["ratio_disclosure"]["day"] - 1)
    # The disclosed LCR includes Option C's credit, if any (Clarification 12 item 7).
    lcr = compute_lcr(st)
    st["lcr_start"] = (lcr["hqla_bn"] + st.get("credit_left_bn", 0.0)) / lcr["calibrated_outflows_bn"]
    st["lcr_disclosing"] = lcr["lcr_status"] == "required"
    st["ratio_disclosed"] = np.zeros(n, bool)
    st["events"] = []


# ---------------------------------------------------------------- each half-day

def _event(st, t, route, observer, mask, **values):
    if mask.any():
        st["events"].append({"t": t, "route": route, "observer": observer, "mask": mask.copy(),
                             **{k: np.broadcast_to(v, mask.shape).copy() for k, v in values.items()}})


def observe(st, t, drawn_bn, sold_bn, refused_bn):
    """After the half-day's funding: schedule the events that what happened will cause."""
    cfg, off, n = st["info_cfg"], st["routes_off"], len(st["bank_id"])
    rt, spd = cfg["routes"], st["settings"]["time"]["steps_per_day"]

    first = (st["first_draw_step"] == NEVER) & (drawn_bn > 0)
    st["first_draw_step"] = np.where(first, t, st["first_draw_step"])
    st["dw_drawn_total_bn"] += drawn_bn
    material = ((st["material_step"] == NEVER)
                & (st["dw_drawn_total_bn"] >= rt["announcement"]["materiality_share_of_assets"]
                   * st["assets_start_bn"]))
    st["material_step"] = np.where(material, t, st["material_step"])

    leaks = first & (st["leak_u"] < rt["leak"]["probability"])
    when = {"supervisory": (first, t + rt["supervisory"]["lag_steps"]),
            "leak": (leaks, t + spd * rt["leak"]["lag_days"]),
            "weekly_aggregate": (first, weekly_act_step(np.full(n, t), cfg, spd)),
            "announcement": (material, t + spd * rt["announcement"]["filing_lag_days"])}
    for route, (mask, step) in when.items():
        if route not in off:
            st["due"][route] = np.where(mask, step, st["due"][route])

    if "inference" not in off:
        for o in INFERENCE_OBSERVERS:
            lag = rt["inference"][f"{o}_lag_steps"]
            st["inference_due"][(o, "sale")][:, t + lag] += sold_bn
            st["inference_due"][(o, "refusal")][:, t + lag] += refused_bn


def deliver(st, t, phase):
    """Hand observers every event due now. The only place knowledge changes.

    Called at the start of each half-day (before confidence is judged) and again
    at its end, for same-half-day routes scheduled by `observe`. News delivered
    at the end of a half-day moves confidence from the next one.
    """
    effective = t if phase == "start" else t + 1
    for route in BORROWING_ROUTES:
        rows = (st["due"][route] == t) & ~st["delivered"][route]
        if not rows.any():
            continue
        st["delivered"][route] |= rows
        if route == "supervisory":
            st["supervisor_knows"] |= rows
            _event(st, t, route, "supervisor", rows, amount=st["dw_drawn_total_bn"])
            continue
        revealing = st["weekly_revealing"] if route == "weekly_aggregate" else np.ones(len(rows))
        chance = st["stigma_eff"] * revealing
        read = rows & read_as_distress(st["stigma_eff"], revealing, st["read_u"])
        new = read & (st["distress_from"] == NEVER)
        st["distress_from"] = np.where(new, effective, st["distress_from"])
        st["market_knows"] = np.where(rows, np.maximum(st["market_knows"], revealing), st["market_knows"])
        _event(st, t, route, "market", rows, amount=st["dw_drawn_total_bn"], revealing=revealing,
               chance=chance, read=read, new_distress=new)

    for (o, kind), due in st["inference_due"].items():
        amount = due[:, t].copy()
        due[:, t] = 0.0
        rows = amount > 0
        st["sees_distress_signs"][o] |= rows
        _event(st, t, f"inference_{kind}", o, rows, amount=amount)

    if (phase == "start" and t == st["disclosure_step"] and "ratio_disclosure" not in st["routes_off"]):
        rows = st["lcr_disclosing"].copy()
        st["ratio_disclosed"] |= rows
        _event(st, t, "ratio_disclosure", "market", rows, lcr=st["lcr_start"])


def distress_news(st, t, half_life_steps):
    """The extra news from a distress reading at step t: h x 0.5^(steps since / half-life), else 0."""
    since = t - st["distress_from"]
    return np.where(since >= 0, st["distress_shock"] * 0.5 ** (np.maximum(since, 0) / half_life_steps), 0.0)
