"""Placeholder check from session S0.2.

It only confirms the plumbing works: the right Python version is in use and
the add-ons load. It says nothing about any policy. Real checks replace it
from M1 onward.
"""

import sys


def test_environment_is_ready():
    # The project brief requires Python 3.11 or later.
    assert sys.version_info >= (3, 11)

    # The add-ons listed in requirements.txt must load without error.
    import numpy  # noqa: F401
    import yaml  # noqa: F401
