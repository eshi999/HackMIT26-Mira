# MIRA

**An autonomous digital CFO — not a chatbot.**

Mira is one AI employee for the Office of the CFO. Internally she plans work, delegates to specialist roles, applies deterministic finance engines, learns scoped precedent, and escalates when she is uncertain. You talk to Mira. You do not manage a swarm of chat windows.

HackMIT 2026. Seeded demo company: **Northstar Labs**.

This branch is the judge-ready demo: overnight briefing, human review, voice in/out, and sponsor-visible proof. Finance arithmetic still comes from engines, not from a model. See [ARCHITECTURE.md](./ARCHITECTURE.md), [DATA_MODEL.md](./DATA_MODEL.md), [docs/DEMO_SCENARIOS.md](./docs/DEMO_SCENARIOS.md), and [SPONSOR_SCORECARD.md](./SPONSOR_SCORECARD.md).

---

## What is implemented

| Surface | What a judge sees |
| --- | --- |
| Command center `/` | Overnight briefing, Ramp protected dollars + hours returned, typed/voice Ask Mira |
| Office `/office` | Specialist org graph + Token Company measured context reduction |
| Review `/decisions` | Exception → human approve/reject → typed AWS $12k precedent |
| Evidence `/evidence` | Dropbox-shaped source lineage + Elastic retrieved hits (live or demo projection) |
| Signals `/signals` | Isolated public space data + optional Grok Voice; does not write finance truth |

**Voice:** mic → Deepgram STT → existing `POST /api/v1/executive/request`. Typed input still works if Deepgram is unset or down. Optional ElevenLabs TTS speaks Mira's already-computed text only. It does not generate financial reasoning.

**OpenAI:** bounded AWS spend investigation only. Not required. Without `OPENAI_API_KEY`, the same ledger evidence is returned by a deterministic fallback. Smoke: `make openai-smoke`.

**Optional adapters** stay in demo mode when credentials are missing. The command center still boots.

---

## Stack

| Layer | Choice |
| --- | --- |
| Web | Next.js, React, TypeScript, Tailwind, shadcn-style UI, React Flow, Recharts |
| API | Python 3.12, FastAPI, Pydantic, SQLAlchemy 2 |
| DB | SQLite by default; PostgreSQL 16 via Docker Compose |
| Search | Elastic adapter (optional Compose profile); SQL / in-memory fallback |
| Voice | Deepgram STT (optional), ElevenLabs TTS (optional) |
| Monorepo | `apps/web`, `apps/api`, `packages/mira/*` |

No Kafka, Kubernetes, microservices, or graph database.

---

## Prerequisites

- Python 3.12+
- Node.js 20+ (22 is fine)
- Optional: Docker, for Postgres / Elastic
- Optional keys in `.env` (copy [`.env.example`](./.env.example))

---

## Quick start (zero infrastructure)

SQLite is the default. Reset to a deterministic seeded demo, then boot API + UI.

```bash
git checkout feat/final-integrations-demo

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# optional live OpenAI planner:
# pip install -e ".[openai]"
npm install
cp .env.example .env   # add keys only if you have them

make demo-reset
make demo-doctor

# terminal 1 — API  http://localhost:8000/docs
make api

# terminal 2 — UI   http://localhost:3000
make web
```

`make demo-reset` recreates SQLite, seeds Northstar, and runs overnight + September close. Expected baseline: **$23,250 protected**, **9.50 hours returned**.

`make demo-doctor` reports DB / Dropbox / Elastic / Deepgram / ElevenLabs / OpenAI / Grok as live, demo, or unavailable. It prints configured yes/no only — never secret values.

