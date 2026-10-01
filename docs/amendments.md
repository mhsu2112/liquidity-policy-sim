# Amendments

Every change to `docs/contract.md` or frozen parameters after `pre-registration-v1` is recorded here.
Nothing is changed silently.

Format for each entry:

## YYYY-MM-DD — short title
- **What changed:**
- **Why:**
- **Seen results before the change?** yes / no
- **Evidence (test or reviewer comment):**

## 2026-09-30 — Clarification 1: how the 40 synthetic banks are drawn (before session M1.1) — date corrected from 2026-10-01 on 2026-09-30
- **What changed:** three implementation rules the contract left unstated. No value or range in the contract changes.
  1. **Asset shares must fit.** Securities, reserves and loans are drawn from their contract ranges. If together they exceed
     100% of assets, that bank's draw is rejected and redrawn (same seed sequence). Whatever is left is "other assets",
     which are not liquid and not eligible as collateral.
  2. **Liabilities.** Equity and short-term wholesale funding are drawn from their ranges; all remaining liabilities are
     deposits, split into insured and uninsured using the drawn uninsured share.
  3. **LCR category is assigned by bank type** (contract section 1c), not recomputed from each bank's drawn funding mix.
     The synthetic funding mix is not detailed enough to compute weighted short-term wholesale funding.
- **Why:** the contract gives ranges for each variable but not how they combine. These rules keep every drawn value
  inside its published range and keep the LCR treatment exactly as the contract states.
- **Seen results before the change?** No. No code had run.
- **Evidence:** contract section 1b ranges can sum to more than 100% for SVB-like banks (up to 115%).

## 2026-09-30 — Clarification 2: Level 1 and Level 2A split of securities (session M1.1)
- **What changed:** an implementation rule the contract left unstated. No value or range in the contract changes.
  Each bank draws its Level 1 share of securities from its section 1b range; the rest of its securities are Level 2A.
  For every archetype the two section 1b ranges mirror each other (e.g. SVB-like 30–50% and 50–70%), so the
  Level 2A share always falls inside its own published range. Securities hold no Level 2B or non-HQLA assets.
- **Why:** the contract gives both ranges but not how they combine. Owner chose this option in session M1.1.
- **Seen results before the change?** No. Decided before any bank was generated.
- **Evidence:** `tests/test_banks.py` checks every bank's Level 2A share against its section 1b range.
