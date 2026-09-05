.PHONY: eval test

eval:
	PYTHONPATH=. .venv/bin/python -m evaluation.runner

test:
	PYTHONPATH=. .venv/bin/pytest
