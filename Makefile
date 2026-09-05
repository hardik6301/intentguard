.PHONY: eval test

ifneq ($(wildcard .venv/bin/python),)
PYTHON ?= .venv/bin/python
else
PYTHON ?= python3
endif

eval:
	PYTHONPATH=. $(PYTHON) -m evaluation.runner

test:
	PYTHONPATH=. $(PYTHON) -m pytest tests evaluation/test_harness.py
