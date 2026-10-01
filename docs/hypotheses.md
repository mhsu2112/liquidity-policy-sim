# Pre-registered hypotheses

**Status: FINAL DRAFT v1.0 (2026-09-30), ready to freeze.** Updated for contract v0.5. Mike reconfirmed H1, restated H6 after Review 1, and confirmed all reasoning. Frozen at tag `pre-registration-v1`. Never edited afterwards.
Results are published against these hypotheses whether they confirm or contradict them.

**Who holds these expectations.** Mike Hsu, the project's sponsor, who publicly advocated a version of Option B.
They were recorded before any code compared policies. The reasoning lines were drafted by Claude from Mike's answers
and confirmed by Mike on 2026-09-30.

## Definitions used below

- **Leads / tie / trade-off:** as defined in `docs/contract.md` section 4 (paired runs, 90% intervals).
- **Mid-range cells:** market stigma ∈ {0.20, 0.35, 0.50} × supervision ∈ {penalizes, neutral, encourages} = 9 cells.
- **Defaults:** all other swept assumptions at their contract defaults unless a hypothesis says otherwise.
- **Scenario and bank:** S1 (fast run), SVB-like archetype, unless stated.

---

## H1. B and C perform about equally in the mid-range

> Reconfirmed by Mike on 2026-09-30, after Review 1 strengthened C (30% stress ceiling, usage multiple, 75% default
> uptake, routine-borrowing effect).

- **Expectation:** For SVB-like banks in S1, B and C are tied on survival in most mid-range cells.
- **Reasoning:** With the Treasury-style usage multiple, C also rewards prepositioning and routine test
  borrowing, so in the middle of the stigma range the two policies produce similar readiness.
- **Shown wrong if:** either B or C leads in 5 or more of the 9 mid-range cells.

## H2. What the five-day ratio adds beyond readiness (no directional prediction)

- **Expectation:** None recorded. Mike is unsure whether B's extra reserves add survival beyond E's mandated
  prepositioning and testing.
- **Pre-committed report:** the B-versus-E comparison in all 35 cells and each archetype, plus the feature-attribution
  share of the five-day-ratio switch. Either answer is reported as a finding, not as support for or against B.

## H3. LCR credit on its own may leave banks worse off than the status quo

- **Expectation:** When banks release most of the HQLA their credit allows, C does not improve survival over A and
  may lower it.
- **Reasoning:** Released HQLA is cash that is no longer on hand on day one of a run. Unless the credit also
  brings real, tested readiness, a bank has less usable liquidity than under A.
- **Test cells:** SVB-like and Category III regional, S1, HQLA release = 100%, voluntary uptake = 50% (the lowest level in
  the revised grid), all 35 stigma × supervision cells.
- **Shown wrong if:** C leads A in the majority of these cells.
- **Strong form (reported separately):** A leads C in at least one-third of these cells.

## H4. C matches or beats B under favorable conditions

- **Expectation:** C ties or leads B when any one of these holds:
  (a) market stigma is low (0 or 0.10);
  (b) voluntary prepositioning uptake is 100%;
  (c) supervisors encourage or strongly encourage borrowing.
- **Reasoning:** B's advantage comes mainly from forcing readiness and overcoming the reluctance to borrow.
  Where reluctance is low or readiness is universal anyway, that advantage shrinks.
- **Shown wrong if:** for any one of (a), (b) or (c), B leads C in the majority of cells meeting that condition.
  Each condition is scored and reported separately.

## H5. C with high HQLA release produces more false comfort

- **Expectation:** Under C with HQLA release = 100%, false comfort (reported LCR ≥ 100% but failure within 7 days) is
  clearly higher than under A.
- **Reasoning:** The reported LCR counts capacity that may not convert to cash in time, while real HQLA has
  fallen, so the headline ratio overstates resilience.
- **Test:** SVB-like and large-bank archetypes, S1, default grid.
- **Shown wrong if:** the paired difference (C minus A) in false comfort has a 90% interval that includes zero or is
  negative, in either archetype.

## H6. Cost ordering: B > E > A > C > C′

> Restated by Mike on 2026-09-30, after Review 1 added C′ and set C's default HQLA release to 100% of credit.

- **Expectation:** Median annual cost across the 40-bank sample, at contract defaults, ranks B highest, then E, then A
  (zero by construction), then C (net negative), then C′ (more negative than C).
- **Reasoning:** B adds reserve costs where the five-day test binds, on top of E's prepositioning and testing
  costs. C's released HQLA earns the loan spread, which outweighs prepositioning costs for banks that opt in. C′ earns the same
  credit without the cost of five usage draws every six months, so it is cheaper still.
- **Shown wrong if:** the ordering of medians differs at contract defaults. Each pairwise difference is reported with
  its spread across banks.

## H7. Supervisory posture matters about as much as the rule

- **Expectation:** The swing in survival from moving the supervisory dial end to end (policy held fixed) is comparable
  to the swing from changing policy (supervision held at neutral).
- **Shown wrong if:** the ratio of the two swings, for SVB-like banks in S1 at mid-range stigma, is below 0.5 or above 2.

## H8. No extra needless borrowing under readiness mandates

- **Expectation:** In the false-alarm scenario (S2), needless borrowing under B and under E is about the same as under A.
- **Reasoning:** A sound bank facing a rumor rarely needs to borrow, so easier access changes little.
- **Shown wrong if:** the paired difference (B minus A, or E minus A) has a 90% interval that excludes zero.

---

## What is not hypothesized

- No hypothesis on the diversified regional archetype under C: under current LCR scope, C has no effect there by
  construction (contract section 1c).
- No hypothesis on the Jev reference estimate's location. It is a marker on the stigma sweep, not an input to these tests.
