# MIRA

**An autonomous digital CFO — not a chatbot.**

Mira is one AI employee for the Office of the CFO. Internally she plans work, delegates to specialist roles, applies deterministic finance engines, learns scoped precedent, and escalates when she is uncertain. You talk to Mira. You do not manage a swarm of chat windows.

HackMIT 2026 · Seeded demo company: **Northstar Labs**

**Design rule: no model ever produces a financial number.** Cash, aging, three-way match, duplicate detection, policy, risk, and forecasts all come from tested Python engines. The only learned component in the request path is a small intent classifier that decides *which* deterministic workflow to run. There is no LLM in the runtime.

---

## What's in the demo

| Surface | Route | What you see |
| --- | --- | --- |
| Command center | `/` | Overnight briefing, protected dollars and hours returned, typed or voice **Ask Mira** |
| How it works | `/office` | Specialist org graph and the measured context-budgeting result |
| Review | `/decisions` | Exception → human approve/reject → scoped AWS $12k precedent |
| Evidence | `/evidence` | Source-document lineage and search hits (live Elastic or local fallback) |
| Signals | `/signals` | Isolated public space data and optional Grok Voice. Never writes finance truth. Not in the top nav. |

### Ask Mira

Ask Mira is a typed or spoken **executive request**, not an open chat. Each request is routed to one bounded finance workflow:

```
text (typed, or Deepgram transcript)
  → intent router (TF-IDF + logistic regression, scikit-learn)
  → deterministic finance tools on a canonical snapshot
  → typed recommendation with routing metadata, evidence, and risk
```

The router recognizes 11 intents: `cash_position`, `ap_ar`, `pending_approvals`, `close_status`, `finance_review`, `vendor_spend`, `invoice_investigation`, `evidence_query`, `risk_controls`, `scenario`, and `help`. Below a 0.35 confidence threshold the request is returned as `unknown` and Mira asks for more specificity instead of guessing. The response always includes the predicted intent, confidence, and model version.

Try:

- `Run today's finance review.`
- `What is our cash position?`
- `Why did September AWS spend increase?`
- `Show payments requiring approval.`
- `What's blocking month-end close?`
- `Can we afford 20 engineers?`

The classifier learns language routing only. It is trained on `data/training/executive_intents.jsonl` (146 labeled examples) and is intentionally small; held-out accuracy is about 84% on a 37-example split, so expect the occasional misroute on unusual phrasing.

### Voice

Mic → Deepgram STT → the same `POST /api/v1/executive/request` path. Optional ElevenLabs TTS reads Mira's already-computed text aloud and does not generate financial reasoning. If Deepgram is unset or down, typed input still works. `GET /api/v1/voice/status` reports readiness.

---

## Stack

| Layer | Choice |
| --- | --- |
| Web | Next.js 15, React 19, TypeScript, Tailwind, shadcn-style UI, React Flow, Recharts |
| API | Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic |
| Language routing | scikit-learn (TF-IDF word + char n-grams → logistic regression) |
| DB | SQLite by default; PostgreSQL 16 via Docker Compose |
| Search | Elastic adapter (optional Compose profile); SQL / in-memory fallback |
| Voice | Deepgram STT and ElevenLabs TTS, both optional |
| Monorepo | `apps/web`, `apps/api`, `packages/mira/*` |

No Kafka, Kubernetes, microservices, or graph database.

---

## Prerequisites

- Python 3.12+
- Node.js 20+ (22 is fine)
- Network access at web build time: `next/font` fetches Google Fonts (Newsreader, IBM Plex)
- Optional: Docker, for Postgres / Elastic
- Optional: API keys in `.env` (copy [`.env.example`](./.env.example))

---

## Quick start (zero infrastructure)

SQLite is the default. Reset to a deterministic seeded demo, then boot the API and UI.

```bash
git clone https://github.com/eshi999/HackMIT26-Mira.git
cd HackMIT26-Mira

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
npm install
cp .env.example .env   # add keys only if you have them

make demo-reset
make demo-doctor

# terminal 1 — API  http://localhost:8000/docs
make api

# terminal 2 — UI   http://localhost:3000
make web
```

`make demo-reset` recreates the SQLite DB, seeds Northstar, and runs the overnight review plus September close. Expected baseline: **$23,250 protected**, **9.50 hours returned**.

`make demo-doctor` reports DB / Dropbox / Elastic / Deepgram / ElevenLabs / Grok as `live`, `demo`, or `unavailable`. It prints configured yes/no only — never secret values.

The Makefile's Python and pip targets use `.venv/bin/...`, but the intent-router targets (`train-intents`, `test-intents`, `check-ask-mira`) call `python3` from your `PATH`. **Activate the venv before running them**, or they will use whatever scikit-learn your system Python has.

