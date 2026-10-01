# Amendments

Every change to `docs/contract.md` or frozen parameters after `pre-registration-v1` is recorded here.
Nothing is changed silently.

Format for each entry:

## YYYY-MM-DD — short title
- **What changed:**
- **Why:**
- **Seen results before the change?** yes / no
- **Evidence (test or reviewer comment):**

## 2026-09-30 — Clarification 1: how the 40 synthetic banks are drawn (before session M1.1) — date corrected from 2026-10-01 on 2026-09-30
- **What changed:** three implementation rules the contract left unstated. No value or range in the contract changes.
  1. **Asset shares must fit.** Securities, reserves and loans are drawn from their contract ranges. If together they exceed
     100% of assets, that bank's draw is rejected and redrawn (same seed sequence). Whatever is left is "other assets",
     which are not liquid and not eligible as collateral.
  2. **Liabilities.** Equity and short-term wholesale funding are drawn from their ranges; all remaining liabilities are
     deposits, split into insured and uninsured using the drawn uninsured share.
  3. **LCR category is assigned by bank type** (contract section 1c), not recomputed from each bank's drawn funding mix.
     The synthetic funding mix is not detailed enough to compute weighted short-term wholesale funding.
- **Why:** the contract gives ranges for each variable but not how they combine. These rules keep every drawn value
  inside its published range and keep the LCR treatment exactly as the contract states.
- **Seen results before the change?** No. No code had run.
- **Evidence:** contract section 1b ranges can sum to more than 100% for SVB-like banks (up to 115%).

## 2026-09-30 — Clarification 2: Level 1 and Level 2A split of securities (session M1.1)
- **What changed:** an implementation rule the contract left unstated. No value or range in the contract changes.
  Each bank draws its Level 1 share of securities from its section 1b range; the rest of its securities are Level 2A.
  For every archetype the two section 1b ranges mirror each other (e.g. SVB-like 30–50% and 50–70%), so the
  Level 2A share always falls inside its own published range. Securities hold no Level 2B or non-HQLA assets.
- **Why:** the contract gives both ranges but not how they combine. Owner chose this option in session M1.1.
- **Seen results before the change?** No. Decided before any bank was generated.
- **Evidence:** `tests/test_banks.py` checks every bank's Level 2A share against its section 1b range.

## 2026-09-30 — Clarification 3: LCR outflow rates and simplifications (session M1.2)
- **What changed:** implementation rules for the current-rules LCR, which contract section 7 gives only in part
  (haircuts and the 40% cap). No value or range in the contract changes. Settings live in `config/lcr.yaml`.
  1. **30-day outflow rates (12 CFR 249.32):** insured deposits 3% (§249.32(a)(1), stable retail); uninsured deposits
     40% (§249.32(h)(1)(ii), non-operational corporate, the same basis as contract Decision 2-2); short-term wholesale
     funding 100% (§249.32(h)(3), treated as unsecured from financial counterparties and maturing within 30 days).
  2. **No inflows.** Contractual inflows are set to zero. The 75% inflow cap (§249.30) is kept in the formula but has
     nothing to act on.
  3. **No peak-day add-on.** The maximum cumulative net outflow day amount (§249.30(b)) is left out: the synthetic banks
     have no maturity schedule.
  4. **Unrealized losses reduce securities to market value pro rata.** Level 1 and Level 2A holdings each lose the
     bank's same percentage.
  5. **Banks with no LCR requirement** (Category IV diversified regional) get a ratio computed on unadjusted outflows
     (factor 100%) and are marked "not required".
  6. **Mark-to-market equity** (book equity less unrealized loss) is reported for information only.
- **Why:** the LCR needs outflow rates and a treatment of losses that the contract does not state. Rates are the owner's
  proposal, checked against 12 CFR 249.32 and agreed in session M1.2.
- **Seen results before the change?** No. Agreed before any LCR was computed.
- **Evidence:** `tests/test_lcr.py` (hand-calculated example, 40% cap, calibration, pro-rata loss) and
  `outputs/lcr_worked_examples.xlsx`.

## 2026-10-01 — Clarification 4: where collateral sits under the status quo, and Home Loan Bank lending (before session M1.3)
- **What changed:** two implementation rules the contract left unstated. No value or range in the contract changes.
  1. **Collateral placement under policy A.** Each bank's eligible loans start 30% prepositioned at the Fed, 40% pledged to
     the Home Loan Bank, and 30% unpledged. The Fed and Home Loan Bank shares are each swept ±20 percentage points, with
     the unpledged share adjusting so the three add to 100%. Fed-prepositioned collateral starts untested; banks test
     voluntarily at the status-quo routine borrowing rate in contract section 3a.
  2. **Home Loan Bank lending.** The bank can borrow up to a pre-arranged line of 5% of total assets on the same day
     (swept 3%, 5%, 8%). Beyond the line, it can borrow on the next day up to 75% of the value of loans pledged to the Home
     Loan Bank [ESTIMATE]. This applies contract section 7 ("same day up to pre-arranged line; next day above it").
  3. **Policies that require prepositioning** (B, E, and C for banks that opt in) take the extra collateral from unpledged
     loans first, then from loans pledged to the Home Loan Bank, which reduces Home Loan Bank capacity one for one.
- **Why:** the waterfall needs a starting position for collateral and a Home Loan Bank rule, and the contract gives only
  the timing rule.
- **Seen results before the change?** No. Agreed by the owner before any funding calculation ran.
- **Evidence:** to be added in session M1.3 (tests of capacity and timing).

