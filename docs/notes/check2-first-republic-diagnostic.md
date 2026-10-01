# Check 2 (First Republic-like) diagnostic

> **Decision (owner, 2026-10-01): neither option is built. Check 2 stays failed.** "No weekends; no BTFP; no
> contagion between banks" is added to the known limits (validation report and the `M1-complete` tag). The scripted
> contagion shock is **dropped permanently**. A weekend calendar is a separate M2 decision; it will be proposed only
> after measuring how often failures come from funding that was agreed but arrives the next day (Clarification 17).

Written 2026-10-01, after M1.11. **Diagnostic only:** nothing here changes the model, and the frozen settings
(fingerprint `05f9e763efc16772`) are not retuned. Every number comes from throwaway what-if runs under policy A on
the validation banks (200 runs each, M1.11 seed). Those scripts are not part of the project. **Seen validation
results: yes**, so any fix adopted from this note must be recorded that way.

## What failed

| Criterion (Clarification 16) | Needed | Model | |
|---|---|---|---|
| Survive past day 5 | ≥ 80% | 82.5% | met |
| Peak support (window + Home Loan Bank) | > 25% of assets | 6.0% | not met |
| Cumulative outflow by day 10 | $48–144bn | $21.3bn | not met |

## The finding: the binding constraint is on the funding side, not the run size

The First Republic-like bank can raise about **$28bn the same half-day**: reserves above the floor $10.6bn, its
same-day repo line $6.4bn and its Home Loan Bank line $10.6bn. Most of its other capacity, about **$86bn** (the window
on untested loans $25.6bn, the Home Loan Bank above the line $22.5bn, the window on securities $38bn), arrives
**one day later**. Under the strict failure test (Clarification 10 item 6), a payment waiting for tomorrow's cash
counts as unpaid. So any run big enough to resemble 2023 kills the bank on day 1 or 2 while window cash is still on
its way. In the loan-loss case below, $58bn of window lending was agreed, but the bank failed owing $12bn.

In 2023, First Republic had a **weekend** between its first bad day (Friday 10 March, about $25bn) and its worst
(Monday 13 March, about $40bn, after Signature's Sunday closure). That weekend gave it time to arrange Fed, Home Loan
Bank and JPMorgan funding. The model has no weekends: every half-day is a business day.

## The three candidate mechanisms, one at a time

| What-if (First Republic-like bank only) | Survive > day 5 | Peak support | Day-10 outflow | Fail ≤ 30 days |
|---|---|---|---|---|
| As reported (frozen model) | 82.5% | 6.0% | $21.3bn | 17.5% |
| **Mark-to-market loss on loans** 10% of loans (~$14bn) | 0.0% | 32.3% | $34.8bn | 100% |
| Same, 15% of loans (~$21bn) | 0.0% | 32.4% | $37.1bn | 100% |
| **Faster uninsured depositors:** fast share 65% (archetype 40%) | 45.0% | 10.7% | $22.6bn | 55% |
| Same, fast share 90% (SVB-like) | 21.0% | 13.2% | $24.3bn | 79% |
| **Contagion:** extra news +0.25 on day 2 | 0.5% | 15.5% | $25.2bn | 99.5% |
| Same, +0.50 on day 2 | 0.0% | 18.2% | $27.4bn | 100% |
| Same, +0.50 on day 4 | 12.0% | 15.5% | $27.2bn | 89% |

How each mechanism was emulated:
- **Loan losses** enter only the mark-to-market term g in the confidence rule. Collateral values are unchanged.
- **The uninsured share** itself is a given input (68%). What's adjustable is the share of uninsured depositors who
  move fast.
- **Contagion** is a second news shock that fades with the same half-life.

**Each one makes the run bigger, but the bank then dies early,** so outflows stop counting before they reach $48bn.
None of the three, alone, fixes Check 2; all three break its survival criterion.

### Would each break Checks 1, 3 or 4?

| Mechanism | Check 1 (Signature) | Check 3 (S2, 40 banks) | Check 4 (no shock) |
|---|---|---|---|
| Loan mark-to-market loss | Still passes: 100% fail by day 3; day-1 outflow 15% (was 23%) | **Breaks it** if applied to the 40 banks at 10%: 0 of 20 scored banks pass. The contract gives the sample no loan-loss range, so in practice the sample's would be zero and Check 3 is unaffected | Unaffected (no news, so g doesn't matter) |
| Faster depositors | Still passes (Signature is already SVB-like, 90%) | Unaffected if limited to the validation bank. If applied to the diversified-regional archetype it changes M3's sample (not scored in Check 3) | Unaffected |
| Contagion (scripted news) | Unaffected unless scripted for it too | Unaffected: it's an event in the First Republic scenario only | Unaffected |

