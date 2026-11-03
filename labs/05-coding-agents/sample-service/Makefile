PY ?= $(shell command -v python >/dev/null 2>&1 && echo python || echo python3)

.PHONY: test lint fmt run

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

fmt:
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

run:
	$(PY) -m uvicorn app.main:app --reload
