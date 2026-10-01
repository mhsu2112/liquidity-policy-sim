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

## 2026-10-01 — Clarification 5: the funding waterfall (session M1.3)
- **What changed:** implementation rules for the funding waterfall that the contract and Clarification 4 leave unstated.
  No value or range in the contract changes. Settings live in `config/funding.yaml`.
  1. **Fire-sale price impact.** Linear and cumulative within an episode: each extra dollar a bank sells loses
     λ × (market value that bank has already sold). Level 1 λ = 10 bp per $10bn (Greenwood, Landier & Thesmar 2015;
     Duarte & Eisenbach 2021); Level 2A λ = 30 bp per $10bn [ESTIMATE], agency MBS being less liquid than Treasuries.
     The price does not recover within the episode. These are starting values; contract section 7 lists fire-sale price
     impact among the parameters tuned in M1.10. The discount does not revalue securities the bank still holds.
  2. **Realized losses.** A sale realizes the unrealized loss on the amount sold (pro rata, Clarification 3) plus the
     fire-sale discount; both reduce equity.
  3. **Settlement.** Level 1 sales settle T+1 (Treasury regular-way settlement); Level 2A sales settle T+2 [ESTIMATE].
     Proceeds sit in a "sale proceeds due" asset until settled.
  4. **Bridging (speed tiers).** A payment due now is met first from sources that pay the same half-day; slower sources
     cover only what is left, and those payments are reported as late. Within each speed tier the order is reserves,
     securities sales, Home Loan Bank, discount window. As a result, when next-day sources are still short the window
     lends against Level 2A securities (next day) before they are sold (T+2).
  5. **Reserve operating floor:** 1% of total assets at the start of the episode [ESTIMATE].
  6. **Home Loan Bank capacity** (reading of Clarification 4): total advances are at most 75% of loans pledged to the
     Home Loan Bank; the pre-arranged line (5% of assets) is the same-day part of that total, not an addition to it.
     Loans pledged to the Home Loan Bank are not available at the discount window.
  7. **Treasury margin at the window:** 96% (the >5-year bucket in contract section 2b) for all Level 1 securities,
     as the banks have no maturity split. Agency MBS: 96%.
  8. **Loans not prepositioned** become usable at the window from day 11 (contract section 7: "not available within 10
     days"). Each collateral pool holds resi, CRE and C&I loans in the bank's own loan mix.
  9. **Unpaid outflows.** An outflow not yet paid stays on the balance sheet as a liability ("unpaid outflows") until
     cash arrives; the part no source can cover is reported every step as the shortfall and retried the next step.
- **Why:** the waterfall needs a price-impact rule, settlement timing and several accounting choices the contract does
  not state. Items 1, 3, 4, 5, 6, 7 and 8 were chosen by the owner in session M1.3; 2 and 9 follow from them.
- **Seen results before the change?** No. Agreed before any funding calculation ran.
- **Evidence:** `tests/test_funding.py` (order, limits, lags, hand-worked sale, balance, shortfall); also completes the
  evidence for Clarification 4.

## 2026-10-01 — Clarification 6: same-day repo of liquid securities (before session M1.3b)
- **What changed:** a funding source the waterfall lacked. No value or range in the contract changes.
  1. **Same-day private repo.** A bank can raise cash the same half-day by repo of Level 1 securities (haircut 2%) and
     agency MBS (haircut 5%) [ESTIMATE]. Repo does not realize unrealized losses; the securities stay on the balance sheet
     as encumbered and stop counting as HQLA while pledged.
  2. **Order.** Within the same-day tier, repo comes after reserves and before the Home Loan Bank line and the discount
     window. Securities sales (T+1 / T+2) remain in the next-day tier, used only for what repo cannot cover.
  3. **Rolling.** Repo is overnight and must be rolled each day. From session M1.4, repo lenders roll or refuse using the
     same confidence rule as other wholesale lenders, so access shrinks as a run deepens. Until then, repo always rolls.
  4. **Not official support.** Private repo is not counted as official support. The Fed's Standing Repo Facility is not
     modeled in v1.
- **Why:** in practice a bank can usually turn Treasuries and agency MBS into cash the same day by repo without selling
  them. Without this source the model understates how quickly liquid assets become cash, which affects every policy.
- **Seen results before the change?** No stress or policy results exist. The M1.3 demo (a mechanical test of two fixed
  outflows) showed Level 1 securities paying only the next day, which prompted this.
- **Evidence:** session M1.3b. `tests/test_funding.py`: repo comes after reserves and before the Home Loan Bank line
  (`test_repo_after_reserves_before_fhlb_line`); 2% / 5% haircuts (`test_repo_haircuts_applied`); no loss realized
  (`test_repo_realizes_no_loss`); a security is repo'd, pledged or sold only once; balance sheets balance after every step.
  `tests/test_lcr.py`: repo-encumbered securities leave HQLA. `make demo-waterfall`: SVB-01 now meets both the $10bn and
  $40bn outflows the same half-day (reserves $6.3bn; repo $13.7bn Level 1 and $30.0bn Level 2A; Home Loan Bank line
  $31m), with no late payment and no realized loss; before M1.3b, $37.8bn of the $40bn was paid a day late. Known gaps,
  left for M1.7 by the owner: securities pledged at the discount window still count as HQLA, and repo adds no LCR
  outflow (12 CFR 249.32(j)).
