"""The funding waterfall (session M1.3).

When a bank must pay out cash in a half-day step, it looks for that cash in a
fixed order. Sources are grouped by how fast their cash arrives (Clarification 5,
"bridging"): everything that pays today is used first, then next-day sources,
and so on. Within each speed tier the order is reserves, securities (repo or
sale), Home Loan Bank, discount window.

    Tier   Cash arrives          Sources, in order
    1      same half-day         reserves above floor; repo of Level 1, then
                                 Level 2A, within the bank's same-day repo line
                                 (Clarifications 6-7); Home Loan Bank line;
                                 window on prepositioned loans, if tested
    2      next day              repo beyond the line (Clarification 7);
                                 sell Level 1; Home Loan Bank above the line;
                                 window on untested prepositioned loans,
                                 then on Level 1 and Level 2A securities
    3      two days              sell Level 2A
    4      day 11                window on eligible loans pledged nowhere

There is no borrowing decision and no stigma here (both come in M1.6): the
bank always moves on to the next source when one is used up.

Everything is vectorized: each quantity is an array with one entry per bank,
and one call to `step` moves all banks forward together.
"""

from pathlib import Path

import numpy as np
import yaml

from engine.balance_sheet import ONE_DOLLAR_BN, total_assets

FUNDING_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "funding.yaml"
LOAN_TYPES = ("resi", "cre", "ci")
SECURITY_CLASSES = ("level1", "level2a")

# The sources in waterfall order: (name, plain-English label). The lag of each
# comes from config/funding.yaml (see _lags). Sorting by lag, keeping this order
# within a lag, gives the speed tiers above.
SOURCES = [
    ("reserves", "reserves above the floor"),
    ("repo_level1", "repo of Level 1 securities"),
    ("repo_level2a", "repo of Level 2A securities"),
    ("repo_next_level1", "next-day repo of Level 1 securities"),
    ("repo_next_level2a", "next-day repo of Level 2A securities"),
    ("sale_level1", "Level 1 securities sale"),
    ("fhlb_line", "Home Loan Bank line"),
    ("fhlb_above_line", "Home Loan Bank above the line"),
    ("dw_tested", "discount window, tested prepositioned loans"),
    ("dw_untested", "discount window, untested prepositioned loans"),
    ("dw_level1", "discount window, Level 1 securities"),
    ("dw_level2a", "discount window, Level 2A securities"),
    ("sale_level2a", "Level 2A securities sale"),
    ("dw_unpledged", "discount window, loans not prepositioned"),
]
LABELS = dict(SOURCES)
BORROWING_LINE = {"repo_level1": "repo_bn", "repo_level2a": "repo_bn",
                  "repo_next_level1": "repo_bn", "repo_next_level2a": "repo_bn",
                  "fhlb_line": "fhlb_advances_bn", "fhlb_above_line": "fhlb_advances_bn",
                  "dw_tested": "dw_loans_bn", "dw_untested": "dw_loans_bn", "dw_level1": "dw_loans_bn",
                  "dw_level2a": "dw_loans_bn", "dw_unpledged": "dw_loans_bn"}


BEHAVIOR_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "behavior.yaml"


def load_funding_settings(path=FUNDING_SETTINGS_PATH, behavior_path=BEHAVIOR_SETTINGS_PATH):
    """Funding settings, plus the fire-sale price impact, which lives in
    config/behavior.yaml because it is one of the five settings tuned in M1.10."""
    with open(path) as f:
        s = yaml.safe_load(f)
    with open(behavior_path) as f:
        impact = yaml.safe_load(f)["fire_sale_price_impact_per_bn"]
    s["securities"]["price_impact_per_bn"] = {c: impact[c]["value"] for c in SECURITY_CLASSES}
    return s


def _lags(s):
    sec, fhlb, dw = s["securities"]["settlement_lag_steps"], s["fhlb"], s["discount_window"]["lag_steps"]
    repo, repo_next = s["repo"]["lag_steps"], s["repo"]["beyond_line_lag_steps"]
    return {"reserves": 0, "repo_level1": repo, "repo_level2a": repo,
            "repo_next_level1": repo_next, "repo_next_level2a": repo_next,
            "fhlb_line": 0, "dw_tested": dw["prepositioned_tested"],
            "sale_level1": sec["level1"], "fhlb_above_line": fhlb["above_line_lag_steps"],
            "dw_untested": dw["prepositioned_untested"], "dw_level1": dw["securities"],
            "dw_level2a": dw["securities"], "sale_level2a": sec["level2a"],
            "dw_unpledged": dw["unprepositioned_loans"]}


def waterfall_order(s):
    """Sources sorted into speed tiers; the brief's order is kept within a tier."""
    lags = _lags(s)
    return sorted((name for name, _ in SOURCES), key=lambda name: lags[name])  # sort is stable


