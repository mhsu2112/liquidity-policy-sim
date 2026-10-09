> **v0.1 proof of concept. Jev reference not validated against human readers. Not a v1 result.**

# Hypotheses memo: v0.1 results against H1–H8 as pre-registered

**Disclosure.** This project's sponsor, Mike Hsu, publicly advocated a version of Option B (a standalone discount window readiness requirement) while serving as Acting Comptroller of the Currency. The comparison rules and hypotheses are published before any results are produced, Option C's specification is reviewed by an outside supporter of LCR recognition, and results are reported whether or not they match the hypotheses.

Stamp: commit `f2bcb09c5073` · config `3835bc0add36d4c2` · frozen settings `05f9e763efc16772` · Jev `v0.1-signals (frozen at e14cd74; markers provisional)` (jev-1.13.0) · 200 paired runs per bank per cell.

The hypothesis text below is quoted unedited from `docs/hypotheses.md` (frozen at `pre-registration-v1`). Where it leaves room, Clarification 31 B7 (recorded before any stress run of B, B′, C, C′ or E) fixes how it is scored; H8 follows Clarifications 17–18. Verdicts: supported, not supported, untestable, or reported (H2, which makes no prediction).

## H1. B and C perform about equally in the mid-range

- **Expectation:** For SVB-like banks in S1, B and C are tied on survival in most mid-range cells.
- **Reasoning:** With the Treasury-style usage multiple, C also rewards prepositioning and routine test borrowing, so in the middle of the stigma range the two policies produce similar readiness.
- **Shown wrong if:** either B or C leads in 5 or more of the 9 mid-range cells.

| Part | Result | Verdict |
|---|---|---|
| main | SVB-like, S1, 9 mid-range cells: B leads in 9, C leads in 0, tie in 0, trade-off in 0. Shown wrong if either leads in 5 or more. | **not supported** |

## H2. What the five-day ratio adds beyond readiness (no directional prediction)

- **Expectation:** None recorded. Mike is unsure whether B's extra reserves add survival beyond E's mandated prepositioning and testing.
- **Pre-committed report:** the B-versus-E comparison in all 35 cells and each archetype, plus the feature-attribution share of the five-day-ratio switch. Either answer is reported as a finding, not as support for or against B.

| Part | Result | Verdict |
|---|---|---|
| main | S1, B vs E in all 35 cells — svb_like: B leads 0, E leads 0, tie 35, trade-off 0; diversified_regional: B leads 0, E leads 0, tie 35, trade-off 0; regional_cat3: B leads 0, E leads 0, tie 35, trade-off 0; gsib: B leads 0, E leads 0, tie 35, trade-off 0. Five-day-ratio switch's Shapley contribution to survival (9 mid-range cells) — svb_like: +14.5 pp [+14.1, +15.0] of a +67.0 pp total effect of all four switches; diversified_regional: +0.0 pp [-0.0, +0.0] of a +2.9 pp total effect of all four switches; regional_cat3: +0.2 pp [+0.1, +0.2] of a +4.1 pp total effect of all four switches; gsib: +0.0 pp [+0.0, +0.0] of a +0.2 pp total effect of all four switches. | **reported** |

## H3. LCR credit on its own may leave banks worse off than the status quo

- **Expectation:** When banks release most of the HQLA their credit allows, C does not improve survival over A and may lower it.
- **Reasoning:** Released HQLA is cash that is no longer on hand on day one of a run. Unless the credit also brings real, tested readiness, a bank has less usable liquidity than under A.
- **Test cells:** SVB-like and Category III regional, S1, HQLA release = 100%, voluntary uptake = 50% (the lowest level in the revised grid), all 35 stigma × supervision cells.
- **Shown wrong if:** C leads A in the majority of these cells.
- **Strong form (reported separately):** A leads C in at least one-third of these cells.

| Part | Result | Verdict |
|---|---|---|
| main | SVB-like and Category III regional, S1, uptake 50%, released 100%, 70 cells: C leads A in 31, A leads C in 0, tie 39, trade-off 0. Shown wrong if C leads in a majority. | **supported** |
| strong_form | SVB-like and Category III regional, S1, uptake 50%, released 100%, 70 cells: C leads A in 31, A leads C in 0, tie 39, trade-off 0. Strong form holds if A leads in at least one-third (23.3). | **not supported** |

## H4. C matches or beats B under favorable conditions

- **Expectation:** C ties or leads B when any one of these holds: (a) market stigma is low (0 or 0.10); (b) voluntary prepositioning uptake is 100%; (c) supervisors encourage or strongly encourage borrowing.
- **Reasoning:** B's advantage comes mainly from forcing readiness and overcoming the reluctance to borrow. Where reluctance is low or readiness is universal anyway, that advantage shrinks.
- **Shown wrong if:** for any one of (a), (b) or (c), B leads C in the majority of cells meeting that condition. Each condition is scored and reported separately.

