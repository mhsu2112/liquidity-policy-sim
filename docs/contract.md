# Comparison contract

**Status: FINAL DRAFT v1.0 (2026-09-30), ready to freeze.** Review 1 of Option C is complete and signed off with changes (see `docs/review-log.md`). Becomes binding at tag `pre-registration-v1` (M0.6).
Becomes binding when tagged `pre-registration-v1`. After that it changes only through `docs/amendments.md`.

How to read this file:
- **[SOURCED]** — taken from a cited public source.
- **[ESTIMATE]** — Claude's estimate anchored to the cited facts; you may change it.
- **[YOUR CALL — recommended: X]** — a judgment only you should make. The recommendation is a default, not a decision.
- All money in $ billions unless stated. All percentages of the stated base.

---

## 0. Policy context (why Option C is specified the way it is)

On March 3, 2026, Treasury Secretary Bessent proposed that the LCR "give appropriate capped recognition" to
discount window capacity backed by prepositioned collateral, with the recognized amount "capped at the lesser of
the overall ceiling and some multiple of the bank's discount window borrowing over a specified period of time,"
and a mechanism to raise the cap during severe stress ([Treasury, 2026-03-03](https://home.treasury.gov/news/press-releases/sb0412)).
Vice Chair for Supervision Bowman testified in June 2026 that the Fed's "efforts focus on formally recognizing
discount window collateral in our liquidity regulations" ([Fed, 2026-06-04](https://www.federalreserve.gov/newsevents/testimony/bowman20260604a.htm)).
No rule text had been published as of this draft.

Option B follows the proposal that banks "have cash and discount window borrowing capacity sufficient to meet five
days of stress outflows" (as summarized by [BPI, 2024-01-25](https://bpi.com/clear-recognition-of-the-discount-window-would-improve-liquidity-rules/)).

**Decision C-1. DECIDED: v1 models Option C as the 2026 Treasury design (ceiling + usage multiple).**
The live 2026 proposal is a usage-conditioned cap (C2 in the PRD), not only the static cap (C). The outside
reviewer is likely to ask for it. Recommended: v1 models C as the Treasury design with two parameters:
an overall ceiling and a usage multiple. The static cap is the special case where the multiple is unlimited.
Following Review 1 (R1-2), the stress-adjustable cap (C3) is also in v1: Option C in v1 is the full Treasury design.

---

## 1. Bank population

**40 synthetic banks: 10 variants of each of four archetypes.** Each variant draws its values uniformly from the
ranges below using seed `20260923`. The same 40 banks are used everywhere. The Category III regional archetype was
added after Review 1 (R1-7).

### 1a. Anchor facts

| Fact | Value | Source |
| --- | --- | --- |
| SVB total assets, end-2022 | ~$209–212bn | [FDIC, 2023-09-28](https://www.fdic.gov/news/speeches/2023/spsept2823a.html); [Fed SVB review](https://www.federalreserve.gov/publications/2023-April-SVB-Evolution-of-Silicon-Valley-Bank.htm) |
| SVB uninsured share of deposits | ~94% (Fed); ~90% (FDIC) | same |
| SVB securities share of assets | 55% (large-bank peers: 25%) | [Fed SVB review](https://www.federalreserve.gov/publications/2023-April-SVB-Evolution-of-Silicon-Valley-Bank.htm) |
| SVB HTM unrealized loss | $15.2bn, 16.6% of $91.3bn amortized cost | [CPA Journal, 2024](https://www.cpajournal.com/2024/04/08/bank-failures-highlight-the-shortcomings-of-held-to-maturity-htm-accounting/) |
| SVB outflows | >$40bn on March 9; ~$100bn expected March 10 | [Fed SVB review](https://www.federalreserve.gov/publications/2023-April-SVB-Evolution-of-Silicon-Valley-Bank.htm) |
| SVB LCR status | Category IV; would have become subject to reduced (70%) LCR in Q4 2023 after crossing $50bn wSTWF in Dec 2022 | [Fed SVB review, regulation chapter](https://www.federalreserve.gov/publications/2023-April-SVB-Federal-Reserve-Regulation.htm) |
| Signature total assets, end-2022 | ~$110bn | [FDIC, 2023-09-28](https://www.fdic.gov/news/speeches/2023/spsept2823a.html) |
| Signature uninsured share | ~90% | same |
| Signature outflow | $18.6bn (20% of deposits) in hours on March 10 | [Harris testimony, 2023-05-18](https://www.banking.senate.gov/download/harris-testimony-5-18-23&download=1) |
| Signature collateral readiness | FRBNY would not accept $18bn of capital call loans; CRE loans "would take weeks to assess" | same |
| First Republic total assets, end-2022 | $212.6bn | [FDIC OIG MLR, 2023](https://www.fdicoig.gov/sites/default/files/reports/2023-12/EVAL-24-03.pdf) |
| First Republic uninsured share | 68% ($119.5bn) | same |
| First Republic outflows | ~$25bn March 10; ~$40bn March 13; $96bn March 10–24 | same; [YPFS](https://elischolar.library.yale.edu/cgi/viewcontent.cgi?article=5705&context=ypfs-documents2) |
| First Republic discount window peak | ~$109bn; failed May 1, 2023 | [FDIC OIG MLR](https://www.fdicoig.gov/sites/default/files/reports/2023-12/EVAL-24-03.pdf) |
| Large-bank safe-asset share | ~25% of balance sheet (Treasury's characterization) | [ABA Banking Journal, 2026-03](http://bankingjournal.aba.com/2026/03/regulators-set-sights-on-liquidity-coverage-ratio-reform/) |

### 1b. Archetype ranges [ESTIMATE, anchored to 1a]

| Variable | SVB-like (Cat. IV) | Diversified regional (Cat. IV) | Regional (Cat. III) | GSIB / large bank |
| --- | --- | --- | --- | --- |
| Total assets ($bn) | 100–250 | 100–250 | 250–700 | 700–2,000 |
| Uninsured share of deposits | 80–95% | 35–55% | 35–55% | 40–60% |
| Securities share of assets | 40–60% | 15–25% | 18–28% | 20–30% |
| Of which Level 1 (Treasuries, reserves-like) | 30–50% | 40–60% | 40–60% | 50–70% |
| Of which Level 2A (agency MBS) | 50–70% | 40–60% | 40–60% | 30–50% |
| Unrealized loss on securities | 8–17% | 4–10% | 4–10% | 3–8% |
| Reserves (cash at Fed) share of assets | 5–10% | 4–8% | 5–10% | 8–15% |
| Loans share of assets | 30–45% | 60–70% | 55–65% | 45–60% |
| Loan mix (resi / CRE / C&I) | 30 / 20 / 50 | 35 / 35 / 30 | 35 / 30 / 35 | 40 / 20 / 40 |
| Share of loans eligible as collateral | 60–80% | 70–90% | 70–90% | 70–90% |
| Short-term wholesale funding share of liabilities | 3–8% | 5–10% | 8–15% | 10–20% |
| Equity share of assets | 7–9% | 8–10% | 8–10% | 7–9% |

**Decision 1-1. DECIDED: these ranges are the published starting point.** Results are reported per archetype, so an odd range is visible, not hidden.

### 1c. LCR applicability, held constant across policies [SOURCED]

Under the 2019 tailoring rules: Categories I–II, full LCR; Category III, full LCR if wSTWF ≥ $75bn, otherwise 85%;
Category IV ($100–250bn assets), 70% LCR if wSTWF ≥ $50bn, otherwise no LCR
([Fed board memo, 2019-10-10](https://www.federalreserve.gov/aboutthefed/boardmeetings/files/tailoring-board-memo-20191010.pdf)).

| Archetype | Category | LCR applied |
| --- | --- | --- |
| GSIB / large bank | I–II, and III with wSTWF ≥ $75bn | Full (100%) |
| Regional (Cat. III) | III, wSTWF < $75bn | Reduced (85%) — added after Review 1 |
| SVB-like | IV, wSTWF ≥ $50bn | Reduced (70%) — Decision 1-2 |
| Diversified regional (Cat. IV) | IV, wSTWF < $50bn | None |

**Decision 1-2. DECIDED: SVB-like banks face the reduced 70% LCR; no-LCR is a sensitivity.** SVB crossed the $50bn wSTWF threshold in December 2022
and would have been subject to a 70% LCR from Q4 2023. Options: (a) 70% LCR, matching SVB's actual trajectory;
(b) no LCR, matching most Category IV banks. With (b), Option C does nothing for SVB-like banks by construction.
Recommended (a), with (b) reported as a sensitivity.

**Consequence to state publicly:** under current scope, Option C has no effect on the Category IV diversified regional archetype.
That is a feature of today's rules, not of the model. Extending the LCR to them is C-ext (v2).

---

## 2. Policy rules

### 2a. The four switches

| Switch | A | B | C | E |
| --- | --- | --- | --- | --- |
| Prepositioning mandate | off | on | off | on |
| Testing mandate | off | on | off | on |
| Five-day ratio | off | on | off | off |
| LCR credit | off | off | on | off |

### 2b. Discount window collateral values [SOURCED]

Fed collateral margins (lendable value as % of value), effective July 1, 2026
([Fed discount window collateral valuation](https://www.frbdiscountwindow.org/pages/collateral/collateral_valuation)):

| Collateral | Margin used | Fed range |
| --- | --- | --- |
| Treasuries, 0–5 years | 98% | 99–98% |
| Treasuries, >5 years | 96% | 97–95% |
| Agency MBS | 96% | 98–94% |
| Residential mortgages (1–4 family, first lien) | 80% [ESTIMATE within range] | 95–59% |
| CRE loans (normal risk, ~5-year) | 72% | 72–75% (5-yr bucket) |
| C&I loans (normal risk, ~3–5-year) | 80% | 77–86% (3–5-yr buckets) |

**Decision 2-1. DECIDED: use these single margins, with ±5 percentage points as a sensitivity.**

### 2c. Option B: five-day readiness ratio

(Reserves + post-margin prepositioned capacity) ÷ (5-day stressed runnable outflows) ≥ 100%.

Runnable outflows = uninsured deposits + short-term wholesale funding maturing within 5 days.

**Decision 2-2. DECIDED: over the five-day window, 40% of uninsured deposits and 100% of short-term wholesale funding run off.**
The 40% matches the LCR's 30-day rate for uninsured non-operational corporate deposits
([eCFR §249.32(h)(1)(ii)](https://www.ecfr.gov/current/title-12/chapter-II/subchapter-A/part-249/subpart-D/section-249.32)),
compressed into five days. The 100% treats all short-term wholesale funding maturing within the window as not rolling.
Sensitivity: 100% of uninsured deposits (a full run).

**Test draws (B and E):** quarterly. **Decision 2-3. DECIDED: $50m, overnight.**

**Prepositioning under B:** the lowest amount that passes the ratio, using the bank's cheapest eligible collateral first.
**Under E:** the same collateral amount the bank would preposition under B, without the ratio.

### 2d. Option C: LCR credit

- **Eligible:** post-margin capacity against loans and other non-HQLA collateral pledged to the Fed only.
  Securities pledged to the window already count as unencumbered HQLA if withdrawable
  ([Fed](https://www.federalreserve.gov/monetarypolicy/discountrate.htm)), so they earn no extra credit.
- **Ceiling (Review 1, R1-1):** 20% of total net cash outflows in the ordinary course. Swept 15%, 20%, 25%.
- **Stress-adjustable ceiling (R1-1, R1-2):** the ceiling rises automatically to 30% when market indicators show funding
  stress (trigger: SOFR above the top of the federal funds target range). Because v1's scenarios are bank-specific and the
  trigger would rarely fire (SOFR stayed within the target range in March 2023), the trigger is run as a switch in S1:
  **off**, or **fires on day 1**. Banks that opt in preposition ahead of time enough collateral to support credit at the 30%
  ceiling, reflecting the incentive the reviewer describes.
- **Usage multiple (R1-3, R1-4):** credit ≤ k × the average of the 1st, 3rd and 5th largest overnight discount window
  borrowings over the prior two quarters. Default k = 75; swept over {no limit, 75, 100, 125}. A bank therefore needs at
  least five overnight draws every six months, each sized so the formula supports its target credit. Banks that opt in
  make these draws, and their cost is counted (section 6).
- **After a draw:** existing LCR treatment for discount window loans applies. Unused-capacity credit falls by the amount drawn.
- **Released HQLA (R1-5, resolved):** banks that opt in shift their balance sheets toward non-HQLA after prepositioning,
  which is part of the rationale for C. Default: HQLA released equal to **100%** of the credit received; swept 0%, 50%, 100%.
  Released funds go to loans.
- **C′, no usage cap (named variant, suggested by Reviewer 1):** C with the same 20% and 30% ceilings but no usage
  multiple, so no draws are needed to earn credit. This is the "no limit" point of the usage-multiple sweep, reported as a
  named policy alongside A, B, C and E. Banks under C′ have no reason to make usage draws, so their routine borrowing
  rate equals A's.
- **Uptake (R1-6):** share of eligible banks that preposition voluntarily. Default 75%; swept 50%, 75%, 100%.

---

## 3. What observers can see, and when

| Route | Default | Range swept |
| --- | --- | --- |
| Fed weekly aggregate report | Weekly; no bank named | Informativeness falls as other borrowing rises |
| Fed named disclosure | ~2 years later ([Fed](https://www.federalreserve.gov/monetarypolicy/discountrate.htm)) | Not swept (outside episode) |
| Bank announcement | Bank chooses; mandatory if material | Not swept |
| Leak of named borrowing | 20% chance within episode; 1-day lag | 0–50%; 0–5 days |
| Inference from asset sales / pulled lines | Same or next half-day | Not swept (mechanics) |
| B's ratio disclosed publicly | Quarterly, like the LCR | on / off |
| C's LCR (including credit) disclosed | Quarterly for banks already under LCR public disclosure | Not swept |

**Decision 3-1. DECIDED: B's five-day ratio is publicly disclosed quarterly, like the LCR.** Keeping it supervisory is a sensitivity.

### 3a. Routine-borrowing effect (added after Review 1)

The more often banks borrow routinely, the less any single draw signals distress. This applies identically to every policy.

- **Routine borrowing rate (r):** average routine draws per bank per quarter across the banking system, set by each policy's
  rules: A and C′, voluntary tests only (0.1); B and E, quarterly tests (1.0); C, usage draws by banks that opt in
  (uptake × 2.5, since five draws per six months is 2.5 per quarter).
- **Effective stigma** = market stigma (swept, section 5) × e^(−s × r), where s is the strength of the effect.
- **Effective supervisory and internal reluctance** = the supervisory treatment cost (swept, section 5) × e^(−s × r), with
  the same s. Routine draws are expected to normalize borrowing in board and examiner conversations as well as in markets
  (Review 1, final check). Same rule for every policy.
- **Strength s:** swept over {0, 0.3, 0.7}. With s = 0 there is no routine-borrowing effect.
- **Reported outcome:** effective stigma, and routine borrowing frequency, for each policy (section 4).
- **Not modeled in v1:** market-wide effects on short-term funding markets, and stronger banks borrowing ahead of a
  stress to take advantage of funding-market dislocations. Both need several banks and a funding-market scenario
  (S4, S5 in v2).

---

## 4. How a policy "leads"

- Reported together: survival rate, liquidity shortfall, official support drawn, annual cost, and effective stigma (added after Review 1).
- Also reported: routine borrowing frequency under each policy.
- Paired runs; differences with 90% intervals.
- **Leads:** at least as good on both survival and shortfall, with the interval for at least one excluding zero.
- Otherwise **tie** or **trade-off** against cost. No dollar value per failure.

---

## 5. Swept assumptions and grid

| Assumption | Grid points |
| --- | --- |
| Market stigma: chance a known draw is read as distress | 0, 0.10, 0.20, 0.35, 0.50, 0.70, 0.90 (7 points; Jev estimate marked) |
| Supervisory treatment of borrowing | strongly penalizes, penalizes, neutral, encourages, strongly encourages (5 points) |
| Leak probability / lag | 0, 20%, 50% / 0, 1, 5 days |
| C ordinary ceiling | 15%, 20%, 25% (default 20%) |
| C stress trigger (S1) | off, fires on day 1 |
| C usage multiple | no limit (= C′), 75, 100, 125 (default 75) |
| C voluntary uptake | 50%, 75%, 100% (default 75%) |
| C share of HQLA released | 0%, 50%, 100% (default 100%) |
| Routine-borrowing effect strength s | 0, 0.3, 0.7 |
| Collateral margins | −5, 0, +5 percentage points |
| Prepositioning cost rates | ×0.5, ×1, ×1.5 |
| Depositor coordination | low, medium, high |

Main grid: 7 × 5 = 35 stigma-by-supervision cells, as in the PRD. Other sweeps run on a coarser grid around the defaults.

---

## 6. Cost inputs

| Input | Default | Range | Basis |
| --- | --- | --- | --- |
| Opportunity cost: Treasuries and agency securities | 2 bp | 1–3 | [ESTIMATE] still count as HQLA; operational cost only |
| Opportunity cost: residential mortgages | 20 bp | 10–30 | [ESTIMATE] forgone Home Loan Bank capacity |
| Opportunity cost: CRE loans | 20 bp | 10–30 | [ESTIMATE] forgone Home Loan Bank capacity or sale |
| Opportunity cost: C&I loans | 15 bp | 8–23 | [ESTIMATE] forgone sale or securitization |
| Test draw cost | primary credit rate minus interest on reserves × size × 1 day, ×4 per year | — | [ESTIMATE] negligible at $50m; to confirm current spread |
| C usage draws | primary credit rate minus interest on reserves × draw size × 1 day, ×5 per six months | — | Added after Review 1; draw sizes set by the usage-multiple formula |
| Loan-to-reserve yield spread (B's extra reserves; C's released HQLA) | 250 bp | 200–300 | [ESTIMATE] |

**Decision 6-1. DECIDED (session M0.4): these are the cost defaults.** The test-draw spread is set from the published primary credit rate and interest on reserve balances at the time of the M1.8 session and recorded in config.

---

## 7. Mechanics fixed before tuning

| Item | Value | Basis |
| --- | --- | --- |
| Time step | Two half-days per day; 30 days | PRD |
| Discount window lag: prepositioned and tested in last 90 days | Same half-day | [ESTIMATE] |
| Lag: prepositioned, not tested | 1 day | PRD (1–3 days); [ESTIMATE] |
| Lag: securities not prepositioned | 1 day | [ESTIMATE] |
| Lag: loans not prepositioned | Not available within 10 days | Signature: CRE "would take weeks to assess" |
| Home Loan Bank advances | Same day up to pre-arranged line; next day above it | [ESTIMATE] |
| HQLA haircuts in LCR | Level 1: 0%; Level 2A: 15%, 40% cap | [SOURCED] U.S. LCR rule |

**Parameters tuned in M1.10, and only these:** depositor sensitivity to news; coordination strength;
slow-depositor lag; wholesale roll threshold; fire-sale price impact. Everything else in this file is fixed before tuning.

---

## Decisions (summary)

| ID | Question | Status |
| --- | --- | --- |
| C-1 | Model C as the 2026 Treasury design (ceiling + usage multiple) in v1? | **Decided: yes** |
| 1-2 | SVB-like LCR status | **Decided: 70% LCR**; no-LCR as sensitivity |
| 2-2 | B's run-off rates over five days | **Decided: 40% uninsured deposits, 100% short-term wholesale**; full run as sensitivity |
| 3-1 | Disclose B's ratio publicly? | **Decided: yes, quarterly like the LCR**; private as sensitivity |
| 1-1 | Accept archetype ranges? | **Decided: yes** |
| 2-1 | Collateral margins | **Decided: single margins, ±5 pp** |
| 2-3 | Test draw size | **Decided: $50m overnight, quarterly** |
| 2-4 | C usage multiple | **Superseded by Review 1: {no limit, 75, 100, 125}; default 75** |
| R1 | Review 1 changes | **Accepted**: R1-1 to R1-8, plus named variant C′ and the routine-borrowing effect on supervisory reluctance (see `docs/review-log.md`) |
| 6-1 | Cost defaults | **Decided: yes (M0.4)** |

## For the outside reviewer (M0.5)

Five disclosure templates in `signals/templates/disclosure_templates.yaml` frame evidence in ways a reviewer should
check for balance, and are flagged rather than removed:
- **AN6, L2, W2** let a bank present a draw as routine testing under B or E, which may favor B and E.
- **L3, P5** show borrowing to maintain credit, and a ratio falling as recent borrowing drops, under C's usage multiple, which may cut against C.
- **W4** assumes analysts can identify a borrower from district-level weekly figures.

