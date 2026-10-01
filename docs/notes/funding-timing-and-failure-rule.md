# Funding timing and the strict failure rule

Written 2026-10-02 (session M1.12). **Policy A only** for every stress run (project Rule 2); the cross-policy
measurement is pre-registered for M3 (Clarification 18). Frozen settings unchanged (fingerprint `05f9e763efc16772`).
Numbers: `make timing-gap` → `outputs/timing_gap_summary.json`, `outputs/timing_gap.csv` (every cell),
`outputs/timing_exposure.csv`. **Nothing is built from this note; the recommendation below is for your decision.**

## The question

The strict rule (Clarification 10 item 6) fails a bank at the end of any half-day in which more than 0.1% of its
starting assets is still owed, even when cash it has already been granted arrives the next morning. How often is
that the reason banks fail in the model?

## Answer: every time

Policy A: S1 and S2 × 40 banks × 35 cells × 200 runs (560,000 episodes), plus the validation banks at the tuning
cell. A failure is "pure timing" if what's owed is no more than the cash already agreed and arriving within the next
day, and equity is positive.

| Scenario, bank type | Runs failing | Pure timing | Partly covered | Not covered | Equity < 0 | Median owed at failure | Median cash on its way |
|---|---|---|---|---|---|---|---|
| S1 SVB-like | 99.4% | **100%** | 0 | 0 | 0 | $7.9bn | $62.3bn |
| S1 Diversified regional | 4.9% | **100%** | 0 | 0 | 0 | $0.8bn | $7.5bn |
| S1 Regional (Cat. III) | 4.8% | **100%** | 0 | 0 | 0 | $2.4bn | $26.7bn |
| S1 GSIB | 0.2% | **100%** | 0 | 0 | 0 | $9.8bn | $101.7bn |
| S2 SVB-like | 98.5% | **100%** | 0 | 0 | 0 | $6.0bn | $46.5bn |
| S2 other types | 0–0.2% | **100%** | 0 | 0 | 0 | — | — |
| SVB validation bank (S1) | 100% | **100%** | 0 | 0 | 0 | $12.9bn | $104.8bn |
| Signature-like (S1) | 100% | **100%** | 0 | 0 | 0 | $9.2bn | $48.7bn |
| First Republic-like (S1) | 17.5% | **100%** | 0 | 0 | 0 | $1.7bn | $14.6bn |

**No run fails for lack of any source, and none for negative equity.** Every failure happens on a half-day when
same-day sources ran out while far larger next-day funding was already agreed: typically 8–10× what was owed. A
typical example: SVB-01 fails on the afternoon of day 1 owing $3.8bn with $28.6bn arriving; it would owe $0.6bn the
next morning and nothing after that.

## What other rules would do (same runs, report only)

| | Strict (now) | Grace: fail only if owed exceeds tomorrow's cash | Two strikes: owed above the tolerance two half-days running |
|---|---|---|---|
| S1 SVB-like, runs failing | 99.4% | 15.9% (5 half-days later, median) | 65.1% (1 half-day later) |
| S1 all 40 banks | 27.3% | 4.0% | 17.4% |
| S2 SVB-like | 98.5% | 12.9% | 72.2% |
| SVB validation bank | 100% | 34.0% | 100% |
| Signature-like | 100% | 34.0% | 81.5% |
| First Republic-like | 17.5% | 0% | 5.5% |

**Caveat:** these are upper bounds. The bank's own borrowing decision assumes the strict rule, and the path after
a strict failure is reused, so the true effect of a rule change would be somewhat smaller.

## Which policies the gap favors (static, no stress run)

The same-half-day share of each bank's two-day funding capacity, from one waterfall step with no behavior, median by
bank type:

| Bank type | A | B | B′ | C | C′ | E |
|---|---|---|---|---|---|---|
| SVB-like | 0.23 | 0.72 | 0.52 | 0.28 | 0.19 | 0.72 |
| Diversified regional | 0.25 | 0.56 | 0.53 | 0.25 | 0.25 | 0.56 |
| Regional (Cat. III) | 0.41 | 0.71 | 0.66 | 0.57 | 0.36 | 0.71 |
| GSIB | 0.65 | 0.87 | 0.88 | 0.79 | 0.61 | 0.87 |

Testing makes prepositioned collateral pay the same half-day (contract 7). That is the main thing B, B′, E, and C's
opted-in banks change. These are capacities, not results, and say nothing yet about survival under any policy.

## Is the strict rule the right one?

**For.**
- It is how the 2023 banks actually ended. SVB was closed the morning after it could not settle the previous day's
  outflows (a ~$1bn negative Fed balance; California DFPI order, 10 March 2023), not because it ran out of collateral.
- Signature was closed with collateral it could not get valued in time.
- The rule is also what the SVB tuning rests on (fails by day 2). Under the grace rule the SVB validation bank would
  survive in about two-thirds of runs, so changing the rule would undo the frozen fit.

**Against.**
- It treats a bank that is fully funded by tomorrow morning as failed.
- Banks in March 2023 did survive nights on promised funding, including First Republic and the regionals.
- In the model the rule is the **only** way banks fail, so every survival difference between policies is a difference
  in same-day cash.

**Why the gap belongs in M3, not engineered away.** The readiness policies act precisely on this gap: testing turns
next-day cash into same-day cash. A grace period or a weekend calendar would shrink the very difference M3 is meant
to measure, and would do so by assumption. Policy A's Check 2 failure and the "pure timing" result describe the same
fact from two sides.

## Recommendation (for your decision; nothing is built)

1. **Keep the strict rule in v1.** It matches how 2023 failures happened. It's what the frozen tuning rests on.
   Changing it would require retuning.
2. **Don't add a weekend calendar in v1.** With day 1 on a Monday (Clarification 9), S1 runs resolve on days 1–3
   and S2 banks stabilize by day 3. A calendar would mostly matter where it's least checkable, and it would rescue
   banks by assumption.
3. **Make the gap visible in M3 instead:**
   - report each policy's timing bands, pre-registered (Clarification 18);
   - report the grace-rule counterfactual as a sensitivity that is **reported, not scored**, computed from the same
     recorded runs with no new runs. It shows how much of each policy's survival advantage depends on the strict
     rule.
   - Point 3's second item would need a short amendment to the run plan's reporting (not its run counts).
4. **v2:** a business-day calendar and a closure rule that allows a supervisory "funding committed overnight" grace,
   both validated on the 2023 weekend sequence.