| Part | Result | Verdict |
|---|---|---|
| a | SVB-like, S1, market stigma 0 or 0.10, 10 cells: B leads C in 10, C leads B in 0, tie 0, trade-off 0. Shown wrong if B leads in a majority. | **not supported** |
| b | SVB-like, S1, uptake 100%, 35 cells: B leads C in 35, C leads B in 0, tie 0, trade-off 0. Shown wrong if B leads in a majority. | **not supported** |
| c | SVB-like, S1, supervisors encourage or strongly encourage, 14 cells: B leads C in 14, C leads B in 0, tie 0, trade-off 0. Shown wrong if B leads in a majority. | **not supported** |

## H5. C with high HQLA release produces more false comfort

- **Expectation:** Under C with HQLA release = 100%, false comfort (reported LCR ≥ 100% but failure within 7 days) is clearly higher than under A.
- **Reasoning:** The reported LCR counts capacity that may not convert to cash in time, while real HQLA has fallen, so the headline ratio overstates resilience.
- **Test:** SVB-like and large-bank archetypes, S1, default grid.
- **Shown wrong if:** the paired difference (C minus A) in false comfort has a 90% interval that includes zero or is negative, in either archetype.

| Part | Result | Verdict |
|---|---|---|
| main | S1, all 35 cells. svb_like: false comfort C 99.6% vs A 99.3%, C − A +0.29 pp [+0.01, +0.56]; gsib: false comfort C 0.2% vs A 0.3%, C − A -0.06 pp [-0.21, +0.09]. Shown wrong if the interval includes zero or is negative in either archetype. | **not supported** |

## H6. Cost ordering: B > E > A > C > C′

- **Expectation:** Median annual cost across the 40-bank sample, at contract defaults, ranks B highest, then E, then A (zero by construction), then C (net negative), then C′ (more negative than C).
- **Reasoning:** B adds reserve costs where the five-day test binds, on top of E's prepositioning and testing costs. C's released HQLA earns the loan spread, which outweighs prepositioning costs for banks that opt in. C′ earns the same credit without the cost of five usage draws every six months, so it is cheaper still.
- **Shown wrong if:** the ordering of medians differs at contract defaults. Each pairwise difference is reported with its spread across banks.

| Part | Result | Verdict |
|---|---|---|
| main | Median annual cost across the 40 banks ($m vs A): B 6.4, E 6.4, A 0.0, C -133.1, C′ -133.1. Pairwise differences across banks (min / median / max): B-E 0.0 / 0.0 / 0.0; E-A 0.0 / 6.4 / 37.2; A-C 0.0 / 133.1 / 3,037.5; C-C′ 0.0 / 0.0 / 0.1. Expected strictly B > E > A > C > C′. | **not supported** |

## H7. Supervisory posture matters about as much as the rule

- **Expectation:** The swing in survival from moving the supervisory dial end to end (policy held fixed) is comparable to the swing from changing policy (supervision held at neutral).
- **Shown wrong if:** the ratio of the two swings, for SVB-like banks in S1 at mid-range stigma, is below 0.5 or above 2.

| Part | Result | Verdict |
|---|---|---|
| main | SVB-like, S1, mid-range stigma: supervision swing (dial end to end, policy fixed) 0.0 pp; policy swing (across A, B, C, C′, E at neutral) 72.2 pp; ratio 0.00. Shown wrong if below 0.5 or above 2. | **not supported** |

## H8. No extra needless borrowing under readiness mandates

- **Expectation:** In the false-alarm scenario (S2), needless borrowing under B and under E is about the same as under A.
- **Reasoning:** A sound bank facing a rumor rarely needs to borrow, so easier access changes little.
- **Shown wrong if:** the paired difference (B minus A, or E minus A) has a 90% interval that excludes zero.

| Part | Result | Verdict |
|---|---|---|
| main | S2, scored archetypes (A survives ≥ 90%): diversified_regional, regional_cat3, gsib. B vs A: 159 of 1050 bank × cells qualify; runs borrowing A 1.6%, B 1.7%; exact ties 97.9%; needless borrowing B − A +0.012 $bn [-0.045, +0.069]; E vs A: 159 of 1050 bank × cells qualify; runs borrowing A 1.6%, E 1.7%; exact ties 97.9%; needless borrowing E − A +0.012 $bn [-0.045, +0.069]. Shown wrong if either interval excludes zero. | **supported** |

## Note recorded after results (Amendment 8)

`docs/hypotheses.md` says, under "Not hypothesized", that C has no effect on the diversified regional archetype by construction. The text above is left unedited. In the model, those banks get no LCR credit, but C's policy-wide routine-borrowing rate (contract 3a) lowers their effective stigma, so C can and does differ from A for them.

## Tally

not supported: 8, reported: 1, supported: 2 (counting each scored part).
