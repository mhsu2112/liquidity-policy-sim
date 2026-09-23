# Liquidity Policy Simulator

**Disclosure.** This project's sponsor, Mike Hsu, publicly advocated a version of Option B
(a standalone discount window readiness requirement) while serving as Acting Comptroller of the
Currency. The comparison rules and hypotheses are published before any results are produced,
Option C's specification is reviewed by an outside supporter of LCR recognition, and results
are reported whether or not they match the hypotheses.

## What this is

A small, open simulator that shows how a bank run plays out under different discount window
readiness policies, and what each policy costs:

| ID | Policy |
| --- | --- |
| A | Status quo |
| B | Standalone readiness requirement: reserves + prepositioned discount window capacity cover five days of stressed runnable outflows; mandatory prepositioning and quarterly test draws |
| C | Capped LCR recognition: discount window capacity against non-HQLA collateral counts toward the LCR, up to a cap |
| E | Mandate only: required prepositioning and quarterly test draws, no new ratio or LCR credit |

## Status

Setup. No results yet. See `docs/implementation-plan.md` for the build sequence.

## Key documents

- `docs/contract.md` — the comparison contract (the fixed rules of the comparison)
- `docs/hypotheses.md` — pre-registered expectations
- `docs/amendments.md` — every dated change after pre-registration
- `docs/PRD.md` — product requirements
- `docs/implementation-plan.md` — milestones and sessions

## Running it

Instructions arrive with session S0.2. The goal is one command: `make results`.
