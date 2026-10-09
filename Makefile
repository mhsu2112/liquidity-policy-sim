# One-word commands for this project. Type `make test` in this folder.
#
# The Python environment lives in .venv/ (never saved to history). It is
# built from requirements.txt the first time any command needs it.

# Python 3.11 or later is required (see CLAUDE.md); 3.13 is used here.
PYTHON_FOR_SETUP ?= python3.13
VENV := .venv
PY := $(VENV)/bin/python

.PHONY: setup test banks lcr demo-waterfall demo-run demo-info demo-episode policy-table costs benchmark tune validate timing-gap corpus corpus-build corpus-sample corpus-check-sheet gold-draw gold-sheets lock-labels compare-practice publish-labels jev-hello mock-report report m3-dry results ai-labels gold-check markers corpus-scores freeze

# Build the environment only when it is missing or requirements.txt changed.
$(VENV)/.installed: requirements.txt
	$(PYTHON_FOR_SETUP) -m venv $(VENV)
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r requirements.txt
	touch $@

## make setup: build the Python environment (needed once per computer)
setup: $(VENV)/.installed

## make test: run every automated check in tests/
test: $(VENV)/.installed
	$(PY) -m pytest tests/ -v

## make banks: draw the 40 synthetic banks and write outputs/banks.csv
banks: $(VENV)/.installed
	$(PY) -m engine.write_banks

## make lcr: each bank's LCR and its parts, plus the worked-examples spreadsheet
lcr: $(VENV)/.installed
	$(PY) -m engine.write_lcr

## make demo-waterfall: plain-English account of two banks meeting a $10bn then $40bn outflow
demo-waterfall: $(VENV)/.installed
	$(PY) -m engine.demo_waterfall

## make demo-run: SVB-01 under a mild and a severe news shock, half-day by half-day (policy A)
demo-run: $(VENV)/.installed
	$(PY) -m engine.demo_run

## make demo-info: who learns of a forced SVB-01 draw, through which route, and when (policy A; r = 0.1 vs 2.5)
demo-info: $(VENV)/.installed
	$(PY) -m engine.demo_info

## make demo-episode: one full SVB-01 episode in plain English, plus a stigma x supervision table (policy A; mechanics only)
demo-episode: $(VENV)/.installed
	$(PY) -m engine.demo_episode

## make policy-table: each bank's starting position under A, B, B', C, C' and E (static; no stress runs)
policy-table: $(VENV)/.installed
	$(PY) -m engine.write_policy_table

## make costs: each policy's annual cost per bank relative to A, plus a worked-example spreadsheet (static)
costs: $(VENV)/.installed
	$(PY) -m engine.write_costs

## make benchmark: time 10,000 policy-A episodes, check same seed = same result, and count the M3 run plan
benchmark: $(VENV)/.installed
	$(PY) -m engine.benchmark

## make tune: tune the five behavioral settings on the SVB validation bank (policy A, S1 only), and write the report
tune: $(VENV)/.installed
	$(PY) -m validation.tune
	$(PY) -m validation.tuning_report

## make validate: the four out-of-sample checks of Clarification 16 (policy A only), and the validation report
validate: $(VENV)/.installed
	$(PY) -m validation.checks
	$(PY) -m validation.validation_report

## make timing-gap: how often policy-A failures come from funding agreed but arriving next day; static exposure for every policy
timing-gap: $(VENV)/.installed
	$(PY) -m analysis.timing_gap
	$(PY) -m analysis.timing_exposure

## make corpus: collect the calibration corpus from public sources (needs the internet and the keys in .env; takes hours; resumable)
corpus: $(VENV)/.installed
	$(PY) -m signals.corpus.collect_fed
	$(PY) -m signals.corpus.collect_other_cb
	$(PY) -m signals.corpus.collect_edgar
	$(PY) -m signals.corpus.collect_news_api
	caffeinate -i $(PY) -m signals.corpus.extract
	$(PY) -m signals.corpus.review --batches 60
	@echo "Next: review the batches in signals/corpus/work/review_batches/ (Clarification 21), then make corpus-build"

