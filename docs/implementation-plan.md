# Liquidity Policy Simulator — Implementation Plan

> **Superseded in part by `docs/contract.md` v0.5 (2026-09-30).** The contract governs wherever the two differ. Main changes
> since this PRD was written, mostly from the outside review of Option C (`docs/review-log.md`):
> - **Option C is the full 2026 Treasury design:** a 20% ceiling rising to 30% under funding stress (run as an off / on
>   switch in S1); credit capped at 75 × the average of the 1st, 3rd and 5th largest overnight discount window borrowings
>   over two quarters; default uptake 75%; default HQLA release 100% of credit.
> - **New named variant C′:** C's ceilings with no usage cap and no draw requirement.
> - **Policies compared in v1:** A, B, C, C′ and E.
> - **Bank population:** 40 banks, four types; Category III regional banks (85% LCR) added.
> - **B's five-day test:** 40% of uninsured deposits and 100% of short-term wholesale funding; B's ratio disclosed quarterly.
> - **Routine-borrowing effect:** the more often banks borrow routinely, the lower both market stigma and supervisory and
>   internal reluctance, by the same rule for every policy. Effective stigma is a reported outcome.

Sep 23, 2026 · Mike Hsu · Live version: https://claude.ai/code/artifact/8b7daca1-f330-4828-9436-270b6c6f8125

## Overview

The build is five milestones and about 35 working sessions over roughly 10 weeks. Claude Code writes and tests the code. You set direction, approve each plan before work starts, and check results in plain English. Every session ends with something you can run yourself and a saved checkpoint you can return to.

This plan implements the Liquidity Policy Simulator PRD (`docs/PRD.md`). Where the two differ, the PRD and its comparison contract win.

| Milestone | Weeks | What it produces | Sessions | Mostly you, or mostly Claude Code? |
| --- | --- | --- | --- | --- |
| Setup | Before week 1 | A project folder with saved history, ready for work | 2 | Both |
| M0 Comparison contract | 1–3 | The published rules of the comparison, before any results exist | 6 | You, helped by Claude |
| M1 Engine and cost model | 2–6 | The simulator itself, checked against 2023 bank failures | 11 | Claude Code |
| M2 Jev reference estimate | 3–6, alongside M1 | Jev's reading of each disclosure, tested against human labels | 6 + labeling | Both |
| M3 Comparison | 7–8 | The full set of runs, charts, replays and scorecard | 6 | Claude Code |
| M4 Review and release | 9–10 | Outside review, public repository and write-up | 4 | You |

**Where things live.** Everything goes in a new folder, `liquidity-policy-sim`, inside `Work/06-policy-simulation`. Your existing Research folder and the digital-twins paper stay where they are, untouched.

## Words you'll see

You don't need to know how any of these work, only what they mean when Claude Code says them.

| Term | What it means for you |
| --- | --- |
| Repository (repo) | The project folder, plus a complete history of every saved change. |
| Commit | A saved checkpoint with a one-line label. You can always go back to one. |
| Tag | A permanent name on an important commit, such as "M1-complete". Used at each milestone gate. |
| Branch | A side copy of the project for trying something without touching the main version. |
| GitHub | The website where the repository is published. Private until you make it public. |
| Push | Sending your saved commits up to GitHub. |
| Test | A small automatic check that the code does what it should, e.g. "the balance sheet always balances." Green means pass; red means fail. |
| Plan mode | Claude Code proposes what it will do and waits for your OK before touching anything. |
| CLAUDE.md | A standing brief in the folder that Claude Code reads at the start of every session: who you are, the rules, what not to do. |
| Config file | A plain-text settings file (bank sizes, policy rules, ranges) that you can open and read. |
| Seed | A number that fixes the random draws, so the same run gives the same answer every time. |
| Mock mode | Jev code running with fake answers, so the plumbing can be tested without a key or cost. |
| `make` command | A one-word shortcut that runs a whole job, such as `make test` or `make results`. |

## How every session works

Every coding session follows the same seven steps and takes 30–90 minutes of your attention. One session builds one piece; never ask for two milestones' worth of work at once.