## A test of the explanation: add weekends

The same what-if, with a business-day calendar: on Saturday and Sunday nobody can withdraw, but collateral lags
keep running. Day 1 is Friday 10 March for the First Republic and Signature checks, and Monday for the 40 banks
(Clarification 9).

| What-if (with weekends) | Survive > day 5 | Peak support | Day-10 outflow | Fail ≤ 30 days |
|---|---|---|---|---|
| Weekends only | 100% | 0.0% | $5.2bn | 0% |
| Weekends + loan loss 10% | 94.5% | 7.5% | $18.8bn | 5.5% |
| Weekends + loan loss 15% | 94.5% | 9.1% | $21.0bn | 7% |
| **Weekends + contagion +0.50 on Monday (day 4)** | **99.5%** | **18.4%** | **$69.7bn** | 18% |

With weekends: Check 1 still passes (100% fail by day 3; day-1 outflow 23%), Check 3 still passes (20 of 20) and
Check 4 still passes (40 of 40).

Weekends plus Monday contagion is the only combination that resembles 2023: First Republic survives a large run by
borrowing heavily. **It meets 2 of the 3 criteria. Support still falls short (18% against the 25% needed).** In 2023 First
Republic's window borrowing (~$109bn) partly reflects BTFP, new from 12 March (par-value lending on securities),
and JPMorgan funding, neither of which the model has.

## Proposed fix (not built; for your approval)

**Recommendation: build two mechanisms, as a new amendment marked "seen validation results: yes", then rerun all
four checks once, unchanged, and report them whatever they show.**

1. **A business-day calendar** (all scenarios). Weekends have no deposit withdrawals and no wholesale
   maturities. Window, Home Loan Bank and settlement lags keep counting in calendar half-days. The episode's day 1
   stays Monday for the 40-bank sample (Clarification 9). For the Signature and First Republic checks it's Friday 10
   March, matching 2023.
   *Why it's general, not a patch:* weekends exist under every policy, and they matter for readiness, because a bank
   with untested collateral gains two days.
   *Effect on M3:* most S1 runs end in days 1–3 and S2 banks stabilize by day 3, so it touches few runs. It could
   still move B and E's advantage from tested collateral, in either direction.
2. **Contagion news in the First Republic check only:** Signature's closure lands on Monday (day 4) as a fresh news
   shock the size of S1 (0.50). This is a scripted event in that check, like the $30bn consortium deposit, not a new
   model mechanism.
   *Caveat:* the 0.50 size was chosen after seeing this what-if. Tying it to S1's registered size is the least
   arbitrary choice, but it must be disclosed.

**What I do not recommend:**
- **Loan-book losses:** they kill the bank faster, and the contract gives the sample no data. Adding a loan-loss
  range would be a contract change.
- **A faster depositor share:** it's ad hoc and small.
- **Changing the strict failure test, or any frozen value.**

**Expected result:** Check 2 still fails, on support (about 18% against 25%), but with outflows inside the band and
the survival pattern right. Checks 1, 3 and 4 are unchanged in the what-ifs. A rerun after building could differ
slightly from these emulations.

**Alternative:** build nothing, close M1 as tagged ("Check 2 failed — known structural limit"), and list "no
weekends; no BTFP" among the known limits. This is the cleanest for credibility. The cost is that M3's runs for
mid-size banks under S1 rest on a run model that has never reproduced a survivable large run.
