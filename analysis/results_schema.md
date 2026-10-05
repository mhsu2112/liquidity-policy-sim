# M3 results schema (v1.0)

The M3 report (`analysis/report/`) reads **one folder** of result files in this schema, and nothing else
from the simulation. Session M3.0 fills the folder with mock numbers (`analysis/mock_results.py` →
`outputs/mock/results/`). M3 writes real numbers to `outputs/results/` in the same schema, so the report
switches from mock to real with no layout change (Clarification 28).

`analysis/results_schema.py` checks a folder against this file: `validate(folder)` returns a list of
problems (empty means the folder is valid). The report refuses to build from an invalid folder.

The names it checks against come from the binding run plan and the bank file, never typed twice:
policies, scenarios, the 7 stigma points and 5 supervision settings from `config/run_plan.yaml`
(Clarification 14), bank types from `config/banks/archetypes.yaml`.

## Conventions

- CSV files: UTF-8, one header row, comma separated. A blank field means "not applicable" or "not available".
- Policy keys: `A, B, B_prime, C, C_prime, E` (shown as A, B, B′, C, C′, E).
- Scenario keys: `S1, S2`. Bank type keys: `svb_like, diversified_regional, regional_cat3, gsib`.
- Money: `_bn` columns in $ billions; `_m` columns in $ millions per bank per year.
- Shares are fractions (0.25 = 25%). Every interval is a 90% interval with `lo ≤ estimate ≤ hi`.
- "Paired difference" means policy minus comparator on the same banks, shocks and random draws (contract 4).

## Files

### 1. `meta.json`

| Field | Meaning |
| --- | --- |
| `schema_version` | `"1.0"` |
| `mock` | `true` for mock files. The report shows the mock banner and watermark on every page and image when true |
| `generated_at` | ISO date-time the files were written |
| `stamp.git_commit` | commit the results were produced from (`-dirty` if uncommitted changes) |
| `stamp.config_hash` | hash of the settings files used |
| `stamp.params_fingerprint` | fingerprint of `config/params_frozen.yaml` (Clarification 15) |
| `stamp.jev_estimate_version` | version of the frozen Jev estimate in `signals/frozen/`, or `"none"` |
| `stamp.jev_model` | pinned Jev model version (Clarification 27), or a note saying why there is none |
| `jev_marker.available` | `false` if M2.4's agreement test failed: no marker is drawn and reversal distances are empty |
| `jev_marker.stigma` | the marker's position on the market-stigma axis (0–1), or `null` |
| `jev_marker.label` | text drawn beside the marker (mock: `"mock marker"`) |
| `scorecard_scope` | one sentence saying which cells the scorecard pools (decided in M3.2) |
| `runs_per_cell` | paired runs per bank and cell (Clarification 14: 200) |

### 2. `scorecard.csv` — one row per policy × scenario × bank type × metric

Columns: `policy, scenario, bank_type, metric, value, diff_vs_a, diff_lo, diff_hi, n_runs`.

`value` is the policy's own level. `diff_vs_a`, `diff_lo`, `diff_hi` are the paired difference against A and its
interval; blank on A's rows and on metrics with no interval.

| Metric key | Unit | Present for | Interval |
| --- | --- | --- | --- |
| `survival_rate` | share of runs | all | yes |
| `liquidity_shortfall_bn` | $bn | all | yes |
| `support_peak_bn` | $bn (window + Home Loan Bank) | all | yes |
| `support_total_bn` | $bn | all | yes |
| `annual_cost_m` | $m per bank per year, relative to A (A = 0 by construction) | all | yes |
| `buffer_gap_pp` | reported LCR minus LCR without window credit, percentage points | C, C′ only | yes |
| `effective_stigma` | 0–1 (contract 3a) | all | yes |
| `routine_borrowing_per_quarter` | draws per bank per quarter | all | yes |
| `hesitation_gap_days` | days | all | yes |
| `false_comfort` | share of runs | all | yes |
| `needless_borrowing_bn` | $bn | S2 only | yes |
| `timing_only_upper_bound` | count of failed runs (Amendment 6; reported, not scored) | all | no |

### 3. `timing_bands.csv` — Clarification 18 item 2

Columns: `policy, scenario, bank_type, band, failures, share`. Bands: `pure timing`, `partly covered`,
`not covered`, `equity below zero` (the strings `engine/outcomes.py` writes). `share` is of that row-group's
failures; the four shares sum to 1, or are all blank when there are no failures.

### 4. `tradeoff.csv` — one row per comparison × scenario × bank type × stigma × supervision

Columns: `comparison, scenario, bank_type, stigma, supervision, label, cost_diff_m, survival_diff, survival_lo,
survival_hi, shortfall_diff_bn, shortfall_lo, shortfall_hi`.

`comparison` is `X_vs_Y`, one of: `B_vs_C, B_vs_E, C_vs_A, B_vs_A, E_vs_A, C_prime_vs_C, B_prime_vs_B`.
Differences are X minus Y. `label` is `x_leads`, `y_leads`, `tie` or `trade_off` (contract 4). In real files
the label follows from the two intervals; in mock files it is drawn at random.

### 5. `reversal.csv` — one row per comparison × scenario × bank type × supervision

Columns: `comparison, scenario, bank_type, supervision, label_at_marker, down_distance, down_label, up_distance,
up_label`. Distances are in stigma units from the marker to the nearest grid point where the label changes,
moving down or up; blank if it never changes on the grid. Header only when `jev_marker.available` is false.

### 6. `frontier.csv` — one row per policy × scenario × bank type

Columns: `policy, scenario, bank_type, cost_m, cost_lo, cost_hi, survival, survival_lo, survival_hi,
shortfall_bn, shortfall_lo, shortfall_hi`.

### 7. `option_c.csv` — one row per policy (C, C_prime) × scenario × bank type × uptake × HQLA released

Columns: `policy, scenario, bank_type, uptake, hqla_released, run, survival_diff, survival_lo, survival_hi,
cost_m`. Grid: uptake 0.50 / 0.75 / 1.00 × released 0 / 0.50 / 1.00. `run` is `true` only where the run plan
has runs (Clarification 14 item 3 sweeps one setting at a time around the defaults uptake 0.75, released 1.00,
so 5 of the 9 cells); the other rows have blank numbers.

### 8. `attribution.csv` — one row per feature × scenario × bank type × outcome

Columns: `feature, scenario, bank_type, outcome, contribution, lo, hi`. Features: `prepositioning_mandate,
testing_mandate, five_day_ratio, lcr_credit`. Outcomes: `survival_rate, liquidity_shortfall_bn`.

### 9. `replay.json` — one scenario × one policy

`{scenario, policy, bank_id, run, selection, placeholder, days: [{day, entries: [{half, actor, kind, route,
text, log_line, support_check}]}], log: [{line, text}]}`. `kind` is `saw`, `did` or `why`. `route` is an
information route from contract 3, or blank. Every `log_line` must exist in `log`. `support_check` is
`null` (not yet run), `"supported"` or `"flagged"` (M3.5's Jev check).

### 10. `hypotheses.json`

A list of `{id, parts: [{part, result, verdict}]}` for H1–H8. Parts: H3 `main`, `strong_form`; H4 `a`, `b`, `c`;
all others `main`. `verdict` is one of `pending`, `supported`, `not supported`; plus `untestable` for H8 only
(Clarification 18) and `reported` for H2 only (no directional prediction). The hypothesis text and tests are
read from `docs/hypotheses.md`, never copied here.