## make corpus-build: keep reviewed-eligible passages, remove duplicates, apply the per-document and filing caps (no internet)
corpus-build: $(VENV)/.installed
	$(PY) -m signals.corpus.build_corpus

## make corpus-sample: counts by period and source type, and 20 random rows of the corpus
corpus-sample: $(VENV)/.installed
	$(PY) -m signals.corpus.readout

## make corpus-check-sheet: the owner's random 50 eligibility decisions to hand-check in Excel (git-ignored)
corpus-check-sheet: $(VENV)/.installed
	$(PY) -m signals.corpus.review --check-sheet

## make gold-draw: draw the gold set and practice set from the corpus (Clarification 24; seed 20260923)
gold-draw: $(VENV)/.installed
	$(PY) -m signals.gold_set.draw

## make gold-sheets: build the two labelers' Excel files in signals/gold_set/sheets/ (git-ignored)
gold-sheets: $(VENV)/.installed
	$(PY) -m signals.gold_set.sheets

## make lock-labels FILE=path: check a returned CSV, fingerprint it in locks.md, commit and push locks.md only
lock-labels: $(VENV)/.installed
	$(PY) -m signals.gold_set.labels lock "$(FILE)"

## make compare-practice: where the two practice sets differ, side by side (practice files only)
compare-practice: $(VENV)/.installed
	$(PY) -m signals.gold_set.labels compare-practice

## make publish-labels: after both main-round locks, verify fingerprints and commit labels_L1/L2.csv and the key
publish-labels: $(VENV)/.installed
	$(PY) -m signals.gold_set.labels publish

## make jev-hello: one live Jev call on a made-up sentence; prints the answer, model version and tokens (M2.1)
jev-hello: $(VENV)/.installed
	$(PY) -m signals.jev_hello

## make mock-report: the M3 report pages on MOCK numbers (layout only, NOT results; session M3.0). Opens nothing; prints where to look
mock-report: $(VENV)/.installed
	$(PY) -m analysis.mock_results
	$(PY) -m analysis.report.build outputs/mock/results outputs/mock/report --no-marker-preview outputs/mock/results_no_marker

## make report: the same pages from real M3 results in outputs/results/ (same schema, same layout; M3 calls this)
report: $(VENV)/.installed
	$(PY) -m analysis.report.build outputs/results outputs/report

## make m3-dry: the 1% dry run of the whole M3 grid; prints a time estimate (session v0.1-C)
m3-dry: $(VENV)/.installed
	$(PY) -m analysis.m3.run --dry

## make results: delete and rebuild every result from scratch: the full grid (about 8 minutes on 8 cores),
## the results files, the episode replays (Jev answers reused from signals/replay_checks.csv), the hypotheses
## memo and the report. Open outputs/report/index.html. Clarification 31.
results: $(VENV)/.installed
	rm -rf outputs/raw outputs/results outputs/report
	caffeinate -i $(PY) -m analysis.m3.run || $(PY) -m analysis.m3.run
	$(PY) -m analysis.m3.build
	$(PY) -m analysis.m3.replay
	$(PY) -m analysis.m3.memo
	$(PY) -m analysis.report.build outputs/results outputs/report

## make ai-labels: convert the AI-labelled Main tab to signals/gold_set/labels_AI.csv (v0.1 only; Amendment 7)
ai-labels: $(VENV)/.installed
	$(PY) -m signals.gold_set.ai_labels

## make gold-check: v0.1 model-to-model check — run Jev once on the gold set (resumes; never re-asks), then the report
gold-check: $(VENV)/.installed
	$(PY) -m signals.gold_set.jev_check
	$(PY) -m signals.gold_set.check_report

## make markers: M2.5 provisional market-stigma marker per policy (Clarification 30 Part B; v0.1)
markers: $(VENV)/.installed
	$(PY) -m signals.markers

## make corpus-scores: M2.6 score the corpus with the M2.4 question; historical range by period and type (v0.1)
corpus-scores: $(VENV)/.installed
	$(PY) -m signals.corpus_scores

## make freeze: copy every v0.1 Jev output into signals/frozen/ with the banner and a manifest of fingerprints
freeze: $(VENV)/.installed
	$(PY) -m signals.freeze
