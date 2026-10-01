"""Wholesale and repo lenders: roll or refuse each morning (session M1.4).

Rules from docs/amendments.md Clarification 8. Each lender judges the bank's
chance of survival using the same confidence the depositors see: from M1.5
both read the same public news through the information routes (Clarification 9).
Lenders see inference signs a half-day before depositors, but in M1.5 those
signs carry no confidence effect of their own, so the number stays shared. Lenders' cut-offs are spread evenly around
the roll threshold, so the share refusing rises from 0 to 100% as confidence
falls through that band. Refusals must be repaid that day through the funding
waterfall. The Home Loan Bank and discount window are not affected.
"""

import numpy as np


def refusal_share(conf, agents, behavior):
    """Share of lenders whose cut-off is above today's confidence."""
    theta = behavior["wholesale_roll_threshold"]["value"]
    spread = agents["lenders"]["cutoff_spread"]
    return np.clip((theta + spread - conf) / (2 * spread), 0, 1)


def morning_decisions(st, conf, agents, behavior):
    """Refused repo and unsecured wholesale funding to be repaid today.

    Repo is overnight: the refused share of the whole repo book is repaid, which
    returns its securities. Unsecured funding matures 1/30 of its starting
    balance a day; the refused share of what matures is repaid. Refusing lenders
    also stop new repo in the same proportion.
    """
    r = refusal_share(conf, agents, behavior)
    st["repo_access"] = 1 - r
    maturing = np.minimum(agents["lenders"]["stwf_maturing_share_per_day"] * st["stwf_start_bn"], st["stwf_bn"])
    return r, {"repo_out_level1_bn": r * st["repo_out_level1_bn"],
               "repo_out_level2a_bn": r * st["repo_out_level2a_bn"],
               "stwf_bn": r * maturing}