The trained router is saved to `data/models/executive_intent_router.pkl` (gitignored). It is trained automatically on first use if missing, so `make train-intents` is only needed after editing the training data.

Health checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/v1/company
curl http://localhost:8000/api/v1/meta
```

---

## Testing

```bash
source .venv/bin/activate
make test          # pytest: apps/api/tests + packages/mira
make lint          # ruff
make typecheck     # tsc --noEmit
make token-eval    # paired context measurement (expect 52.50%, 200,571 tokens avoided, 6/6)
make eval          # Maximor-style baseline vs learned precedent
make check-ask-mira  # retrain router, run router/voice tests, compile-check, typecheck web
```

Targeted suites: `make test-intents`, `make test-ask-mira-python`, `make test-ask-mira-voice`.

Web production build: `npm run build --prefix apps/web` (needs network for fonts).

### Live demo checklist

1. **Ramp** — Command center scoreboard: protected dollars and hours returned, computed from `SavingsEvent` rows written by the runtime.
2. **Ask Mira** — Type `Run today's finance review.` or `Why did September AWS spend increase?`. The mic uses Deepgram when configured; otherwise type.
3. **Listen** — If ElevenLabs is live, Mira speaks her on-screen result. Numbers come from the engines, not the voice layer.
4. **Dropbox / Elastic** — Evidence page: document lineage (`Dropbox-shaped local inbox → Document → locator`) and retrieved hits. Elastic is live only when `ELASTICSEARCH_URL` is set and healthy.
5. **Token Company** — Office page: **52.50%** context reduction, **200,571** estimated tokens avoided, **6/6** correctness retained (`make token-eval` on a fresh seed). This is Mira's own offline context budgeter. Token Company is **not** integrated and no live API is called.
6. **Maximor** — Review page: exception packet → Approve/Reject → **Learn AWS $12k precedent**. New vendors still escalate. `make eval` shows the before/after: a baseline AWS $11k invoice escalates, the same case with the learned precedent pays, and a new-vendor control still holds (autonomy score 63.75 → 68.00).
7. **SpaceXAI** — Signals page: public next launch + ISS position, optional Grok Voice. Does not affect finance truth.

---

## Auth (demo only)

Executive and mutating API routes require a bearer token. Requests without one get a `401`.

```bash
curl -X POST http://localhost:8000/api/v1/executive/request \
  -H "Authorization: Bearer mira-demo-elena" \
  -H "Content-Type: application/json" \
  -d '{"request": "What is our cash position?"}'
```

| Token | Actor | Role | Can authorize spend / precedent | Can resolve approvals |
| --- | --- | --- | --- | --- |
| `mira-demo-elena` | Elena Voss | CFO | yes | yes |
| `mira-demo-jordan` | Jordan Hale | Controller | no | yes |
| `mira-demo-sam` | Sam Okonkwo | AP | no | no |

Override Elena's token with `MIRA_DEMO_TOKEN`; the web app reads `NEXT_PUBLIC_MIRA_DEMO_TOKEN`. These are demo credentials, not real auth.

---

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health`, `/health/ready` | Liveness and DB/seed readiness |
| `GET` | `/api/v1/company`, `/api/v1/briefing`, `/api/v1/meta` | Company, overnight briefing, org and adapter status |
| `POST` | `/api/v1/executive/request` | Ask Mira (`/executive/investigate` is a compatibility alias) |
| `POST` | `/api/v1/overnight`, `/api/v1/events` | Run the overnight review; push an office event |
| `POST` | `/api/v1/decisions/{id}/resolve` | Human approve/reject |
| `POST` | `/api/v1/precedents/authorize` | Typed precedent authorization |
| `GET` | `/api/v1/precedents`, `/office/runs`, `/decisions/{id}/trace` | Precedent list, agent runs, decision audit trace |
| `GET` | `/api/v1/context/efficiency`, `/context/measured` | Context-budgeter results |
| `GET` | `/api/v1/evidence/search` | Evidence retrieval |
| `GET` `POST` | `/api/v1/voice/status`, `/transcribe`, `/request`, `/speak` | Voice pipeline |
| `GET` `POST` | `/api/v1/external-signals/space`, `/space/speak` | Isolated public-data signals |

Full interactive docs at `http://localhost:8000/docs`.

---

## Integrations

Missing credentials → **demo / fallback**. The product still runs.

