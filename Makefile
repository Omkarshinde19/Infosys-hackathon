PY := .venv/bin/python

.PHONY: install test lint dev demo down logs e2e

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

# Full stack in Docker: http://localhost:3000
demo:
	docker compose up --build --detach --wait

down:
	docker compose down

logs:
	docker compose logs --follow --tail=50

# End-to-end test against the running `make demo` stack
e2e:
	NETHEAL_E2E=1 $(PY) -m pytest -q tests/e2e