Health:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/v1/company
curl http://localhost:8000/api/v1/meta
```

---

## How to test

### Automated

```bash
source .venv/bin/activate
make test          # pytest: apps/api/tests + packages/mira
make lint          # ruff
make typecheck     # tsc --noEmit
npm run build --prefix apps/web
make token-eval    # paired context measurement (expect 52.50%, 200,571 tokens avoided, 6/6)
make eval          # Maximor baseline vs learned precedent
make openai-smoke  # skips cleanly if OPENAI_API_KEY is unset
```

### Live demo checklist

1. **Ramp** — Command center scoreboard: protected dollars and hours returned from `SavingsEvent` rows.
2. **Ask Mira** — Type `Run today's finance review.` or `Why did September AWS spend increase?`. Mic uses Deepgram when configured; otherwise type.
3. **Listen** — If ElevenLabs is live, speak Mira's on-screen result. The model is not asked to invent numbers.
4. **Dropbox / Elastic** — Evidence page: document lineage (`Dropbox-shaped local inbox → Document → locator`) and retrieved search hits. Elastic is live only when `ELASTICSEARCH_URL` is set and healthy.
5. **Token Company** — Office page: measured **52.50%** context reduction, **200,571** estimated tokens avoided, **6/6** correctness retained (`make token-eval` on a fresh seed). Token Company is not a live API.
6. **Maximor** — Review page: exception packet → Approve/Reject → **Learn AWS $12k precedent**. New vendors still escalate.
7. **SpaceXAI** — Signals page: public next launch + ISS position. Optional Grok Voice. Does not affect finance truth.

Mutating routes need `Authorization: Bearer mira-demo-elena`.

---

## Make targets

| Command | What it does |
| --- | --- |
| `make install` | editable Python install + `npm install` |
| `make demo-reset` | wipe SQLite, seed Northstar, run overnight + close |
| `make demo-doctor` | readiness report without exposing secrets |
| `make openai-smoke` | optional live-key OpenAI check; skip if unset |
| `make test` | pytest |
| `make lint` | ruff |
| `make typecheck` | `tsc --noEmit` in `apps/web` |
| `make token-eval` | paired context evaluation |
| `make eval` | Maximor baseline vs learned-state metrics |
| `make api` | uvicorn with reload |
| `make web` | Next.js dev server |
| `make seed` | re-seed Northstar Labs |
| `make migrate` | alembic upgrade head |

---

## Integrations

Missing credentials → **demo / fallback**. The product still runs.

| Integration | Live when | Fallback |
| --- | --- | --- |
| Deepgram | `DEEPGRAM_API_KEY` healthy | typed Ask Mira |
| ElevenLabs | `ELEVENLABS_API_KEY` healthy | text on screen |
| Dropbox | `DROPBOX_ACCESS_TOKEN` healthy | `data/demo/inbox` |
| Elastic | `ELASTICSEARCH_URL` healthy | in-memory / SQL projection |
| OpenAI | `OPENAI_API_KEY` + `openai-agents` | deterministic AWS investigation |
| Grok / xAI | `XAI_API_KEY` or `GROK_API_KEY` healthy | labeled public-data snapshot on Signals |
| Visa | always sandbox in this demo | `is_sandbox=true` |

Env var **names** (values stay in local `.env`, never commit):

`DATABASE_URL` `MIRA_ENV` `API_HOST` `API_PORT` `CORS_ORIGINS` `MIRA_BOOTSTRAP` `MIRA_DEMO_TOKEN` `OPENAI_API_KEY` `DEEPGRAM_API_KEY` `ELEVENLABS_API_KEY` `ELEVENLABS_VOICE_ID` `DROPBOX_ACCESS_TOKEN` `ELASTICSEARCH_URL` `ELASTICSEARCH_API_KEY` `XAI_API_KEY` `GROK_API_KEY` `FRED_API_KEY` `VISA_SANDBOX` `ZENNI_SKILL_TOKEN` `NEXT_PUBLIC_API_URL` `NEXT_PUBLIC_MIRA_DEMO_TOKEN`

---

## PostgreSQL / Elastic (optional)

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg://mira:mira@localhost:5432/mira
make migrate
make demo-reset
make api
```

```bash
docker compose --profile search up -d
```

---

## Repository layout

```
apps/web                 Command center, Review, Evidence, Office, Signals
apps/api                 FastAPI process, Alembic, API tests
packages/mira/core       Canonical models, schemas, typed agent I/O
packages/mira/agents     Deterministic runtime + bounded OpenAI Agents SDK path
packages/mira/{finance,risk,reconciliation,policies,
               forecasting,memory,evidence,context,integrations,evaluation,demo}
packages/mira/seed       Northstar Labs fixture
data/demo/inbox          Messy finance document dump (Dropbox-shaped)
```

---

## Demo narrative (Northstar Labs)

Elena Voss hired Mira as digital CFO. Overnight Mira ingested a chaotic AP inbox, blocked a duplicate HelixCloud invoice ($18,400 protected once), aged an overdue Apex Scientific bill, and stopped work that still needs a human. The homepage is that briefing. Ask Mira is a typed/voice **executive request**, not an open chat.