def start_state(banks, s=None, tested=None):
    """Set up each bank before the first step.

    `tested` (one True/False per bank) says whether the bank's prepositioned
    collateral was tested in the last 90 days. Clarification 4: it starts untested.
    """
    s = s or load_funding_settings()
    n = len(banks["bank_id"])
    st = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in banks.items()}
    st["settings"] = s
    st["lags"] = _lags(s)
    st["order"] = waterfall_order(s)
    st["tested"] = np.zeros(n, bool) if tested is None else np.asarray(tested, bool)

    # New balance-sheet lines, all zero to start.
    for line in ("repo_bn", "fhlb_advances_bn", "dw_loans_bn", "sale_proceeds_due_bn", "unpaid_outflows_bn"):
        st[line] = np.zeros(n)

    # The reserve floor is fixed in dollars at the start, so it doesn't shrink as the bank does.
    st["reserve_floor_bn"] = s["reserves"]["floor_share_of_assets"] * banks["total_assets_bn"]

    # Unrealized loss rate on securities, the same for Level 1 and Level 2A (Clarification 3).
    st["loss_rate"] = banks["unrealized_loss_bn"] / banks["securities_bn"]
    for c in SECURITY_CLASSES:
        st[f"sold_mv_{c}_bn"] = np.zeros(n)     # market value sold so far (drives price impact)
        st[f"dw_pledged_mv_{c}_bn"] = np.zeros(n)  # market value pledged at the window
        st[f"repo_pledged_mv_{c}_bn"] = np.zeros(n)  # market value encumbered by repo (Clarification 6)
        st[f"repo_out_{c}_bn"] = np.zeros(n)  # repo outstanding against class c (memo; total is repo_bn)

    # Same-day repo line by bank type (Clarification 7), and the share of repo
    # lenders still willing to lend (1 until lenders start refusing; M1.4).
    line_share = np.array([s["repo"]["same_day_line_share_of_assets"][a] for a in banks["archetype"]])
    st["repo_line_left_bn"] = line_share * banks["total_assets_bn"]
    st["repo_access"] = np.ones(n)

    # Collateral pools (Clarification 4): eligible loans split between the Fed,
    # the Home Loan Bank and nowhere, each pool holding the bank's own loan mix.
    place, margins = s["collateral_placement"], s["discount_window"]["margins"]
    eligible = banks["eligible_loans_bn"]
    loans = banks["loans_bn"]
    lendable_per_eligible = sum(margins[t] * banks[f"{t}_loans_bn"] / loans for t in LOAN_TYPES)
    st["dw_prepositioned_left_bn"] = place["fed_prepositioned"] * eligible * lendable_per_eligible
    st["dw_unpledged_left_bn"] = place["unpledged"] * eligible * lendable_per_eligible
    st["fhlb_pledged_loans_bn"] = place["fhlb_pledged"] * eligible
    st["fhlb_total_left_bn"] = s["fhlb"]["advance_rate"] * st["fhlb_pledged_loans_bn"]
    st["fhlb_line_left_bn"] = np.minimum(s["fhlb"]["line_share_of_assets"] * banks["total_assets_bn"],
                                         st["fhlb_total_left_bn"])

    # Cash on its way: one row per bank, one column per future half-day, per source.
    steps = s["time"]["steps_per_day"] * s["time"]["days"]
    width = steps + max(st["lags"].values()) + 1
    st["incoming"] = {name: np.zeros((n, width)) for name, _ in SOURCES}
    st["t"] = 0
    return st


# ---------------------------------------------------------------- securities

def _saleable_mv(st, c):
    """Market value of securities in class c not yet sold, repo'd or pledged at the window."""
    return (st[f"{c}_securities_bn"] * (1 - st["loss_rate"])
            - st[f"dw_pledged_mv_{c}_bn"] - st[f"repo_pledged_mv_{c}_bn"])


def _impact(st, c):
    return st["settings"]["securities"]["price_impact_per_bn"][c]


def _sale_capacity(st, c):
    """Most cash a sale of class c can raise now, after the price discount.

    Selling x (market value) when S has already been sold raises
    (1 - lam*S)*x - lam*x^2/2. Selling stops if the next dollar would fetch nothing.
    """
    lam, sold = _impact(st, c), st[f"sold_mv_{c}_bn"]
    x = _saleable_mv(st, c)
    if lam > 0:
        x = np.minimum(x, np.maximum((1 - lam * sold) / lam, 0))
    return np.maximum((1 - lam * sold) * x - lam * x**2 / 2, 0)