## 2026-10-01 — Clarification 5: the funding waterfall (session M1.3)
- **What changed:** implementation rules for the funding waterfall that the contract and Clarification 4 leave unstated.
  No value or range in the contract changes. Settings live in `config/funding.yaml`.
  1. **Fire-sale price impact.** Linear and cumulative within an episode: each extra dollar a bank sells loses
     λ × (market value that bank has already sold). Level 1 λ = 10 bp per $10bn (Greenwood, Landier & Thesmar 2015;
     Duarte & Eisenbach 2021); Level 2A λ = 30 bp per $10bn [ESTIMATE], agency MBS being less liquid than Treasuries.
     The price does not recover within the episode. These are starting values; contract section 7 lists fire-sale price
     impact among the parameters tuned in M1.10. The discount does not revalue securities the bank still holds.
  2. **Realized losses.** A sale realizes the unrealized loss on the amount sold (pro rata, Clarification 3) plus the
     fire-sale discount; both reduce equity.
  3. **Settlement.** Level 1 sales settle T+1 (Treasury regular-way settlement); Level 2A sales settle T+2 [ESTIMATE].
     Proceeds sit in a "sale proceeds due" asset until settled.
  4. **Bridging (speed tiers).** A payment due now is met first from sources that pay the same half-day; slower sources
     cover only what is left, and those payments are reported as late. Within each speed tier the order is reserves,
     securities sales, Home Loan Bank, discount window. As a result, when next-day sources are still short the window
     lends against Level 2A securities (next day) before they are sold (T+2).
  5. **Reserve operating floor:** 1% of total assets at the start of the episode [ESTIMATE].
  6. **Home Loan Bank capacity** (reading of Clarification 4): total advances are at most 75% of loans pledged to the
     Home Loan Bank; the pre-arranged line (5% of assets) is the same-day part of that total, not an addition to it.
     Loans pledged to the Home Loan Bank are not available at the discount window.
  7. **Treasury margin at the window:** 96% (the >5-year bucket in contract section 2b) for all Level 1 securities,
     as the banks have no maturity split. Agency MBS: 96%.
  8. **Loans not prepositioned** become usable at the window from day 11 (contract section 7: "not available within 10
     days"). Each collateral pool holds resi, CRE and C&I loans in the bank's own loan mix.
  9. **Unpaid outflows.** An outflow not yet paid stays on the balance sheet as a liability ("unpaid outflows") until
     cash arrives; the part no source can cover is reported every step as the shortfall and retried the next step.
- **Why:** the waterfall needs a price-impact rule, settlement timing and several accounting choices the contract does
  not state. Items 1, 3, 4, 5, 6, 7 and 8 were chosen by the owner in session M1.3; 2 and 9 follow from them.
- **Seen results before the change?** No. Agreed before any funding calculation ran.
- **Evidence:** `tests/test_funding.py` (order, limits, lags, hand-worked sale, balance, shortfall); also completes the
  evidence for Clarification 4.

## 2026-10-01 — Clarification 6: same-day repo of liquid securities (before session M1.3b)
- **What changed:** a funding source the waterfall lacked. No value or range in the contract changes.
  1. **Same-day private repo.** A bank can raise cash the same half-day by repo of Level 1 securities (haircut 2%) and
     agency MBS (haircut 5%) [ESTIMATE]. Repo does not realize unrealized losses; the securities stay on the balance sheet
     as encumbered and stop counting as HQLA while pledged.
  2. **Order.** Within the same-day tier, repo comes after reserves and before the Home Loan Bank line and the discount
     window. Securities sales (T+1 / T+2) remain in the next-day tier, used only for what repo cannot cover.
  3. **Rolling.** Repo is overnight and must be rolled each day. From session M1.4, repo lenders roll or refuse using the
     same confidence rule as other wholesale lenders, so access shrinks as a run deepens. Until then, repo always rolls.
  4. **Not official support.** Private repo is not counted as official support. The Fed's Standing Repo Facility is not
     modeled in v1.
- **Why:** in practice a bank can usually turn Treasuries and agency MBS into cash the same day by repo without selling
  them. Without this source the model understates how quickly liquid assets become cash, which affects every policy.
- **Seen results before the change?** No stress or policy results exist. The M1.3 demo (a mechanical test of two fixed
  outflows) showed Level 1 securities paying only the next day, which prompted this.
- **Evidence:** session M1.3b. `tests/test_funding.py`: repo comes after reserves and before the Home Loan Bank line
  (`test_repo_after_reserves_before_fhlb_line`); 2% / 5% haircuts (`test_repo_haircuts_applied`); no loss realized
  (`test_repo_realizes_no_loss`); a security is repo'd, pledged or sold only once; balance sheets balance after every step.
  `tests/test_lcr.py`: repo-encumbered securities leave HQLA. `make demo-waterfall`: SVB-01 now meets both the $10bn and
  $40bn outflows the same half-day (reserves $6.3bn; repo $13.7bn Level 1 and $30.0bn Level 2A; Home Loan Bank line
  $31m), with no late payment and no realized loss; before M1.3b, $37.8bn of the $40bn was paid a day late. Known gaps,
  left for M1.7 by the owner: securities pledged at the discount window still count as HQLA, and repo adds no LCR
  outflow (12 CFR 249.32(j)).

## 2026-10-01 — Clarification 7: same-day repo is limited to pre-arranged lines (before session M1.4)
- **What changed:** a limit on the repo source added in Clarification 6. No value or range in the contract changes.
  1. **Same-day repo lines by bank type** [ESTIMATE]: Category IV banks (SVB-like and diversified regional) 3% of total
     assets; Category III regional 10%; GSIB / large bank 20%. Each swept at 50%, 100% and 150% of its default.
  2. **Beyond the line,** further repo can be arranged for the next day, up to the bank's unencumbered Level 1 and agency
     MBS after haircuts.
  3. **Rolling** follows the confidence rule for wholesale lenders built in session M1.4 (Clarification 6, item 3).
- **Why:** the M1.3b demo showed an SVB-like bank raising $40bn by repo in one afternoon. Regional banks rely on
  pre-arranged counterparties for same-day repo, and SVB could not raise funds on that scale the same day in March 2023.
- **Seen results before the change?** Only the M1.3b mechanical demo (two fixed outflows for two banks). No stress
  scenario, behavior or policy result exists.
- **Evidence:** session M1.4. Lines live in `config/funding.yaml`; next-day repo beyond the line comes before sales in
  the next-day tier (Clarification 6 item 2). `tests/test_agents.py::test_repo_lines_respected` (same-day repo never
  above the line; none from refusing lenders; next-day repo arrives exactly one day later) and
  `tests/test_funding.py::test_repo_haircuts_applied` (GSIB hand bank: 40.6 the same day, the rest next day, haircuts
  unchanged). `make demo-waterfall`: SVB-01 now raises $3.5bn by same-day repo (its 3% line) instead of $43.7bn, so
  $34.3bn of the $40bn afternoon outflow is paid a day late by next-day repo, against none late after M1.3b.

## 2026-10-01 — Clarification 8: depositors and wholesale lenders (session M1.4)
- **What changed:** the behavior rules for depositors and lenders, which the contract and PRD describe only in outline
  (PRD agent table; contract section 7 names the five tuned settings). No value or range in the contract changes.
  Fixed values are in `config/agents.yaml`; the five tuned settings are in `config/behavior.yaml` as placeholders.
  1. **Fast share of uninsured deposits** [ESTIMATE, anchored to contract 1a]: SVB-like 90% (SVB lost or had queued
     ~86% of uninsured deposits within two days); diversified regional and Category III regional 40% (First Republic
     pace: ~1/3 of uninsured on its worst day, $96bn over two weeks); GSIB 15% (largely operational corporate deposits;
     Cipriani, Eisenbach & Kovner 2024, NY Fed Staff Report 1104). The rest of uninsured deposits are slow.
  2. **Confidence and withdrawals.** Each half-day, C = 1 − S × (1 + ε) × (1 + g) − c × R, held between 0 and 1.
     S is the news shock, halving every 2 days [ESTIMATE]; ε is random noise with standard deviation 10% [ESTIMATE],
     seeded, drawn up front and identical across policies, so a shock lands somewhat harder or softer from run to run
     and a bank with no shock sees no noise; g is the share of starting book equity gone on a mark-to-market basis;
     R is the share of starting uninsured deposits withdrawn over the last day; c is coordination strength (tuned).
     Unrealized losses matter only through news, as with SVB, whose losses were public for months before the run.
     Fast depositors leave at 1 − e^(−a(1−C)) of their remaining balance each half-day (a = depositor sensitivity,
     tuned); slow depositors use the same function of confidence L half-days earlier (L = slow-depositor lag, tuned);
     insured depositors leave at 5% of the fast rate [ESTIMATE]. Tipping comes from the coordination feedback
     (Goldstein & Pauzner 2005), not a hard threshold. The noise was first proposed as ±0.02 added to confidence; the
     owner changed it to scale with the news before anything ran, because additive noise drained a calm bank.
  3. **Wholesale and repo lenders.** Each morning lenders judge the bank's chance of survival; until M1.5 adds
     information routes, that judgment is the confidence C. Cut-offs are spread evenly within ±0.10 [ESTIMATE] of the
     roll threshold (tuned), so the share refusing rises from 0 to 100% as C falls through the band. Repo is overnight:
     the refused share of the whole repo book is repaid that day and its securities stop being encumbered. Unsecured
     short-term wholesale funding matures evenly, 1/30 of its starting balance a day [ESTIMATE]; the refused share of
     what matures is repaid. Refusing lenders also stop new repo (same-day and next-day) in the same proportion; the
     used part of the same-day line is not restored by repayment. Next-day repo already agreed still arrives and faces
     the decision from the following morning. The Home Loan Bank and the discount window are not affected (PRD:
     "lends first, as in 2023").
  4. **The five tuned settings are placeholders** chosen in session M1.4 before any run and not adjusted after:
     depositor sensitivity 1.0; coordination strength 1.0; slow-depositor lag 4 half-days; wholesale roll threshold
     0.6; fire-sale price impact 10 / 30 bp per $10bn (Clarification 5 starting values, moved to `config/behavior.yaml`).
     They are set only in M1.10.
- **Why:** M1.4 needs explicit behavior rules; these follow the PRD's agent table and the contract's list of tuned
  settings. Items 1, 2 and 3 were chosen by the owner in session M1.4.
- **Seen results before the change?** No stress or policy results exist. Items 1–4 were agreed before any run, except
  the noise form in item 2, changed before any run as stated. One consequence was seen in the M1.4 demo and kept by
  the owner: because insured depositors leave at 5% of the fast rate every half-day that confidence stays low, they
  lose about 13% (mild demo shock) to 18% (severe) of their balance over 10 days at the median bank (up to 20%) under
  the placeholder settings. Reported, not changed.
- **Evidence:** `tests/test_agents.py` (bigger shock drains faster; fast before slow; insured ratio; refusal band;
  refusals repaid with collateral released; repo lines; same seed, same result; balance; rows together equal rows
  alone). `make demo-run` shows SVB-01 under the mild and severe demo shocks.

## 2026-10-01 — Clarification 9: information routes, the stigma link and the supervisor's dial (session M1.5)
- **What changed:** implementation rules for contract sections 3 and 3a that the contract leaves unstated. No value or
  range in the contract changes. Settings live in `config/information.yaml`; code in `engine/information.py` and
  `agents/supervisor.py`. Observers learn anything only through a route; each route is an event at a stated half-day.
  1. **Information routes** (day 1 is a Monday; times in half-days).
     - *Fed weekly aggregate (H.4.1):* released Thursday after the close (days 4, 11, 18, 25), covering borrowing through
       Wednesday; observers act on it Friday morning. How strongly it points at the bank = 1 ÷ (1 + other borrowers that
       week), with other borrowers = r × 40 ÷ 13 (r from contract 3a; the model's 40 banks stand in for the system; 13
       weeks a quarter) [ESTIMATE]. r = 0.1 → 76%; 1.0 → 25%; 2.5 → 12%. No bank is named.
     - *Bank announcement:* mandatory once total discount window borrowing reaches 5% of starting total assets
       [ESTIMATE; the common rule-of-thumb materiality level, SEC Staff Accounting Bulletin 99], filed at the legal
       deadline of four business days (Form 8-K General Instruction B.1; Item 2.03, creation of a direct financial
       obligation). Earlier, voluntary announcements are a bank decision (M1.6).
     - *Leak:* contract 3 defaults (20% chance within the episode, 1-day lag). One random number per run, drawn up front;
       at most one leak, timed from the bank's first draw.
     - *Inference:* securities sold or funding refused; wholesale lenders learn the same half-day, depositors the next
       (contract 3: "same or next half-day"). It reveals distress signs, not borrowing. In M1.5 it is recorded and
       delivered but has no confidence effect of its own: sales already act through equity losses and refusals already
       come from low confidence.
     - *Quarterly ratio disclosure:* day 15 of the episode, for every bank with an LCR requirement (12 CFR 249.90 applies
       to every company subject to 249.1: SVB-like, Category III, GSIB). It reports the prior quarter, so it carries
       start-of-episode values and never reveals an in-episode draw. Under B it adds the five-day ratio, under C and C′
       the LCR including credit (filled in M1.7). No confidence effect in M1.5.
     - *Supervisory channel* (added; not in contract section 3): the supervisor learns of a draw the same half-day. The
       Fed is the lender, and large banks report discount window borrowing daily on FR 2052a.
     - The Fed's named disclosure (about two years later) falls outside the episode and is not modeled (contract 3).
  2. **How a known draw affects confidence** (identical for every policy; no function takes a policy name).
     Effective stigma σ_eff = σ × e^(−s × r) (contract 3a). One random number U per run, drawn up front and shared by
     every policy. A route that reveals the draw is read as distress if U < σ_eff × how revealing the route is (1 for the
     announcement and the leak; the weekly fraction above). The first distress reading adds a news shock of 0.25
     [ESTIMATE] to the confidence formula of Clarification 8, which fades with the same 2-day half-life and is
     amplified by mark-to-market losses in the same way. It happens once per episode; later routes revealing the same
     fact add nothing. Depositors and lenders read the same public news, so they share one confidence number. The size
     0.25 is fixed, not tuned (contract 7 allows only five tuned settings). Default s = 0.3, the middle of the contract 5
     grid, which gives no default.
  3. **Supervisor's five-level dial.** Supervisory and internal cost of borrowing, in units of the bank's loss if it
     fails [ESTIMATE / owner's call; no hard data]: strongly penalizes 0.30, penalizes 0.15, neutral 0.05 (board and
     management reluctance remain), encourages 0.02, strongly encourages 0. Effective cost = level cost × e^(−s × r),
     with the same s as market stigma (contract 3a). No negative costs. In M1.5 the supervisor sets this cost and learns
     of draws; it takes no action inside the episode. The cost is used by the borrowing decision in M1.6.
  4. **Routine borrowing rates** (contract 3a, copied into config): A and C′ 0.1; B and E 1.0; C uptake × 2.5.
  5. **Forced draw for demonstrations.** `engine/funding.py::force_dw_draw` lets the demo and tests make the bank
     borrow (fastest window collateral first). It holds no decision logic and is replaced by M1.6's rule.
- **Why:** M1.5 needs explicit routes, a link from a known draw to confidence, and numbers for the supervisor's dial,
  none of which the contract specifies beyond section 3's table and section 3a's formula. Items 1–3 were proposed in
  session M1.5 and approved by the owner before any code ran.
- **Seen results before the change?** No stress or policy results exist. Agreed before any run. One consequence was
  seen in the demo and is reported, not changed: under the M1.10 placeholder settings a single distress reading
  (news of 0.25) on an otherwise calm SVB-like bank drains about 99% of its uninsured deposits within 16 days.
- **Evidence:** `tests/test_information.py` (no information without a route; knowledge changes only with an event; leak
  probability over 100,000 runs and exact lags of 0, 1 and 5 days; weekly report less revealing as r rises, and its
  timing; announcement only above the threshold, four days later; contract 3a formulas for stigma and supervisory
  cost; no function in the link takes a policy; equal r gives equal readings across policies (static); one distress
  reading at most; inference timing; disclosure day and banks; same seed, same result; rows together equal rows alone).
  `make demo-info` shows SVB-01 at r = 0.1 and r = 2.5.

## 2026-10-01 — Amendment 1: sweep the size of the distress reading (before session M1.6)
- **What changed:** contract section 5 gains one swept assumption. The confidence hit applied when a known discount
  window draw is read as distress (Clarification 9; default 0.25) is swept over **0.10, 0.25 and 0.40**. The default
  stays 0.25. It runs on the coarser grid around the defaults, like the other non-main sweeps.
- **Why:** this single fixed number sets how strongly the stigma channel acts for every policy, and so how much routine
  borrowing (B and E's tests, C's usage draws) can help. Results will report whether any conclusion changes across the
  three sizes, so the comparison does not rest on one estimate.
- **Seen results before the change?** No stress or policy results exist. The M1.5 demo (a forced draw under policy A
  with placeholder settings) showed that one distress reading drains almost all of an SVB-like bank's uninsured
  deposits, which prompted the check.
- **Evidence:** session M1.6. `config/information.yaml` → `market_stigma.distress_news_shock_grid: [0.10, 0.25, 0.40]`,
  with a comment citing this amendment; the default `distress_news_shock` stays 0.25. `start_episode(distress_shock=...)`
  sets it per row for the sweep. `tests/test_decision.py::test_amendment_1_grid_in_config`. Through Clarification 10
  item 2, the same number also sets the bank's own price of a distress reading, so the sweep covers both.

## 2026-10-01 — Clarification 10: the borrowing decision, the discount window and end conditions (session M1.6)
- **What changed:** implementation rules for the PRD's borrowing rule and contract sections 3a and 7 that neither
  states in full. No value or range in the contract changes. Settings in `config/decision.yaml`; code in
  `agents/bank.py`, `engine/episode.py` and `engine/outcomes.py`. The rule is the same function with the same inputs
  for every policy; no function in it takes a policy name.
  1. **The rule** (PRD, "How stigma enters the model"), applied each half-day once today's withdrawals and refusals
     are known: borrow if P(fail without the window) > P(known) x P(read as distress) x L + supervisory cost. Every
     term is in units of the bank's loss if it fails (= 1), the unit of the supervisor's dial (Clarification 9 item 3).
     - *L, the loss from a distress reading,* equals h, the confidence hit a reading causes (0.25; swept 0.10 / 0.25 /
       0.40 by Amendment 1). Confidence runs from 1 (calm) to 0 (full panic, what failure looks like), so the bank
       prices a reading at h of a failure. Owner's choice in session M1.6; it adds no new number.
     - *P(read as distress)* = effective stigma (contract 3a). *P(known)* comes only from the M1.5 routes: 1 if total
       borrowing would reach the 5% materiality line (the 8-K); otherwise, for a first draw, leak chance + (1 − leak
       chance) x the weekly report's revealing share; otherwise 0 (the first draw already set those routes off). Once
       the market reads the bank as distressed the term is 0 (one reading per episode). The bank never sees its own
       random number.
     - *Supervisory cost:* the effective dial cost from Clarification 9 item 3, unchanged.
  2. **How the bank projects its shortfall** [ESTIMATE]. Over this half-day and the next three (two days), it assumes
     each coming half-day loses as much as the larger of this half-day and the last. It counts only cash that can
     arrive in time without the window: reserves above the floor, repo (the better of repo and sale for each class of
     securities; same-day repo within the line), the Home Loan Bank and cash already on its way, each only if its lag is
     within reach. These are the waterfall's own capacity functions. The projected gap is the largest shortfall of
     cash against cumulative outflows. P(fail without the window) treats future outflows as uncertain by ±50% (one
     standard deviation, the same error for every half-day; anchored on SVB's ~$42bn on 9 March against ~$100bn queued
     for 10 March); it is 1 if today's payments alone can't be met on time.
  3. **What "borrow" means.** The window opens to the waterfall that half-day, after private sources as before. The
     bank then asks for the rest of its gap ahead of need, sized at outflows one standard deviation above its central
     projection [ESTIMATE], using the window's fastest collateral first. When the rule says wait, every window source
     counts as empty.
  4. **The window.** It lends post-margin collateral with contract 7's lags (code from M1.3). Whether collateral was
     tested in the last 90 days is drawn up front for each bank: tested if U_test < 1 − e^(−r), with r the policy's
     routine borrowing rate (draws at random over time; at A's r = 0.1 the chance is 9.5%). U_test is one random number
     per bank, from its own stream, shared by every policy, so a bank tested at a low r is tested at any higher r.
  5. **Same-half-day sources pay first.** A payment due now is met first from sources that pay the same half-day, even
     if cash is already on its way; only slower sources net off cash on its way. This restates Clarification 5 item 4,
     which the M1.3 code applied only when nothing was on its way. Found in M1.6 when cash asked for ahead stopped the
     bank from using its reserves; all M1.3 tests pass unchanged.
  6. **Failure** (strict, owner's choice in session M1.6): at the end of a half-day, more than 0.1% of starting total
     assets still owed (including payments waiting for next-day cash: the depositors' wires did not go out), or book
     equity after realized losses below zero. The tolerance sits below SVB's negative Fed balance of about $958m (~0.5%
     of assets) at the close on 9 March 2023, which was enough to close it (California DFPI order, 10 March 2023).
  7. **Stabilization:** three straight days (6 half-days) in which outflows are below 0.1% of starting assets, nothing is
     owed, confidence is no lower than three days earlier, and no news of the bank's borrowing is still on its way
     [ESTIMATE]. A bank with no shock stabilizes on day 3. **Otherwise** the episode ends on its last day (day 30).
  8. **Outputs per episode,** read at the end half-day (rows that have ended keep being computed with the others, but
     nothing after the end counts): end state and day; the hesitation gap (first half-day the central projection showed
     a gap above the failure tolerance, against the first half-day the window lent; negative if the bank borrowed before
     the central projection showed a gap); the shortfall (largest amount still owed at the end of a half-day, and the
     part no source could cover); official support drawn (discount window lending agreed by the end, including cash on
     its way); effective stigma. **Home Loan Bank advances are reported separately and not counted as official support.**
  9. **Random numbers up front.** Every run that is not a demo must supply its random numbers (`draw_info_randoms`:
     leak, reading and testing); a run without them raises an error.
- **Why:** the PRD gives the rule's form but not how its inputs are measured; the contract gives the window's lags but
  not how readiness is drawn or when an episode ends. Items 1 (L), 6 and the projection method were proposed in session
  M1.6 and approved by the owner before any code ran; item 5 is a mechanical correction found while building.
- **Seen results before the change?** No stress or policy results exist. Agreed before any run, except item 5
  (mechanical, found in the first test run). Seen in the M1.6 demo and reported, not changed: under the M1.10 placeholder
  behavior settings and the strict test, most of the 40 banks fail within days even under a 0.05 news shock, because the
  placeholder depositor settings drain uninsured deposits steadily (as in M1.4). The same happens with every information
  route switched off, so it does not come from the borrowing rule. SVB-01 borrows on the first half-day its projection
  shows a gap at every stigma and supervisory setting tried, because its gap is certain at once; for slower runs (e.g.
  DIV-01), high stigma or a penalizing supervisor delays the first draw by a half-day.
- **Evidence:** `tests/test_decision.py`: higher stigma or supervisory cost never makes any of the 40 banks borrow
  sooner (full stigma grid x five dial levels, three shocks); window closed when the rule says wait; normal curve and
  P(fail) by hand; P(known) by route; no policy in the rule; window cash arrives with the contract lag by source,
  tested and untested; tested share ≈ 1 − e^(−r) over 100,000 draws and nested across r; each end condition (owed above
  and below tolerance, negative equity, six calm half-days, pending 8-K, falling confidence, last day); nothing after
  the end counts; no random numbers → error; same seed, same result; balance sheets balance every half-day; rows
  together equal rows alone. Set-up of the M1.4 and M1.5 tests now supplies its random numbers explicitly (no assertion
  changed). `make demo-episode`.

## 2026-10-01 — Amendment 2: depositors tolerate small drops in confidence (before tuning, session M1.6b)
- **What changed:** the depositor withdrawal rule in Clarification 8, item 2, gains a tolerance level θ. Fast depositors
  now leave at 1 − e^(−a × max(0, θ − C)) of their remaining balance each half-day, instead of 1 − e^(−a × (1 − C)).
  Slow depositors use the same rule with their lag; insured depositors still leave at 5% of the fast rate. With
  confidence above θ, nobody withdraws.
- **Tuning:** θ is part of "depositor sensitivity", one of the five settings contract section 7 lists as tuned in
  M1.10. It is tuned together with a, and only in M1.10. Placeholder: θ = 0.9, marked "PLACEHOLDER: set only in M1.10".
  No new tuned setting is created.
- **Applies identically to every policy.** No part of the rule depends on which policy is running.
- **Why:** under the M1.4 rule, any confidence below 100% drains deposits every half-day until confidence recovers, so a
  sound bank facing a small rumor bleeds deposits indefinitely. Tuning would then have to trade the SVB-like run speed
  against false-alarm survival (validation M1.11) with no way to satisfy both. A tolerance level is the standard way
  to separate ordinary worry from a run.
- **Seen results before the change?** No tuning and no policy results exist. The M1.6 mechanical demo (policy A,
  placeholder settings) showed nearly every bank failing under a tiny 0.05 shock, which prompted the check.
- **Evidence:** session M1.6b. `config/behavior.yaml` → `depositor_sensitivity.tolerance_theta.value: 0.9`, marked
  "PLACEHOLDER: set only in M1.10" and citing this amendment; rule in `agents/depositors.py::leave_share`.
  `tests/test_agents.py`: nobody withdraws at or above θ (function and episode); withdrawals rise strictly as confidence
  falls below θ and match the formula by hand; no policy in the rule; same seed, same result; balance sheets balance.
  One M1.6 test guard changed with the owner's approval: `test_higher_costs_never_borrow_sooner` still checks
  monotonicity at all three shocks, but its "some bank borrows" guard now applies only at 0.15 and 0.40, because no bank
  borrows at 0.05 under θ. Mechanical runs (policy A, placeholders, stigma 0.35, neutral supervision, seed 20261001),
  reported, not results: under a 0.05 shock 0 of 40 banks fail (all stabilize, none borrow; SVB-01 stabilizes day 6);
  under a 0.5 shock 39 of 40 fail (all SVB-like on day 1; diversified and Category III regionals days 1–3; 9 of 10
  GSIBs days 3–4). `make demo-episode` rerun.

## 2026-10-01 — Clarification 11: building the policies from their switches (session M1.7)
- **What changed:** implementation rules for contract sections 2a, 2c, 2d and 3a that the contract leaves unstated. No
  value or range in the contract changes. Settings in `config/policies/policies.yaml`; code in `engine/policies.py`,
  `engine/collateral.py`, `engine/five_day.py` and `engine/lcr_credit.py`.
  1. **HQLA released under C** (owner's choice): reserves first, down to the 1% operating floor (Clarification 5), then
     Level 1, then Level 2A. Securities released are sold at market value and realize their unrealized loss
     (Clarification 5 item 2), with no fire-sale discount (a gradual steady-state choice). The cash goes into new loans
     at the bank's loan mix and eligible share, not prepositioned. The amount is sized on ordinary-course credit
     (stress trigger off).
  2. **B's extra reserves** (owner's choice): funded by running off loans not eligible as collateral, at the bank's mix;
     total assets unchanged. If those run out, loans at the Fed are converted, each $1 netting (1 − lendable value per
     $1). If a bank still falls short once every loan is reserves, the remaining gap is reported
     (`b_gap_left_after_all_loans_bn`) and its ratio stays below 100%. This happens only under the full-run sensitivity
     (SVB-04, SVB-08, SVB-09; ratios 97.7%, 92.9%, 98.5%); how B treats such a bank is left open for the owner.
  3. **Collateral for B and E, cheapest first** (owner's choice: the contract 2c rule priced by contract 6): securities
     (2bp) before loans (15–20bp); Level 2A before Level 1 (same cost and 96% margin; Level 1 is kept free for same-day
     repo); then loans in Clarification 4 order (unpledged, then Home Loan Bank-pledged, reducing Home Loan Bank capacity
     one for one), each pool at the bank's loan mix. Securities are valued at market value × margin and stay HQLA
     (contract 2d). The 30% of eligible loans already at the Fed under A counts first. E prepositions exactly B's
     collateral and holds no extra reserves.
  4. **Credit only for banks that opt in** (owner's choice), under both C and C′. Opt-in is drawn once per bank from its
     own random stream (third child of the seed), opting in if U < uptake, so the same banks opt in under C and C′ and the
     sets are nested across uptake levels. Banks with no LCR never opt in.
  5. **Total net cash outflows** for the ceiling are the calibrated amount (×70% / ×85% for reduced-LCR banks), as
     12 CFR 249 defines them for those banks.
  6. **Opt-in prepositioning:** loans only (securities earn no credit), in Clarification 4 order, until loan capacity
     reaches 30% of net cash outflows, or every eligible loan if less.
  7. **Usage draws (C only):** five equal overnight draws every six months, each = target credit ÷ k, where target credit
     = min(30% × net cash outflows, loan capacity). Then k × average(1st, 3rd, 5th) = target, so the usage limit never
     stops the stress raise to 30%. C′ makes none.
  8. **Tested status:** B, E and opted-in C banks are tested. A, C′ and C banks that do not opt in are drawn as in
     Clarification 10 item 4 at the voluntary rate (A's 0.1). The system routine rate r stays as in contract 3a.
  9. **Buffer gap** = reported LCR − LCR without credit (PRD metrics table). **Credit after a stress draw** =
     max(0, credit − amount drawn).
  10. **Not yet wired into the episode:** the starting positions are static. Feeding them into a stress run (including
      a window source for prepositioned securities), and the two M1.3b gaps (securities encumbered at the window still
      in HQLA; no LCR outflow for repo), are left for a later session.
- **Why:** the contract fixes the switches and formulas but not which HQLA is released, how extra reserves are funded,
  which collateral counts as cheapest, or who may claim credit under C′. Items 1–4 were chosen by the owner in session
  M1.7 before any code ran; items 5–9 were stated in the approved plan.
- **Seen results before the change?** No stress or policy results exist; no stress episode ran. Only static
  calculations (allowed before M3): a check of each bank's five-day ratio and credit size informed the options shown to
  the owner. Seen in the static table and reported, not changed: under B every bank meets the ratio with securities alone
  (39 of 40 need some; 10 also use Level 1 after their
  Level 2A); none needs loans or extra reserves. Under C, 21 of 30 LCR banks opt in; one
  (SVB-09; corrected 2026-10-02 in session M1.8, first recorded as SVB-08 in error) releases some Level 1 ($0.76bn)
  because its reserves above the floor are smaller than its credit.
- **Evidence:** `tests/test_policies.py` (42 checks): switches match contract 2a; C never credits securities at the Fed;
  credit never above any limit (C and C′, trigger on/off, three uptakes, three multiples); no-LCR banks get no credit;
  C′ has no draws and A's rate and tested status; B's ratio ≥ 100% (and the least that passes); full-run sensitivity;
  B, C and a loss-realizing release worked by hand; E's collateral equals B's; same seed, same table; balance sheets
  balance under every policy. `make policy-table` → `outputs/policy_table.csv`.

## 2026-10-01 — Amendment 3: add named variant B′ (loan collateral only); non-compliant banks under B (before session M1.7b)
- **What changed:**
  1. **B stays exactly as registered.** A new named variant **B′** is added and reported alongside it. B′ uses B's
     five-day ratio, but only post-haircut capacity against **loans** prepositioned at the Fed counts toward it.
     Securities already count as liquid assets, so they do not count again, mirroring Option C's eligibility rule
     (contract 2d). Under B′ banks preposition loans cheapest first by contract section 6 rates (C&I, then residential
     and CRE), in Clarification 4 order (unpledged, then Home Loan Bank-pledged), then hold extra reserves funded as in
     Clarification 11 item 2. Quarterly $50m tests; tested; routine borrowing rate 1.0. E is unchanged (it mirrors
     registered B's collateral), so B′ has no matching mandate-only variant in v1.
  2. **Banks that cannot meet B's or B′'s ratio** even after converting every loan run **non-compliant**: they operate
     below 100% with the remaining gap reported and flagged in every output where it occurs. Under the registered
     settings no bank is non-compliant under B; three SVB-like banks are under the full-run sensitivity.
  3. Policies compared in v1 become A, B, B′, C, C′ and E.
- **Why:** under the registered cheapest-first rule, every bank meets B with securities that could already raise cash by
  same-day repo, so B never mobilizes loan collateral while C does. B′ shows what B would do if it mobilized loans, so
  a difference between B and C is not driven by the cost rule alone. The sponsor proposed a version of B; keeping B as
  registered and adding B′ as a labelled variant avoids redefining the sponsor's own option after seeing how it is met.
- **Seen results before the change?** No stress or policy-performance result exists. The M1.7 static policy table
  (who prepositions what, ratios and credit sizes; no stress run) showed B met entirely by securities, which prompted
  this.
- **Hypotheses:** none is pre-registered for B′. Any B′ result is reported as exploratory.
- **Evidence:** session M1.7b (rules in Clarification 12). `config/policies/policies.yaml` → `B_prime` (B's switches;
  `five_day_counts: loans_only`; C&I first, then residential and CRE together, each unpledged then Home Loan Bank);
  `config/information.yaml` → `B_prime: 1.0`. `tests/test_policies.py`: B′ counts loans only (moving every security to
  the Fed leaves its ratio unchanged), moves no securities, follows the loan order, is tested at rate 1.0 with quarterly
  tests, and passes unless flagged; B and B′ non-compliant banks are flagged with the exact gap under the full-run
  sensitivity; no bank is non-compliant under registered B. `make policy-table` adds B′ rows and a `b_non_compliant`
  column (240 rows); episode outcomes carry `non_compliant` and `five_day_gap_bn`. Static, reported, not results: under
  B′ all 10 SVB-like banks hold extra reserves after prepositioning every eligible loan (SVB-03 also turns some of its
  loans at the Fed into reserves); no bank is non-compliant at the registered settings. Under the full-run sensitivity
  B has 3 non-compliant banks (SVB-04, -08, -09) and B′ has all 10 SVB-like banks (ratios 46–64%).

## 2026-10-01 — Clarification 12: B′ and connecting the policies to the episode (session M1.7b)
- **What changed:** implementation rules for Amendment 3 and for running episodes from each policy's setup (closes
  Clarification 11 item 10). No value or range in the contract changes. Code in `engine/policies.py`,
  `engine/collateral.py`, `engine/five_day.py`, `engine/funding.py`, `engine/episode.py`, `engine/lcr.py`,
  `engine/lcr_credit.py`, `engine/outcomes.py`.
  1. **B′ loan order** (owner's choice): type first, then pool. C&I unpledged → C&I at the Home Loan Bank → residential
     and CRE unpledged → residential and CRE at the Home Loan Bank. Residential and CRE (both 20bp, contract 6) move
     together, the same share of each holding. Loans are now tracked by type in every pool; B, E and C still move loans
     at the bank's own mix, so their M1.7 figures are unchanged.
  2. **Non-compliance** (Amendment 3 item 2): flag `non_compliant` and the gap left (`five_day_gap_bn`), in the policy
     table and episode outcomes.
  3. **Episodes start from the setup:** balance sheet (released HQLA, extra reserves), collateral at the Fed, tested
     status, routine borrowing rate and C's credit. Without a setup, the episode builds policy A through the same setup
     builder; every policy-A result is identical to before (all earlier tests pass, and `make demo-episode` output is
     unchanged apart from four added columns). If a caller sets r by hand (demos, tests), tested status is drawn from
     that r as in Clarification 10 item 4.
  4. **Window on prepositioned securities:** two same-half-day sources, tested prepositioned Level 1 then Level 2A,
     placed after the window on tested loans (owner's choice), open only to tested banks. Capacity is the lower of the
     prepositioned value not yet borrowed against and the securities not yet sold, repo'd or pledged, × 96%, so repo and
     sales use securities that are not prepositioned first. Untested prepositioned securities use the existing next-day
     window source (contract 7). The bank's ahead-of-need request uses the same fastest-first order.
  5. **HQLA:** securities the window has lent against leave HQLA, as repo'd securities already did. Prepositioned
     securities not borrowed against stay HQLA (contract 2d).
  6. **Repo outflow in the LCR:** 0% for repo against Level 1 and 15% against Level 2A (12 CFR 249.32(j)(1)(i)–(ii)),
     in `config/lcr.yaml`. **Open item:** discount window loans add no LCR outflow in v1 (owner's choice). Contract 2d says
     existing treatment applies, but its rate was not confirmed in this session. Nothing in the episode reads the
     in-episode LCR, so this affects reporting only.
  7. **C's credit in the episode:** starts at the setup's credit, with the 30% ceiling when the stress-trigger switch is
     on (it fires on day 1); release stays sized on ordinary credit. After each half-day, credit = max(0, starting credit
     − total window borrowing). Reported LCR = (HQLA + credit left) ÷ calibrated outflows (`lcr_credit.reported_lcr`).
     The day-15 disclosure (Clarification 9) carries the starting reported LCR, credit included, and the five-day ratio;
     still no confidence effect.
  8. **Only the setup builder takes a policy name.** `routine_rate` moved from `engine/information.py` to
     `engine/policies.py`. A check over `engine/` and `agents/` enforces that no other function takes a policy name,
     compares to one, or passes one to anything but `policy_setup`.
  9. **Test changes approved by the owner (Rule 4):** `tests/test_information.py` imports `routine_rate` from its new
     place (no assertion changed); `tests/test_funding.py::test_lags_match_contract` gains the two new sources at lag 0
     (no existing entry changed); `tests/test_policies.py` covers six policies (240 table rows) and B′'s switches.
- **Why:** Amendment 3 adds B′ and non-compliance; policies must run through the same engine before M3, and the two
  M1.3b gaps (window-encumbered securities in HQLA, no repo outflow) had to close before any LCR is reported mid-episode.
- **Seen results before the change?** No stress or policy-performance results exist. No episode ran under any policy
  but A beyond a single waterfall step with a forced withdrawal and no behavior, or one episode step with no shock;
  no outcome was printed or compared. Items 1, 4 and 6 were chosen by the owner before any code ran.
- **Evidence:** `tests/test_wiring.py`: every policy's starting episode matches its policy-table row; balance sheets
  balance at the start and after one step under every policy; tested prepositioned securities pay the same half-day,
  only after tested loans are used; untested ones wait a day; window-pledged securities leave HQLA and unused ones stay;
  repo outflows of 0% / 15%; the trigger lifts C's ceiling to 30% (setup and episode start); credit falls one for one
  with a forced draw; the disclosed LCR includes credit; no policy name outside the setup builder (AST check).
  `make test` (189 checks); `make policy-table` (240 rows).

## 2026-10-02 — Amendment 4: LCR outflow on discount window loans secured by loans (before session M1.8)
- **What changed:** resolves Clarification 12 item 6 and adds one reporting sensitivity to contract section 5.
  1. A discount window loan is a secured funding transaction (12 CFR 249.3), and the Fed is a "sovereign entity"
     (249.3: "a central government … or an agency, department, ministry, or central bank of a central government").
  2. **Default:** discount window loans secured by Level 1 collateral carry a 0% outflow and by Level 2A a 15% outflow
     (249.32(j)(1)(i)–(ii)); loans secured by non-HQLA collateral (loans) carry a **25%** outflow, reading
     249.32(j)(1)(iii) ("secured funding transactions with sovereign entities …") as covering the Fed.
  3. **Sensitivity:** 0% (the Basel treatment of secured funding from the domestic central bank) and 100%
     (249.32(j)(1)(vi), non-HQLA collateral, if the 20% risk-weight condition in (j)(1)(iii) is read as excluding the Fed).
- **Scope:** affects only the reported LCR during an episode, and so the false-comfort metric (hypothesis H5) and the
  buffer gap. It does not change any bank's cash, funding sources or survival.
- **Why:** the reported LCR during stress needs an outflow rate for discount window borrowing, and the rule's wording
  is ambiguous for central bank counterparties.
- **Seen results before the change?** No stress or policy results exist.
- **Evidence:** session M1.8. Window loans are booked by the collateral behind them (`dw_out_level1_bn`,
  `dw_out_level2a_bn`, `dw_out_loans_bn` in `engine/funding.py`); `engine/lcr.py` adds their outflows;
  `config/lcr.yaml` → `dw_level1: 0.00`, `dw_level2a: 0.15`, `dw_loans: 0.25`, `dw_loans_grid: [0.00, 0.25, 1.00]`,
  citing this amendment. `tests/test_wiring.py`: `test_window_loan_outflow_rates_by_collateral` (0% / 15% / 25% by
  hand, and every grid point) and `test_window_loans_by_collateral_add_up` (the three lines add up to window loans after
  a waterfall step and a forced draw; balance sheets balance). Reporting only: `make demo-episode` output (policy A) is
  identical to session M1.7b's.

## 2026-10-02 — Clarification 13: the cost model (session M1.8)
- **What changed:** implementation rules for contract section 6 that the contract leaves unstated. No value or range in
  the contract changes. Settings in `config/costs.yaml`; code in `engine/costs.py`, `engine/write_costs.py`,
  `engine/cost_workbook.py`.
  1. **Relative to A.** Every cost is the policy's annual cost minus policy A's, in $m, so A costs zero by
     construction. A's own voluntary tests (rate 0.1 a quarter) are not subtracted from B, B′ and E's four tests
     (owner's choice; about $55 a year).
  2. **Prepositioning:** (collateral at the Fed under the policy − under A), by type, × the contract 6 rate. Loans are
     at face value, securities at market value (owner's choice). Negative where a policy leaves less at the Fed than
     A (owner's choice): only SVB-03 under B′, which turns some prepositioned loans into reserves (−$2.5m a year).
     The contract 5 rate multiple (×0.5 / ×1 / ×1.5) is in config at ×1 and isn't swept in M1.8's output.
  3. **Draws:** primary credit rate − interest on reserve balances = **10 bp** (as of 2026-09-17; Federal Reserve
     implementation note of 2026-09-16; figure supplied by the owner in session M1.8 and not independently checked
     here), × size × 1/360 (actual/360, owner's choice) × draws a year. B, B′ and E: four $50m tests. C banks that opt in:
     ten usage draws a year at the Clarification 11 item 7 size. C′ and every other bank: none.
  4. **Extra reserves** (B, B′) and **released HQLA** (C, C′ banks that opt in) at the loan-to-reserve spread. Release
     is measured at the amount released (reserves, plus securities at market value) and counts as a negative cost.
  5. **One-time loss:** the unrealized loss realized when securities are released (book equity under A minus under the
     policy) is reported in its own column, never in the annual cost.
  6. **Spread sweep** (contract 6: 200 / 250 / 300 bp) moves only the extra-reserves and released-HQLA components;
     `costs.csv` shows the annual total at each point.
  7. **Worked examples:** the first SVB-like bank and the first GSIB that opt in under C (SVB-09, GSIB-02), so every
     component appears, each under B, B′ and C.
- **Why:** the contract gives rates but not the base they apply to, the day count, how a position below A's is
  treated, or whether A's voluntary tests are netted. Items 1–3 were chosen by the owner in session M1.8 before any
  code ran.
- **Seen results before the change?** No stress or policy-performance results exist. One static fact informed the
  question asked in item 2 (SVB-03 under B′ ends with less at the Fed than under A). No ranking or summary across
  policies was produced.
- **Evidence:** `tests/test_costs.py`: A's every component is zero; a $50m test by hand; B and E prepositioning
  identical; banks that don't opt in under C and C′ cost nothing; C′ has no draw cost and C's draws match by hand;
  the spread sweep scales extra reserves and release by 0.8 / 1.2 and leaves the rest unchanged; the annual total is
  the sum and excludes the one-time loss; same seed, same table (240 rows); every cost formula in
  `outputs/cost_worked_example.xlsx` (SVB-09 and GSIB-02 under B, B′ and C), worked by pycel, matches the code.
  `make costs`.
