# Liquidity Policy Simulator

**Disclosure.** This project's sponsor, Mike Hsu, publicly advocated a version of Option B
(a standalone discount window readiness requirement) while serving as Acting Comptroller of the
Currency. The comparison rules and hypotheses are published before any results are produced,
Option C's specification is reviewed by an outside supporter of LCR recognition, and results
are reported whether or not they match the hypotheses.

> **v0.1 proof of concept. Jev reference not validated against human readers. Not a v1 result.**
> The pre-registered v1 protocol is paused, not withdrawn; gold-set labels in this release come from an
> AI model (`docs/amendments.md`, Amendment 7).

## What this is

A small, open simulator that shows how a bank run plays out under different discount window
readiness policies, and what each policy costs:

| ID | Policy |
| --- | --- |
| A | Status quo |
| B | Standalone readiness requirement: reserves + prepositioned discount window capacity cover five days of stressed runnable outflows; mandatory prepositioning and quarterly test draws |
| C | Capped LCR recognition (2026 Treasury design): discount window capacity against non-HQLA collateral counts toward the LCR, up to 20% of net cash outflows (30% under funding stress), and up to 75 × recent overnight borrowing |
| C′ | As C, with no cap tied to recent borrowing and no draw requirement |
| E | Mandate only: required prepositioning and quarterly test draws, no new ratio or LCR credit |

## Status

**v0.1 proof of concept. Jev reference not validated against human readers. Not a v1 result.**

Release v0.1 (Amendment 7) is out: the full comparison run of A, B, B′, C, C′ and E over both scenarios, 40 banks and
the 35 stigma × supervision cells (25.8 million paired episodes), tagged `v0.1`; the display fix and diagnostics are
tagged `v0.1.1`. The pre-registered v1 protocol is paused, not withdrawn.

- Report: [`outputs/v0.1/report/index.html`](outputs/v0.1/report/index.html) (open the file in a browser)
- Limits: [`outputs/v0.1/report/limits.html`](outputs/v0.1/report/limits.html) — read these before the results
- Hypotheses memo (H1–H8 as pre-registered, with verdicts): [`outputs/v0.1/results/hypotheses_memo.md`](outputs/v0.1/results/hypotheses_memo.md)
- Rebuild everything from scratch with `make results` (about 8 minutes); diagnostics with `make diagnostics` and `make grace-causes`.

See `docs/implementation-plan.md` for the build sequence and `docs/amendments.md` for every rule and change.

## Key documents

- `docs/contract.md` — the comparison contract (the fixed rules of the comparison)
- `docs/hypotheses.md` — pre-registered expectations
- `docs/amendments.md` — every dated change after pre-registration
- `docs/PRD.md` — product requirements
- `docs/implementation-plan.md` — milestones and sessions

## Running it

Instructions arrive with session S0.2. The goal is one command: `make results`.

### Jev (milestone M2)

`signals/jev_client.py` is the only way the project calls Jev, TypeSafe's text-judgment model. It
works as follows:
- it calls the TypeSafe API directly, with the key read from `.env`, which is never committed;
- it records the exact model version on every call;
- it writes each call to `signals/audit_log.jsonl`, which holds a fingerprint of the text but not the text, and is
  kept local;
- its mock mode runs only when asked for, and mock answers are never results.

`make jev-hello` makes one live call on a made-up sentence. The simulation never calls Jev (CLAUDE.md).
