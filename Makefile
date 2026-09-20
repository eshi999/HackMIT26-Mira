.PHONY: install test typecheck api web seed migrate lint eval token-eval demo-reset demo-doctor openai-smoke

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
UVICORN ?= .venv/bin/uvicorn
PYTEST ?= .venv/bin/pytest

install:
	python3 -m venv .venv
	$(PIP) install -U pip
	$(PIP) install -e ".[dev]"
	npm install

test:
	$(PYTEST) -q apps/api/tests packages/mira

typecheck:
	npm run typecheck --prefix apps/web

api:
	mkdir -p data
	MIRA_BOOTSTRAP=1 $(UVICORN) app.main:app --reload --app-dir apps/api --host 0.0.0.0 --port 8000

web:
	npm run dev --prefix apps/web

seed:
	mkdir -p data
	PYTHONPATH=apps/api:packages $(PYTHON) -m mira.seed.northstar

migrate:
	cd apps/api && PYTHONPATH=../../packages:../../apps/api ../../.venv/bin/alembic upgrade head

lint:
	$(PYTHON) -m ruff check packages apps/api

eval:
	PYTHONPATH=packages $(PYTHON) -m mira.evaluation

token-eval:
	PYTHONPATH=packages $(PYTHON) -m mira.context.evaluation

demo-reset:
	mkdir -p data
	PYTHONPATH=apps/api:packages $(PYTHON) -m mira.demo reset

demo-doctor:
	PYTHONPATH=apps/api:packages $(PYTHON) -m mira.demo doctor

openai-smoke:
	PYTHONPATH=apps/api:packages $(PYTHON) -m mira.demo openai-smoke
