# One-word commands for this project. Type `make test` in this folder.
#
# The Python environment lives in .venv/ (never saved to history). It is
# built from requirements.txt the first time any command needs it.

# Python 3.11 or later is required (see CLAUDE.md); 3.13 is used here.
PYTHON_FOR_SETUP ?= python3.13
VENV := .venv
PY := $(VENV)/bin/python

.PHONY: setup test banks lcr demo-waterfall demo-run demo-info demo-episode policy-table costs

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
