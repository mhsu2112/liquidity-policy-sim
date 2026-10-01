# One-word commands for this project. Type `make test` in this folder.
#
# The Python environment lives in .venv/ (never saved to history). It is
# built from requirements.txt the first time any command needs it.

# Python 3.11 or later is required (see CLAUDE.md); 3.13 is used here.
PYTHON_FOR_SETUP ?= python3.13
VENV := .venv
PY := $(VENV)/bin/python

.PHONY: setup test banks lcr demo-waterfall

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