| Integration | Live when | Fallback |
| --- | --- | --- |
| Deepgram | `DEEPGRAM_API_KEY` healthy | typed Ask Mira |
| ElevenLabs | `ELEVENLABS_API_KEY` healthy | text on screen |
| Dropbox | `DROPBOX_ACCESS_TOKEN` healthy | `data/demo/inbox` |
| Elastic | `ELASTICSEARCH_URL` healthy | in-memory / SQL projection |
| Grok / xAI | `XAI_API_KEY` or `GROK_API_KEY` healthy | labeled public-data snapshot on Signals |
| Public data | `FRED_API_KEY` (Treasury Fiscal Data needs no key) | seeded snapshots |
| Visa | always sandbox in this demo | `is_sandbox=true` |
| Zenni | HTTP contract only | route list appears in `/api/v1/meta`; the routes are not mounted |

Env var **names** (values stay in your local `.env`, never commit):

`DATABASE_URL` `MIRA_ENV` `API_HOST` `API_PORT` `CORS_ORIGINS` `MIRA_BOOTSTRAP` `MIRA_DEMO_TOKEN` `DEEPGRAM_API_KEY` `ELEVENLABS_API_KEY` `ELEVENLABS_VOICE_ID` `DROPBOX_ACCESS_TOKEN` `ELASTICSEARCH_URL` `ELASTICSEARCH_API_KEY` `XAI_API_KEY` `GROK_API_KEY` `FRED_API_KEY` `VISA_SANDBOX` `ZENNI_SKILL_TOKEN` `NEXT_PUBLIC_API_URL` `NEXT_PUBLIC_MIRA_DEMO_TOKEN`

`MIRA_BOOTSTRAP` (default on) seeds Northstar when the API boots.

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
docker compose --profile search up -d   # Elasticsearch 8.15 on :9200
export ELASTICSEARCH_URL=http://localhost:9200
```

---

## Make targets

| Command | What it does |
| --- | --- |
| `make install` | venv, editable Python install, `npm install` |
| `make demo-reset` | wipe SQLite, seed Northstar, run overnight + close |
| `make demo-doctor` | readiness report without exposing secrets |
| `make api` | uvicorn with reload on :8000 |
| `make web` | Next.js dev server on :3000 |
| `make seed` | re-seed Northstar Labs |
| `make migrate` | `alembic upgrade head` |
| `make test` | pytest |
| `make lint` | ruff |
| `make typecheck` | `tsc --noEmit` in `apps/web` |
| `make token-eval` | paired context evaluation |
| `make eval` | baseline vs learned-precedent metrics |
| `make train-intents` | retrain the executive intent router |
| `make test-intents` | router unit tests |
| `make test-ask-mira-python` / `test-ask-mira-voice` | Ask Mira and voice test groups |
| `make check-ask-mira` | full Ask Mira pre-flight |

---

## Repository layout

```
apps/web                 Next.js UI: Command, How it works, Review, Evidence, Signals
apps/api                 FastAPI app, routers, Alembic migrations, API tests
packages/mira/
  core                   Canonical models, schemas, money, typed agent I/O
  agents                 Runtime, intent router, specialists, authority, audit trace
  training               Intent router training script
  finance                Aging, cash, contracts, normalization, snapshots
  risk, policies         Risk detectors and scoring; spend-policy engine
  reconciliation         Three-way match and bank reconciliation
  forecasting            13-week cash forecast and affordability
  memory                 Factual, historical, and precedent memory
  evidence, context      Document indexing; context budgeter and telemetry
  integrations           Dropbox, Elastic, Deepgram, ElevenLabs, Grok, Visa, Zenni
  evaluation, demo       Eval harness; demo reset and doctor
  seed                   Northstar Labs fixture
data/demo/inbox          Messy finance document dump (Dropbox-shaped)
data/training            Intent router training examples
docs/                    Design notes (see below)
```

---

## More docs

- [`docs/DEMO_SCENARIOS.md`](./docs/DEMO_SCENARIOS.md) — planted scenarios and expected numbers
- [`docs/AGENT_ARCHITECTURE.md`](./docs/AGENT_ARCHITECTURE.md) — roles, task protocol, who may do what
- [`docs/MEMORY_AND_PRECEDENT.md`](./docs/MEMORY_AND_PRECEDENT.md) — the three memory stores and precedent authorization
- [`docs/CONTEXT_BUDGETER.md`](./docs/CONTEXT_BUDGETER.md) — deterministic context selection and measurement
- [`docs/sponsor-evidence/token-company/COST_OPTIMIZATION.md`](./docs/sponsor-evidence/token-company/COST_OPTIMIZATION.md) — how the 52.50% figure is measured

Package-level READMEs in `packages/mira/*/README.md` cover each engine.

---

## Demo narrative (Northstar Labs)

Elena Voss hired Mira as digital CFO. Overnight Mira ingested a chaotic AP inbox, blocked a duplicate HelixCloud invoice ($18,400 protected once), aged an overdue Apex Scientific bill, and stopped work that still needs a human. The homepage is that briefing. Ask Mira is a typed or voice executive request, not an open chat.