def _sell(st, c, cash, t, lag):
    """Sell enough of class c to raise `cash`; book the loss; schedule the proceeds."""
    lam, sold = _impact(st, c), st[f"sold_mv_{c}_bn"]
    b = 1 - lam * sold
    # Market value to sell: the smaller root of lam/2*x^2 - b*x + cash = 0,
    # written so it also works when lam = 0 (then x = cash).
    x = 2 * cash / (b + np.sqrt(np.maximum(b**2 - 2 * lam * cash, 0)))
    x = np.where(cash > 0, x, 0.0)
    book_sold = x / (1 - st["loss_rate"])
    realized_unrealized = book_sold - x   # the loss already on the books, now realized
    discount = x - cash                   # the fire-sale price discount
    st[f"{c}_securities_bn"] -= book_sold
    st["securities_bn"] -= book_sold
    st["unrealized_loss_bn"] -= realized_unrealized
    st["equity_bn"] -= realized_unrealized + discount
    st[f"sold_mv_{c}_bn"] += x
    st["sale_proceeds_due_bn"] += cash
    st["incoming"][f"sale_{c}"][:, t + lag] += cash
    return realized_unrealized + discount


# ---------------------------------------------------------------- capacity and use

def _capacity(st, name):
    m = st["settings"]["discount_window"]["margins"]
    if name == "reserves":
        return np.maximum(st["reserves_bn"] - st["reserve_floor_bn"], 0)
    if name.startswith("sale_"):
        return _sale_capacity(st, name[5:])
    if name.startswith("repo_"):
        # Repo raises market value x (1 - haircut), only from lenders still willing;
        # same-day repo is also limited to what is left of the line (Clarification 7).
        c = name.rsplit("_", 1)[1]
        cap = np.maximum(_saleable_mv(st, c), 0) * (1 - st["settings"]["repo"]["haircuts"][c])
        if not name.startswith("repo_next_"):
            cap = np.minimum(cap, st["repo_line_left_bn"])
        return st["repo_access"] * cap
    if name == "fhlb_line":
        return np.minimum(st["fhlb_line_left_bn"], st["fhlb_total_left_bn"])
    if name == "fhlb_above_line":
        return st["fhlb_total_left_bn"] - np.minimum(st["fhlb_line_left_bn"], st["fhlb_total_left_bn"])
    if name == "dw_tested":
        return np.where(st["tested"], st["dw_prepositioned_left_bn"], 0.0)
    if name == "dw_untested":
        return np.where(st["tested"], 0.0, st["dw_prepositioned_left_bn"])
    if name in ("dw_level1", "dw_level2a"):
        c = name[3:]
        return np.maximum(_saleable_mv(st, c), 0) * m[c]
    if name == "dw_unpledged":
        return st["dw_unpledged_left_bn"]
    raise KeyError(name)


def _use(st, name, cash, t):
    """Take `cash` from a source: reduce what is left of it and move the money.

    Same half-day cash pays the outflow at once; slower cash is scheduled to arrive later.
    Returns the realized loss (non-zero for sales only).
    """
    lag = st["lags"][name]
    if name.startswith("sale_"):
        return _sell(st, name[5:], cash, t, lag)

    _reduce_source(st, name, cash)
    if lag == 0:
        if name != "reserves":  # borrowed today: the loan and the cash arrive together
            st[BORROWING_LINE[name]] += cash
            if name.startswith("repo_"):
                st[f"repo_out_{name.rsplit('_', 1)[1]}_bn"] += cash
        st["unpaid_outflows_bn"] -= cash
    else:
        st["incoming"][name][:, t + lag] += cash
    return np.zeros_like(cash)


def _reduce_source(st, name, cash):
    """Reduce what is left of a non-sale source after `cash` is taken from it."""
    if name == "reserves":
        st["reserves_bn"] -= cash
    elif name.startswith("repo_"):
        # Repo: the securities stay on the books, encumbered, so no loss is realized.
        # A 100% haircut means repo raises nothing, so nothing is encumbered.
        c = name.rsplit("_", 1)[1]
        keep = 1 - st["settings"]["repo"]["haircuts"][c]
        st[f"repo_pledged_mv_{c}_bn"] += cash / keep if keep > 0 else 0.0
        if not name.startswith("repo_next_"):
            st["repo_line_left_bn"] -= cash  # repaid repo does not restore the line
    elif name in ("fhlb_line", "fhlb_above_line"):
        st["fhlb_total_left_bn"] -= cash
        if name == "fhlb_line":
            st["fhlb_line_left_bn"] -= cash
    elif name in ("dw_tested", "dw_untested"):
        st["dw_prepositioned_left_bn"] -= cash
    elif name in ("dw_level1", "dw_level2a"):
        c = name[3:]
        st[f"dw_pledged_mv_{c}_bn"] += cash / st["settings"]["discount_window"]["margins"][c]
    elif name == "dw_unpledged":
        st["dw_unpledged_left_bn"] -= cash


# Window sources a forced draw may use, fastest first. Loans not prepositioned
# are left out: they take more than 10 days (contract section 7).
FORCED_DW_SOURCES = ("dw_tested", "dw_untested", "dw_level1", "dw_level2a")


