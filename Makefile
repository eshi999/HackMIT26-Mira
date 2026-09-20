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

.PHONY: train-intents test-intents

train-intents:
	PYTHONPATH=packages python3 -m mira.training.train_intent_router

test-intents:
	PYTHONPATH=packages python3 -m pytest packages/mira/tests/test_intent_router.py -q


.PHONY: test-ask-mira-python test-ask-mira-voice check-ask-mira

test-ask-mira-python:
	PYTHONPATH=packages python3 -m pytest \
		packages/mira/tests/test_intent_router.py \
		packages/mira/tests/test_intent_quality.py \
		packages/mira/tests/test_executive_router_runtime.py \
		packages/mira/tests/test_data_validation.py \
		packages/mira/tests/test_mira_web_contract.py \
		-q

test-ask-mira-voice:
	PYTHONPATH=apps/api:packages python3 -m pytest \
		apps/api/tests/test_voice.py \
		packages/mira/tests/test_deepgram.py \
		packages/mira/tests/test_elevenlabs.py \
		-q

check-ask-mira: train-intents test-ask-mira-python test-ask-mira-voice
	python3 -m py_compile \
		packages/mira/agents/runtime.py \
		packages/mira/agents/intent_router.py \
		packages/mira/training/train_intent_router.py \
		apps/api/app/routers/voice.py
	npm run typecheck --prefix apps/web
