# Brief for coding agents: Liquidity Policy Simulator

Read this whole file at the start of every session. Then read the documents it points to.

## Who you are working for

The owner is Mike Hsu, a former bank regulator (Acting Comptroller of the Currency, 2021–2025).
He knows banking regulation deeply but does not write code. He directs coding agents.

- Explain every plan, change, error and result in plain English. No jargon without a one-line explanation.
- Keep files short and comments plentiful. A comment says *why*, in words a banker would use.
- Every session ends with something he can run with one command and open in Excel or a browser.
- When you are unsure what he wants, ask one clear question rather than guessing.

## What this project is

A small, open simulator comparing discount window readiness policies (A status quo, B standalone
five-day readiness requirement, C capped LCR recognition, E prepositioning-and-testing mandate only)
during a bank run, and what each costs. It is a showcase, built to be inspected and extended.

## Documents, in order of authority

1. `docs/contract.md` — the comparison contract. **The source of truth.** Once tagged
   `pre-registration-v1`, it changes only through a dated entry in `docs/amendments.md`.
2. `docs/hypotheses.md` — pre-registered expectations. Never edited after `pre-registration-v1`.
3. `docs/PRD.md` — the product requirements document.
4. `docs/implementation-plan.md` — milestones M0–M4 and the numbered sessions (S0.1, M1.3, ...).

If these conflict, the higher one wins. If the contract is silent, stop and ask; do not invent a rule.

## How a session works

- Each session has one ID and one goal from `docs/implementation-plan.md`. Do only that goal.
- Start in plan mode. Explain the plan in plain English and wait for approval before writing code.
- Write tests alongside code. Run `make test` before finishing; all tests must pass.
- Finish with: (1) the one command Mike should run to see the result, (2) a plain-English summary of
  what changed, what you assumed, and anything he should know, (3) a commit whose message starts
  with the session ID, e.g. `M1.3: funding waterfall`.
- If a fix fails twice, stop. Explain the problem and suggest reverting to the last commit.

## Rules that protect the credibility of the results (never break these)

1. **Tests check mechanics only.** Balance sheets balance, the LCR matches hand calculations,
   runs are reproducible, rules match the contract. No test may assert that any policy wins,
   loses, or performs better or worse than another.
2. **No policy comparison under stress before M3.** Until the tags `M1-complete` and `M2-complete`
   both exist, only run stress episodes under policy A. Static calculations of each policy's
   ratios and costs are allowed.
3. **No tuning after `params-frozen`.** After session M1.10, `config/params_frozen.yaml` changes only
   through `docs/amendments.md`, and only to fix a mechanical error proven by a new test.
4. **Never change a test to make it pass** without first explaining, in plain English, why the test
   itself was wrong. Wait for approval.
5. **No hidden numbers.** Every parameter lives in a config file with a comment citing the contract
   section or source. No magic numbers in code.
6. **Report results as they come out.** Never adjust code, parameters or charts after seeing policy
   results in order to change them. Surprising results get explained, not fixed.
7. **Disclosure stays.** The README's disclosure of the owner's prior support for Option B stays on
   the front page and in every published output.

## Rules for Jev (TypeSafe's text-judgment model)

- All Jev calls go through one client in `signals/` with mock mode and an audit log
  (text hash, questions, answers, model version, timestamp).
- Use the TypeSafe API directly (`TYPESAFE_API_KEY`). OpenRouter is a fallback for prototyping only.
  Record the exact model version on every call.
- One question = one judgment. Combine answers in code, never in a prompt.
- Jev never does arithmetic, dates or policy weights. Those live in code or config.
- Jev never runs inside the simulation. The only link is the frozen file in `signals/frozen/`.
- Mock answers are for testing plumbing only and are never reported as results.
- Public and synthetic text only. No supervisory, confidential or personal data.

## Technical conventions

- Python 3.11+ and NumPy. No agent-based modeling framework.
- Vectorized from day one: each actor's state is an array with one row per run; a step updates all
  runs together. Never loop over runs in Python.
- Settings in YAML under `config/`. Policies are combinations of four switches:
  prepositioning mandate, testing mandate, five-day ratio, LCR credit.
- Fixed random seeds. Same seed, same inputs → identical outputs. Paired runs: every policy sees
  the same banks, shocks and random draws.
- Every output file is stamped with the git commit, a hash of the config, and the Jev-estimate version.
- One-command targets in the `Makefile` (`make test`, `make results`, and per-session demos).
- Tests with pytest in `tests/`.

## Folder layout

```
config/      banks, policies, scenarios, behavioral parameters (YAML)
engine/      balance sheet, LCR, funding waterfall, daily step
agents/      bank, depositors, counterparties, supervisor
signals/     Jev client, route-tagged templates, gold set, frozen estimate
cost/        steady-state cost model
validation/  SVB-, Signature-, First Republic-like and false-alarm checks
analysis/    metrics, trade-off chart, feature attribution, replays
tests/       automated checks
docs/        contract, hypotheses, amendments, PRD, implementation plan
outputs/     generated files (not saved to history; rebuilt with `make results`)
```

## Security

- Keys live only in `.env`, which is git-ignored. Never print, log or commit a key.
- Before every commit, check that no key, password or `.env` content is included.