1. **Open Claude Code in the project folder.** In Terminal: `cd ~/Work/06-policy-simulation/liquidity-policy-sim` then `claude`.
2. **Paste the session prompt.** Each session below has a one-line goal. Use this pattern:

   ```
   Session M1.3. Goal: <goal from the plan>. Read CLAUDE.md and
   docs/contract.md first. Use plan mode. Explain your plan in plain
   English before writing any code.
   ```
3. **Read the plan and approve or push back.** Ask: does this match the contract? Is it doing only this session's piece? If unsure, ask "what could go wrong with this plan?"
4. **Let it build.** It writes the code and the tests together, and runs the tests.
5. **Run the check yourself.** Each session lists a "You check" item. Usually it's `make test` (all green) plus one command that prints a result in plain English or opens a chart.
6. **Ask for a plain-English summary.** "Summarize what changed, what you assumed, and anything I should know." Paste anything surprising into Cowork if you want a second opinion.
7. **Commit.** "Commit this with a clear message and push to GitHub." At a milestone gate, also ask it to tag the commit.

**When something goes wrong:** ask Claude Code to explain the error in plain English and propose a fix. If two tries fail, stop, tell it to undo back to the last commit, and start the session fresh with a smaller goal.

**Between sessions:** type `/clear` or start a new Claude Code window. A fresh session with CLAUDE.md does better than one long session that has drifted.

## Setup

Setup takes two short steps: Claude in Cowork creates the folder and the standing brief, and one Claude Code session turns it into a saved history, connects it to GitHub and sets up Python. Nothing here involves the simulation itself.

### S0.1 — Folder and brief (Cowork, 20 minutes) — DONE

Claude in Cowork created `06-policy-simulation/liquidity-policy-sim` with:

- **`CLAUDE.md`**, the standing brief. It tells Claude Code who you are and how to explain things, and sets these rules:
  - The comparison contract is the source of truth. It changes only through a dated amendment file.
  - Tests check mechanics only. No test may assert that a policy wins.
  - No policy-comparison runs before M3. No parameter tuning after the M1 tuning session.
  - All model calls go through one Jev client with an audit log. Jev never does arithmetic and never runs inside the simulation.
  - The code runs many scenarios at once as arrays from the start. Every output is stamped with its version.
  - Plain-English comments, short files, and one command for everything.
- **`docs/`**, holding copies of the PRD and this plan, plus starter files for the contract, hypotheses and amendments.
- **Empty sub-folders** matching the PRD layout, and a `README.md` whose first paragraph discloses your prior support for Option B.
- **`.gitignore`** (keeps `.env`, outputs and clutter out of history) and **`.env.example`** (where your key will go).

### S0.2 — Saved history, GitHub and Python (Claude Code, 30–45 minutes)

Prompt: "Session S0.2. Read CLAUDE.md. Check that this Mac has Python 3.11 or later, git and the GitHub command-line tool. Install what's missing, explaining each step. Turn this folder into a git repository and make the first commit. Create a private GitHub repository called liquidity-policy-sim and push. Set up a Python environment, and add a Makefile with `make test` running one placeholder test."

**You check:** `make test` shows one green pass, and the repository appears on your GitHub page as private.

**Keys.** Copy `.env.example` to `.env` and put your TypeSafe key in it. That file is never saved to history or GitHub. It isn't needed until M2.

## M0 — Comparison contract (weeks 1–3)

M0 turns the PRD's comparison contract into exact, published numbers and rules before any code touches a policy. Most of the work is judgment calls only you can make; Claude drafts and you decide. The gate is the outside reviewer signing off on Option C and the contract going public.

