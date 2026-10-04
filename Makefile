PY := .venv/bin/python

.PHONY: install test lint dev

install:
	python3 -m venv .venv
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

dev:
	$(PY) -m uvicorn services.gateway.main:app --reload --port 8000