def force_dw_draw(st, amount_bn):
    """Borrow `amount_bn` from the discount window now, whatever the bank needs.

    A stand-in used only by `make demo-info` and tests (session M1.5): the bank's
    real borrow-or-not decision comes in M1.6. The draw uses the window's fastest
    collateral first. Cash arriving today goes to reserves with the loan booked at
    once; slower cash is scheduled and booked on arrival, like any other source.
    Returns the amount taken from each source.
    """
    t = st["t"]
    want = np.broadcast_to(np.asarray(amount_bn, float), (len(st["bank_id"]),)).copy()
    taken = {}
    for name in FORCED_DW_SOURCES:
        cash = np.minimum(want, _capacity(st, name))
        _reduce_source(st, name, cash)
        if st["lags"][name] == 0:
            st["dw_loans_bn"] += cash
            st["reserves_bn"] += cash
        else:
            st["incoming"][name][:, t + st["lags"][name]] += cash
        taken[name] = cash
        want = want - cash
    return taken


# ---------------------------------------------------------------- one half-day

def step(st, outflows):
    """Move every bank forward one half-day.

    `outflows` maps a funding line (e.g. "uninsured_deposits_bn") to the amount
    leaving each bank this half-day. Returns this step's record, all arrays.
    """
    t, n = st["t"], len(st["bank_id"])
    rec = {"t": t}

    # 1. Cash arriving now: first pays overdue amounts, the rest goes to reserves.
    arrived = np.zeros(n)
    for name, sched in st["incoming"].items():
        cash = sched[:, t]
        if name.startswith("sale_"):
            st["sale_proceeds_due_bn"] -= cash
        elif name in BORROWING_LINE:  # a loan is booked when its cash arrives
            st[BORROWING_LINE[name]] += cash
            if name.startswith("repo_"):
                st[f"repo_out_{name.rsplit('_', 1)[1]}_bn"] += cash
        rec[f"arrived_{name}"] = cash.copy()
        arrived += cash
    paid_late = np.minimum(st["unpaid_outflows_bn"], arrived)
    st["unpaid_outflows_bn"] -= paid_late
    st["reserves_bn"] += arrived - paid_late
    rec["arrived"], rec["paid_late"] = arrived, paid_late

    # 2. The outflow: the funding line falls and the payment is owed until paid.
    #    A line cannot fall below zero; any excess request is recorded, not paid.
    #    Repo a lender refuses to roll ("repo_out_<class>_bn") is repaid the same
    #    way, and its securities stop being encumbered (Clarification 8).
    total_out = np.zeros(n)
    for line, amount in outflows.items():
        amount = np.broadcast_to(np.asarray(amount, float), (n,))
        actual = np.minimum(amount, st[line])
        st[line] -= actual
        if line.startswith("repo_out_"):
            c = line[len("repo_out_"):-len("_bn")]
            st["repo_bn"] -= actual
            st[f"repo_pledged_mv_{c}_bn"] -= actual / (1 - st["settings"]["repo"]["haircuts"][c])
        total_out += actual
        rec[f"outflow_{line}"] = actual
        rec[f"outflow_beyond_balance_{line}"] = amount - actual
    st["unpaid_outflows_bn"] += total_out
    rec["outflow"] = total_out

    # 3. Cover what is owed and not already on its way, source by source.
    on_its_way = sum(sched[:, t + 1:].sum(axis=1) for sched in st["incoming"].values())
    need = np.maximum(st["unpaid_outflows_bn"] - on_its_way, 0)
    rec["realized_loss"] = np.zeros(n)
    for name in st["order"]:
        cap = _capacity(st, name)
        # Under $1 of capacity is rounding dust (e.g. securities left after repo), not a source.
        rec[f"capacity_{name}"] = np.where(cap < ONE_DOLLAR_BN, 0.0, cap)  # recorded so tests can check the order
        cash = np.minimum(need, rec[f"capacity_{name}"])
        rec["realized_loss"] += _use(st, name, cash, t)
        rec[f"used_{name}"] = cash
        # Anything under $1 left over is rounding dust from the arithmetic, not a
        # real need; without this a later source would be tapped for a few cents.
        need = np.where(need - cash < ONE_DOLLAR_BN, 0.0, need - cash)

    # 4. Whatever no source could cover is the shortfall. It stays owed.
    rec["shortfall"] = need
    rec["unpaid_end"] = st["unpaid_outflows_bn"].copy()
    rec["paid_now"] = sum(rec[f"used_{k}"] for k in st["order"] if st["lags"][k] == 0)
    rec["equity"] = st["equity_bn"].copy()
    rec["reserves"] = st["reserves_bn"].copy()

    st["total_assets_bn"] = total_assets(st)
    st["t"] = t + 1
    return rec