| Step | Where | What happens | Your role | Done when |
| --- | --- | --- | --- | --- |
| M0.1 Contract, exact values | Cowork | Claude drafts `docs/contract.md` from the PRD and fills every number: the ranges for the 30 banks, run-off rates for uninsured deposits and wholesale funding, Fed collateral haircuts by type, and the LCR treatment for each archetype | Decide each value flagged "your call" | No blanks left in the contract |
| M0.2 Hypotheses | Cowork | Claude interviews you on what you expect and why, then writes `docs/hypotheses.md`: each expectation, the reasoning, and what result would show it wrong | Give your honest expectations, including where C might win | You would be comfortable seeing any result judged against it |
| M0.3 Disclosure templates | Cowork | For each information route and policy, draft the text an observer would actually see. About 20 base templates, each tagged to a route | Cut anything no real observer would see | Every template has a route |
| M0.4 Cost inputs | Cowork | Confirm opportunity-cost rates by collateral type, test-draw costs and the reserve yield spread, with a one-line reason for each | Approve or change each rate | Cost section of the contract complete |
| M0.5 Outside reviewer | Email | Send the reviewer the Option C rules and swept ranges. Make agreed changes. Also line up the two gold-set labelers for M2 | Choose and approach the reviewer and labelers | **Gate: reviewer signs off on C** |
| M0.6 Publish | Claude Code | Commit the contract, hypotheses and templates; make the repository public; tag it `pre-registration-v1` | Read the final files once more before saying go | **Gate: public, dated, tagged** |

**Prompt for M0.6:** "Session M0.6. Commit docs/contract.md, docs/hypotheses.md and signals/templates/. Show me the list of files that will become public and wait for my OK. Then make the repository public and tag this commit pre-registration-v1."

**After M0.6** the contract and hypotheses are frozen. Any later change goes in `docs/amendments.md` with the date and reason, and is never edited silently.

## M1 — Engine and cost model (weeks 2–6)

M1 builds the simulator one piece at a time, each piece checked before the next starts. Until the last two sessions, everything runs under the status quo or as static calculations. No session compares how policies perform under stress; that waits for M3.

| Session | Goal | You check | Done when |
| --- | --- | --- | --- |
| M1.1 Settings and banks | Read the config files and generate the 30 synthetic banks from the contract's ranges, using a fixed seed | Open `outputs/banks.csv` in Excel: 30 rows, sizes and ratios look plausible | Same 30 banks every time |
| M1.2 Balance sheet and LCR | Hold each bank's balance sheet and compute its LCR under current rules | Open the worked-examples spreadsheet Claude builds; the model matches the hand calculations | Balance sheets always balance; LCR matches 3 worked examples |
| M1.3 Funding waterfall | When cash is needed, draw in order: reserves, securities sales (with price impact and realized losses), Home Loan Bank, discount window | `make demo-waterfall` prints a plain-English account of one bank meeting an outflow | Each source has its limits and delays |
| M1.4 Depositors and counterparties | Fast and slow uninsured depositors, insured depositors, and wholesale lenders who roll or refuse | `make demo-run` shows a bigger shock causing a faster run | Behavior responds in the expected direction |
| M1.5 Supervisor and information | The supervisor's response dial, plus the contract's information routes: weekly aggregate, leaks, announcements, inference | Demo log shows who learned what, and when | Nobody learns anything without a route |
| M1.6 Borrowing decision and discount window | The bank's borrow-or-not rule; the window's haircuts and readiness lag; half-day steps; end conditions (fail, stabilize, day 30) | One full episode, day by day, in plain English | An episode runs start to finish |
| M1.7 Policy switches | The four switches and A, B, C, E as combinations. B's five-day ratio; C's credit accounting exactly as in the contract | `make policy-table`: each bank's ratios under each policy, with no stress run | Contract checks pass, e.g. C never credits HQLA collateral |
| M1.8 Cost model | Annual steady-state cost per bank per policy, by collateral type | `outputs/costs.csv`; spot-check one bank against Claude's hand calculation | Totals match the worked example |
| M1.9 Speed and repeatability | Run 10,000 episodes at once; time it; confirm the same seed gives identical results | `make benchmark` prints the time, and "identical: yes" | On track for the under-an-hour target |
| M1.10 Tuning (status quo only) | Set behavioral parameters so an SVB-like bank reproduces 2023 outflow timing and failure. Then freeze them | Chart of model vs. 2023 pattern | **Parameters frozen and tagged `params-frozen`** |
| M1.11 Out-of-sample checks | Run Signature-like, First Republic-like and false-alarm cases with no retuning. Write a plain-English validation report | Read the report: what passed, what didn't, and why | **Gate: tagged `M1-complete`; results reported whether they pass or fail** |

