# Comparison contract

**Status: DRAFT — to be completed in session M0.1.** Not yet binding.
Once tagged `pre-registration-v1`, this file changes only through `docs/amendments.md`.

The starting text is the "Comparison contract" section of `docs/PRD.md`. M0.1 fills in every
exact value below. Items marked **YOUR CALL** need Mike's decision.

## 1. Bank population
- Archetype ranges (uninsured-deposit share, unrealized-loss ratio, liquid-asset share,
  loan-collateral share) — YOUR CALL
- Seed — to set
- LCR applicability by archetype under current rules — to confirm

## 2. Policy rules
- B: run-off rates for uninsured deposits and short-term wholesale funding — YOUR CALL
- B/E: test-draw size and duration (frequency: quarterly) — YOUR CALL
- C: cap 15% of total net cash outflows (swept 10–25%); Fed haircuts by collateral type — to source
- E: prepositioned amount equal to B's

## 3. What observers can see, and when
- Leak probability and lag ranges; whether B's ratio and C's LCR are publicly disclosed — YOUR CALL

## 4. How a policy "leads"
- Interval level (90%), paired runs, lead / tie / trade-off rule — as in PRD

## 5. Swept assumptions
- Final ranges and grid points for each swept assumption — YOUR CALL

## 6. Cost inputs
- Opportunity-cost rates by collateral type; test-draw cost; loan-to-reserve spread — YOUR CALL
