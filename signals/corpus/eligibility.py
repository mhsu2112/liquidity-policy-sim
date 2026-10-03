"""Clarification 20 eligibility and personal-data screen for corpus passages (session M2.2).

Eligibility is mechanical and never judges tone. A passage already in scope (it names a bank
lending facility) is kept only if it refers to borrowing from a central bank by a bank or banks
(actual, planned, expected or avoided) or to how such borrowing is seen. Rules live in
config/corpus.yaml `eligibility` and are tried in a fixed order; the first that matches decides:

  1. perception  (stigma, "seen as", "sign of" ...)        -> keep
  2. avoided     (reluctant, avoided, declined to ...)       -> keep
  3. negations   ("no amounts outstanding", "did not borrow") -> borrowing rules are skipped
  4. borrowing   (borrowed, drew, "$X outstanding" ...)      -> keep
  5. planned     (plans/expects to borrow or use)            -> keep
  6. drop rules  (funding-source list, facility description, policy design), else no_borrowing

The result is always (keep?, reason), and the reason is written to the drop log for every drop.
"""

import re


class Eligibility:
    KEEP_ORDER = ["perception", "avoided", "borrowing", "planned"]
    BORROWING_RULES = {"borrowing", "planned"}   # the ones a negation switches off

    def __init__(self, settings):
        e = settings["eligibility"]
        flags = re.IGNORECASE
        self.keep = {k: [re.compile(p, flags) for p in e["keep"][k]] for k in self.KEEP_ORDER}
        self.negations = [re.compile(p, flags) for p in e["negations"]]
        self.drop = {k: [re.compile(p, flags) for p in v] for k, v in e["drop"].items()}
        self.personal = [re.compile(p) for p in settings["personal_data"]["patterns"]]   # case matters ("here from Knoxville")

    def judge(self, passage):
        """(True, keep reason) or (False, drop reason)."""
        negated = any(p.search(passage) for p in self.negations)
        for rule in self.KEEP_ORDER:
            if negated and rule in self.BORROWING_RULES:
                continue
            if any(p.search(passage) for p in self.keep[rule]):
                return True, rule
        for rule, patterns in self.drop.items():
            if any(p.search(passage) for p in patterns):
                return False, rule
        return False, "no_borrowing"

    def personal_data(self, passage):
        """True if the passage looks like it quotes a private individual (caller, reader, commenter)."""
        return any(p.search(passage) for p in self.personal)