**Prompt for M1.10 (the sensitive one):** "Session M1.10. Tune only the behavioral parameters listed in the contract, using the SVB-like bank under policy A only. Do not run any other policy. When done, write the final values to config/params_frozen.yaml, commit and tag params-frozen. From now on, refuse any request to change these values except through docs/amendments.md."

## M2 — Jev reference estimate (weeks 3–6, alongside M1)

M2 produces Jev's reading of each disclosure and tests it against human labels. It runs on its own branch, in separate sessions from M1, and never touches the simulator. The gate is completed human labeling, with Jev's agreement with the labelers published.

| Session | Goal | You check | Done when |
| --- | --- | --- | --- |
| M2.1 Jev client | Bring over the client from your jev-supervision-lab folder: TypeSafe first, mock mode, audit log, model version recorded on every call | `make jev-hello` prints one live answer and the model version; one new line in the audit log | Live call works; key never appears in history |
| M2.2 Calibration corpus | Collect public passages about discount window and emergency-facility borrowing, 2007–2024: news, analyst notes, filings. Store links and short excerpts only | Open the corpus spreadsheet; skim 20 random rows | About 2,000 usable passages to start; 10,000 is the target |
| M2.3 Gold set and labeling sheet | Pick 300 passages at random. Build a spreadsheet with one-page instructions: "Does this treat the borrowing as a sign of distress?" | Try labeling 10 yourself; instructions are clear | Sheet sent to both labelers |
| Labeling (human, not a session) | Two people label all 300, independently, without seeing Jev's answers | — | Both sheets returned, ~2–3 days each |
| M2.4 Gold-set test | Compare Jev with each labeler and the labelers with each other. Write a plain-English report with the numbers | Read the report: does Jev agree with people about as often as they agree with each other? | **Gate: agreement published. If poor, no Jev marker is used** |
| M2.5 Reference estimate | Paraphrase each disclosure template 3–5 ways. Ask the vantage-point questions both ways. Combine in code into one estimate per policy, with a spread | Skim the paraphrases for any that change the meaning; open the estimate table | One marker per policy, with its spread |
| M2.6 Sweep range and freeze | Score the corpus to show the historical range of how borrowing has been read. Freeze all Jev outputs with version, date and test scores | Read the one-page method note | **Tagged `M2-complete`** |

**Two cautions for these sessions.**

- Jev never sees the simulation, and the simulation never calls Jev. The only link is the frozen file M2.6 produces.
- In M2.5, remove any paraphrase that changes what is disclosed. A paraphrase changes the wording, never the facts.

## M3 — Comparison (weeks 7–8)

M3 is the first time any policy is compared under stress. It starts only after both the M1 and M2 gates are passed. From here on, results are reported as they come out. A bug fix is allowed only if it is a mechanical error with a new test that proves it, logged in `docs/amendments.md`.

| Session | Goal | You check | Done when |
| --- | --- | --- | --- |
| M3.1 Run the grid | Bring in the frozen Jev file. Run a 1% dry run of the full grid, then the full grid (4 policies × 2 scenarios × 30 banks × 35 sweep cells × 200 paired runs) plus the feature-switch runs | The dry run finishes and prints a time estimate for the full run | Full run complete, stamped with versions |
| M3.2 Scorecard | Compute each metric as a paired difference with a 90% interval. Apply the contract's lead / tie / trade-off rule | Pick one cell and ask "explain this cell in plain English" | Scorecard CSV and HTML table |
| M3.3 Trade-off chart | The main chart with the Jev marker, the cost frontier panel, the Option C panel, and reversal distances | Can you write one plain sentence for each panel? | Charts open in a browser |
| M3.4 Feature attribution | What each switch contributes: prepositioning mandate, testing mandate, five-day ratio, LCR credit | Does the table explain why the leading policy leads? | Attribution table |
| M3.5 Episode replays | The median run for each scenario under A, B, C and E, day by day in plain English. Jev checks every sentence against the log | Read one full replay; review every flagged sentence | All flags resolved |
| M3.6 Reproduce and compare with hypotheses | Delete all outputs and regenerate them with `make results`. Then write a memo comparing results with the pre-registered hypotheses, unedited | Outputs match; read the memo | **Tagged `M3-complete`** |

