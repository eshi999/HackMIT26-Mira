# MIRA

**An autonomous digital CFO — not a chatbot.**

Mira is one AI employee that runs as much of the Office of the CFO as we can prove in 24 hours. Internally she plans, delegates to specialist finance agents, applies deterministic controls, learns precedent, and escalates when she is uncertain. You interact with Mira. You do not manage a swarm of chat windows.

HackMIT 2026. Seeded demo company: **Northstar Labs**.

This slice is foundation only: architecture, canonical models, API health, seed data, and a command-center UI. **Agent runtimes are not implemented yet.** See [ARCHITECTURE.md](./ARCHITECTURE.md), [DATA_MODEL.md](./DATA_MODEL.md), and [SPONSOR_SCORECARD.md](./SPONSOR_SCORECARD.md).

---

## Stack

| Layer | Choice |
| --- | --- |
| Web | Next.js, React, TypeScript, Tailwind, shadcn-style UI, React Flow, Recharts |
| API | Python 3.12, FastAPI, Pydantic, SQLAlchemy 2 |
| DB | SQLite by default; PostgreSQL 16 via Docker Compose |
| Search | Elastic adapter (optional Compose profile); SQL fallback |
| Monorepo | `apps/web`, `apps/api`, `packages/mira/*` |

No Kafka, Kubernetes, microservices, or graph database.

---

## Prerequisites

- Python 3.12+
- Node.js 20+ (22 is fine)
- Optional: Docker, for Postgres / Elastic

---

## Quick start (zero infrastructure)

SQLite is the default. The API creates the schema and seeds Northstar Labs on boot.

```bash
# 1. Python env + package
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Frontend deps
npm install

# 3. Tests (API boot + models + seed)
make test

# 4. Run API  (http://localhost:8000/docs)
make api

# 5. In another terminal: command center (http://localhost:3000)
make web
```

Health:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/v1/company
```

---

## Make targets

| Command | What it does |
| --- | --- |
| `make install` | editable Python install + `npm install` |
| `make test` | pytest (boot, models, seed) |
| `make typecheck` | `tsc --noEmit` in `apps/web` |
| `make api` | uvicorn with reload |
| `make web` | Next.js dev server |
| `make seed` | re-seed Northstar Labs |
| `make migrate` | alembic upgrade head |

---

## PostgreSQL (optional)

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg://mira:mira@localhost:5432/mira
make migrate
make seed
make api
```

Elastic (optional, not required to boot):

```bash
docker compose --profile search up -d
```

---

## Repository layout

```
apps/web                 Command center UI
apps/api                 FastAPI process, Alembic, API tests
packages/mira/core       Canonical models, schemas, typed agent I/O
packages/mira/agents     Protocols only — no LLM loops in this slice
packages/mira/{finance,risk,reconciliation,policies,
               forecasting,memory,evidence,integrations,evaluation}
packages/mira/seed       Northstar Labs fixture
data/demo/inbox          Messy finance document dump (Dropbox-shaped)
```

---

## Demo narrative (Northstar Labs)

Elena Voss hired Mira as digital CFO. Overnight Mira ingested a chaotic AP inbox, blocked a duplicate HelixCloud invoice, aged an overdue Apex Scientific bill, and stopped a GPU procurement for dual approval. The homepage is that briefing. There is no prompt box.

---

## Tests and typecheck

```bash
source .venv/bin/activate
make test
make typecheck
```

CI-equivalent: the project is considered booting when pytest is green and the API `/health/ready` returns the Northstar company after seed.

---

## What this slice does not do

- No agent loops, no OpenAI calls
- No live Dropbox / Elastic / Deepgram / Visa network calls
- No real money movement (sandbox payments are labeled)

Adapters are in place so those verticals can be filled without rewriting Invoice.
