"""The supervisor's five-level dial (session M1.5).

The dial runs from "strongly penalizes" to "strongly encourages" borrowing
(contract section 5). Each level sets the supervisory and internal cost of
borrowing, in units of the bank's loss if it fails (Clarification 9, item 3):
a cost of 0.15 means management will not borrow until it thinks there is more
than a 15% chance of failing without the window (ignoring market stigma).

Routine borrowing shrinks that reluctance exactly as it shrinks market stigma
(contract section 3a): effective cost = level cost x e^(-s x r), with the same
s, for every policy. Nothing here knows which policy is running; a policy can
only act through the routine borrowing rate r.

In M1.5 the supervisor only sets this cost and learns of draws through the
supervisory channel; it takes no action inside the episode. The cost is used
by the borrowing decision in M1.6.
"""

import numpy as np


def level_cost(level_names, sup_cfg):
    """Cost before the routine-borrowing effect, one per row."""
    levels = sup_cfg["levels"]
    return np.array([levels[k] for k in np.atleast_1d(level_names)], float)


def routine_discount(s, r):
    """The contract 3a factor e^(-s x r): 1 with no routine borrowing effect."""
    return np.exp(-np.asarray(s, float) * np.asarray(r, float))


def effective_supervisory_cost(cost, s, r):
    """Contract 3a: supervisory and internal reluctance falls with routine borrowing."""
    return np.asarray(cost, float) * routine_discount(s, r)