**The discipline that matters most here.** The first real results appear in M3.2. If they surprise you, ask Claude Code to explain the mechanism first. Change nothing unless the explanation reveals a genuine mechanical bug.

## M4 — Review and release (weeks 9–10)

M4 gets the results reviewed from outside and publishes them. Most of the work is yours. The gate is the outside review of the results.

| Step | Where | What happens | Your role | Done when |
| --- | --- | --- | --- | --- |
| M4.1 Review package | Cowork | Claude assembles a short package for the reviewer: the results, the hypotheses memo, what changed since pre-registration, and how to rerun everything | Send it; allow 1–2 weeks | Reviewer has everything they need |
| M4.2 Respond to review | Claude Code + Cowork | Fix any mechanical errors the reviewer finds, each through an amendment. Record every comment and response in `docs/review.md`, including those you disagree with | Decide each response | **Gate: review complete and published with responses** |
| M4.3 README and results page | Claude Code + Cowork | Rewrite the README for a fresh reader: disclosure, what it shows, its limits, how to run it in one command. Publish a results page | Read it as a skeptic would | A stranger can rerun it from the README alone |
| M4.4 Write-up and release | Cowork | A short write-up for your Substack or a policy outlet. Tag `v1.0` | Write and publish | **Released** |

## Schedule and your time

Expect about 4–5 hours a week of your time, roughly 45 hours in total, plus the reviewer's and labelers' time. The weeks are a guide; the gates matter, not the dates. If a gate slips, the next milestone waits.

| Week | Sessions | Your time | Waiting on others |
| --- | --- | --- | --- |
| 0 | S0.1, S0.2 | 1.5 h | — |
| 1 | M0.1, M0.2 | 4–5 h | — |
| 2 | M0.3, M0.4, M0.5 (send to reviewer), M1.1 | 5 h | Reviewer reading C's rules |
| 3 | M0.6 (after sign-off), M1.2, M1.3, M2.1 | 5 h | — |
| 4 | M1.4, M1.5, M1.6, M2.2, M2.3 | 6 h | Labelers start |
| 5 | M1.7, M1.8, M1.9, M1.10 | 5 h | Labelers working |
| 6 | M1.11, M2.4, M2.5, M2.6 | 5 h | — |
| 7 | M3.1, M3.2, M3.3 | 4 h | — |
| 8 | M3.4, M3.5, M3.6 | 4 h | — |
| 9 | M4.1 (send), M4.3 | 3 h | Reviewer reading results |
| 10 | M4.2, M4.4 | 4 h | — |

**Order that cannot change:**

- M0.6 (published contract) before M1.7 (policy rules), so the rules are coded from the published version.
- M1.10 (parameters frozen) before any M3 session.
- The M1 and M2 gates both passed before M3.1.

**Money:** Jev calls cost under $10 for the whole project. Claude Code runs under your existing plan. The simulation runs on your laptop at no cost.

## Warning signs

You don't need to read code to catch most problems. Watch for these signs in what Claude Code says and does, and use the matching response.

| You notice | What it may mean | What to say |
| --- | --- | --- |
| It starts on something outside the session goal | Scope drift | "Stop. Undo to the last commit and do only the session goal." |
| It edits or deletes a test to make it pass | A real error being hidden | "Explain why the test was wrong before changing it." Accept only if you follow the reason. |
| A test checks that a policy wins or loses | Breaks the core rule | "Remove it. Tests check mechanics only." |
| A number is typed straight into the code | A hidden assumption | "Move this to a config file and cite the contract." |
| Same seed, different results | Reproducibility is broken | "Fix this before anything else." |
| It proposes changing frozen values after seeing results | Tuning toward an answer | "Only through docs/amendments.md, with the reason, and only for a mechanical error." |
| Jev is asked to calculate anything | Breaks the Jev rule | "Do this in code." |
| A key or password appears in a file about to be committed | Security leak | "Stop. Remove it and check the history." Then replace the key with TypeSafe. |
| You can't follow the explanation after two tries | Too much in one step | "Split this into smaller sessions." |
| A session runs past two hours | Context has drifted | Commit what works, then start fresh. |

**Weekly check-in.** Once a week, paste that week's session summaries into Cowork and ask for a second read against the PRD and contract. It takes about 15 minutes and catches drift early.
