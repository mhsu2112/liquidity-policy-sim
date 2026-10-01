# The SVB-like banks under the false alarm (S2), and what it means for M3

> **Recorded (owner, 2026-10-02):** the "not sound" wording is corrected and the H8 restriction to surviving
> archetypes is decided in advance (Clarification 17). The tie-handling rule is proposed separately, for approval
> before any S2 policy run.

Written 2026-10-02, after M1.11. Policy A only; no policy has been compared.

## The result

Under the S2 rumor (news shock 0.45, Amendment 5), **SVB-like banks survive in only 1.3% of runs** and all of them
borrow, with median window support at 31% of assets. The other three archetypes barely move: survival 99.8–100%,
median deposit outflow 3–4%, and 0–3.6% of runs borrow at all. Clarification 16 reports the SVB-like result without
scoring it, "because those banks are not sound".

## Why it happens, and a correction to that wording

**The SVB-like banks are not insolvent at the start.** All 10 have positive mark-to-market equity: their unrealized
losses are 44–80% of book equity (median 63%). The run comes from the confidence rule (Clarification 8). Losses
amplify any news by (1 + g), where g is the share of equity lost on a mark-to-market basis:

| Archetype | Losses / equity (median) | S2 news after amplification (median) | Confidence on day 1 | Against θ = 0.6 |
|---|---|---|---|---|
| SVB-like | 0.63 | 0.73 | ≈ 0.27 | far below: a full run |
| Category III regional | 0.21 | 0.55 | ≈ 0.45 | a little below: mild outflows |
| GSIB | 0.15 | 0.52 | ≈ 0.48 | a little below: mild outflows |
| Diversified regional | 0.14 | 0.51 | ≈ 0.49 | a little below: mild outflows |

So in the model, a rumor about an SVB-like bank lands about as hard as S1 lands on a bank without losses. That is
arguably the SVB lesson, since its losses were public for months and a moderate trigger was enough. But it means
**S2 is not a false alarm for SVB-like banks.** They are solvent and fragile, not "not sound". I'd propose
Clarification 16's wording be corrected in the record (it doesn't change any result).

## What it means for M3

1. **H8 (no extra needless borrowing under B or E in S2).** For SVB-like banks, borrowing in S2 is not needless:
   without it, the bank fails. Counted in H8, SVB-like runs would measure run response, not needless borrowing. I
   propose a clarification **before any S2 policy run**: H8's "needless borrowing" is measured only on archetypes
   whose S2 runs under A survive in at least 90% of runs (today: diversified regional, Category III, GSIB), with
   SVB-like S2 results reported separately as a "rumor-triggered run". The hypothesis text stays frozen; only how its
   metric is applied gets fixed, and it's fixed before any result.
2. **H8 may tie by construction for the sound banks.** They borrow in 0–3.6% of S2 runs under A, so there's little
   borrowing for B or E to add. A tie would mean "nothing to measure", not "no effect". The M3 write-up should report
   how many runs borrowed at all, next to the paired difference.
3. **S2 effectively gives SVB-like banks a second severe scenario.** Their S1 and S2 results will look alike. M3
   shouldn't count them as independent evidence (for example, two "leads" for one policy from essentially the
   same run).
4. **Cliff-edge ties more generally.** Sound banks under S2 sit just below the tolerance edge; SVB-like banks are far
   past it. Small policy differences may not show up in either group. This is the "cliff-edge" limit in the
   validation report, now with numbers.
5. **No change to the run plan (Clarification 14) and no retuning.** S2 stays at 0.45 for every archetype. Only the
   scoring rule in point 1 needs your decision before M3.
