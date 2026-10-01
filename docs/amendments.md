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

## 2026-09-30 — Clarification 3: LCR outflow rates and simplifications (session M1.2)
- **What changed:** implementation rules for the current-rules LCR, which contract section 7 gives only in part
  (haircuts and the 40% cap). No value or range in the contract changes. Settings live in `config/lcr.yaml`.
  1. **30-day outflow rates (12 CFR 249.32):** insured deposits 3% (§249.32(a)(1), stable retail); uninsured deposits
     40% (§249.32(h)(1)(ii), non-operational corporate, the same basis as contract Decision 2-2); short-term wholesale
     funding 100% (§249.32(h)(3), treated as unsecured from financial counterparties and maturing within 30 days).
  2. **No inflows.** Contractual inflows are set to zero. The 75% inflow cap (§249.30) is kept in the formula but has
     nothing to act on.
  3. **No peak-day add-on.** The maximum cumulative net outflow day amount (§249.30(b)) is left out: the synthetic banks
     have no maturity schedule.
  4. **Unrealized losses reduce securities to market value pro rata.** Level 1 and Level 2A holdings each lose the
     bank's same percentage.
  5. **Banks with no LCR requirement** (Category IV diversified regional) get a ratio computed on unadjusted outflows
     (factor 100%) and are marked "not required".
  6. **Mark-to-market equity** (book equity less unrealized loss) is reported for information only.
- **Why:** the LCR needs outflow rates and a treatment of losses that the contract does not state. Rates are the owner's
  proposal, checked against 12 CFR 249.32 and agreed in session M1.2.
- **Seen results before the change?** No. Agreed before any LCR was computed.
- **Evidence:** `tests/test_lcr.py` (hand-calculated example, 40% cap, calibration, pro-rata loss) and
  `outputs/lcr_worked_examples.xlsx`.

## 2026-10-01 — Clarification 4: where collateral sits under the status quo, and Home Loan Bank lending (before session M1.3)
- **What changed:** two implementation rules the contract left unstated. No value or range in the contract changes.
  1. **Collateral placement under policy A.** Each bank's eligible loans start 30% prepositioned at the Fed, 40% pledged to
     the Home Loan Bank, and 30% unpledged. The Fed and Home Loan Bank shares are each swept ±20 percentage points, with
     the unpledged share adjusting so the three add to 100%. Fed-prepositioned collateral starts untested; banks test
     voluntarily at the status-quo routine borrowing rate in contract section 3a.
  2. **Home Loan Bank lending.** The bank can borrow up to a pre-arranged line of 5% of total assets on the same day
     (swept 3%, 5%, 8%). Beyond the line, it can borrow on the next day up to 75% of the value of loans pledged to the Home
     Loan Bank [ESTIMATE]. This applies contract section 7 ("same day up to pre-arranged line; next day above it").
  3. **Policies that require prepositioning** (B, E, and C for banks that opt in) take the extra collateral from unpledged
     loans first, then from loans pledged to the Home Loan Bank, which reduces Home Loan Bank capacity one for one.
- **Why:** the waterfall needs a starting position for collateral and a Home Loan Bank rule, and the contract gives only
  the timing rule.
- **Seen results before the change?** No. Agreed by the owner before any funding calculation ran.
- **Evidence:** to be added in session M1.3 (tests of capacity and timing).
