# MIRA Architecture

Mira is an autonomous digital CFO: one AI employee the company hires, with an internal multi-agent finance organization underneath. The user never manages a swarm of chatbots. They manage an office.

Central question: **how much of the Office of the CFO can one autonomous AI employee actually run?**

This document is the contract for the 24-hour HackMIT 2026 build. Agents are specified here and **not implemented in this slice**. Domain models, adapters, the command-center UI, and a seeded company (Northstar Labs) come first.

---

## 1. Product thesis

Mira is not ChatGPT with a finance prompt. Mira is a worker with:

- a job description (Office of the CFO)
- delegated authority (policy + limits + human escalation)
- an internal staff of specialist agents she does not expose as separate products
- deterministic tools she is not allowed to override (math, matching, risk, controls)
- a memory of company precedent
- an obligation to show evidence for every material action
- a scoreboard of dollars protected and hours returned to humans

The homepage is Mira's **command center**: overnight work, exceptions, cash, and the one or two decisions that still need a human. It is not a prompt box.

```
┌─────────────────────────────────────────────────────────────┐
│  HUMAN                    MIRA                         WORLD │
│  CFO / CEO / AP     one employee,          vendors, banks,   │
│  reviews exceptions  many specialists      Dropbox, public   │
│  grants authority    one face, one voice   data, Visa sandbox│
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Non-negotiable boundaries

| Rule | Enforcement |
| --- | --- |
| LLMs do not perform financial arithmetic | Amounts, tax, aging, runway, 3-way match, and forecast math live in `packages/mira/finance`, `reconciliation`, `forecasting`. Agents receive computed figures. |
| LLMs do not invent risk scores | `packages/mira/risk` emits a scored `RiskAssessment` from explicit factors and an engine version. Agents may *explain* the score; they may not *set* it. |
| No fake external money movement | Visa and bank actions are sandbox/simulated and labeled as such on the object (`is_sandbox=true`) and in the UI. |
| Every autonomous action carries evidence, confidence, risk, and authority | `Decision` is the canonical write. Missing any of those four fields is a schema error, not a prompt failure. |
| One object, one meaning | `Invoice`, `Transaction`, `Vendor`, etc. are shared models. Workflows do not mint parallel types. |
| High risk or low confidence stops for a human | Policy engine + risk engine jointly set `requires_human_approval`. |
| Degrade, don't collapse | Missing Dropbox / Elastic / Deepgram / OpenAI / Visa credentials flip the matching adapter into demo mode. The Northstar seed still runs. |
| Do not sacrifice the core demo | Integrations are adapters. If a sponsor API is late, the vertical still demos on fixtures. |

---

## 3. Repository map

Modular monorepo. Independent verticals can be assigned to Devin or a teammate without crossing the LLM/deterministic line.

```
apps/web                 Next.js command center (React, Tailwind, shadcn, React Flow, Recharts)
apps/api                 FastAPI process: HTTP, authn stub, session, seed, health

packages/mira/core       Canonical models, enums, money, evidence, audit, typed agent I/O
packages/mira/agents     Protocols only in this slice — no runtime, no LLM loops
packages/mira/finance    Deterministic money, COA, aging, spend, cash
packages/mira/risk       Deterministic risk factors and scores
packages/mira/reconciliation  Matching, duplicates, 3-way match
packages/mira/policies   Authority, spend limits, approval routing
packages/mira/forecasting  Runway, 13-week cash, simple statistical forecasts
packages/mira/memory     Precedent write/read across periods
packages/mira/evidence   Evidence records, hashing, search projection
packages/mira/integrations  Dropbox, Elastic, Deepgram, Visa, Zenni, public data
packages/mira/evaluation Dollars protected, hours saved, workflow scores
packages/mira/seed       Northstar Labs fixture
```

Python is one installable package (`mira`) so Cognition/Devin can own a vertical as a directory with tests. The Next.js app is a separate npm workspace.

No Kafka, Kubernetes, microservices, or graph database. One API process, one relational database, optional Elastic.

---

## 4. Runtime shape (after this slice)

```
                    Voice (Deepgram)     Zenni Claw skill
                            \               /
                             \             /
                              v           v
                         ┌─────────────────────┐
                         │  Safe action API    │  idempotency, authority,
                         │  apps/api           │  sandbox flags, audit
                         └──────────┬──────────┘
                                    │
                         ┌──────────v──────────┐
                         │  Mira (CFO agent)   │  plans, delegates, reviews
                         │  one persona        │  never raw-chats as 6 bots
                         └──────────┬──────────┘
              structured AgentTask  │  structured AgentTaskResult
        ┌────────────┬──────────────┼──────────────┬────────────┐
        v            v              v              v            v
     AP/AR       Treasury      Procurement      Audit/      FP&A /
     intake       cash          Visa path       Policy      forecast
        │            │              │              │            │
        └────────────┴──────┬───────┴──────────────┴────────────┘
                            v
                 Deterministic engines
                 (math, match, risk, policy)
                            v
                 Company store + AuditEvent
                 Evidence layer → Elastic
```

Mira is the only agent allowed to address the user. Specialists speak to Mira in **typed objects**, not prose. Prose is allowed only as an `explanation` field *inside* a schema.

This slice stops **before** the Mira runtime and specialist loops. The schemas, models, and HTTP shell exist so those loops have something lawful to write.

---

## 5. Control loop (target)

For any workflow (invoice, procurement, close, forecast):

1. **Ingest** — document, NL need, voice, Zenni, or period trigger.
2. **Normalize** — map onto canonical objects (`Invoice`, `PurchaseOrder`, …).
3. **Plan** — Mira emits an `AgentRun` with a list of `AgentTask`s.
4. **Delegate** — specialists return `AgentTaskResult` subclasses.
5. **Compute** — engines attach amounts, match results, risk, policy hits.
6. **Decide** — Mira writes a `Decision` with evidence, confidence, risk, authority.
7. **Gate** — if `requires_human_approval`, create `Approval` and stop.
8. **Act** — sandbox payment, ledger proposal, vendor selection, etc.
9. **Learn** — store `Precedent` when a human confirms or overrides.
10. **Score** — write `SavingsEvent` (Ramp) and index evidence (Elastic).

Long-horizon work is an `AgentRun` that can span periods. Memory is `Precedent` + prior `Decision`s + period `Metric`s, not a chat log.

---

## 6. Deterministic vs generative

| Generative (LLM, structured out) | Deterministic (Python, tested) |
| --- | --- |
| Classify a messy document | Sum invoice lines, tax, aging |
| Extract fields from a contract/invoice into a schema | Duplicate detection (amount+vendor+date+fuzzy invoice #) |
| Propose a vendor given constraints | Budget remaining, 3-way match |
| Draft a recommendation and explanation | Risk score from factor table |
| Decide which specialist to call | Policy threshold, approval matrix |
| Read precedent and analogize | Forecast arithmetic, runway |
| Escalate with a question | Audit hash chain append |

If a value *must* be right, it is not generated.

---

## 7. Typed agent I/O

Agents MUST NOT communicate through unstructured prose alone. Canonical output types live in `packages/mira/core/agent_outputs.py`:

- `EvidenceReference`
- `RiskFinding`
- `ReconciliationResult`
- `InvoiceDecision`
- `AuditFinding`
- `AgentTaskResult`
- `CFORecommendation`
- `HumanEscalation`

Plus money (`Money`), confidence (`Confidence`), and risk (`RiskLevel`). Every `Decision` row serializes these types into JSONB/JSON columns so the UI, audit log, and Elastic index see the same shape.

---

## 8. Evidence and audit

`Evidence` is a first-class object (document snippet, ledger row, public series, policy clause). `EvidenceReference` points at it with a locator (`page:3`, `field:total`, `series:DGS3MO`).

`AuditEvent` is append-only. Application code inserts; it never updates or deletes. Actors are `user | mira | agent | system | zenni | voice`. Payload is JSON without secrets.

The Elastic adapter projects `Evidence`, `Transaction`, `Decision`, `Finding`, and `AuditEvent` into a single search index. pgvector is **not** used in this slice; Elastic is the search layer. If Elastic is down, SQL filters still serve the command center.

---

## 9. Integration adapters

Every third-party system is an interface + a demo implementation.

| Adapter | Demo mode (default) | Live mode (optional) |
| --- | --- | --- |
| Storage | `data/demo/inbox` | Dropbox folder |
| Search | SQL `LIKE` / filters | Elastic |
| Voice | typed command API | Deepgram STT → same API |
| Payments | `Payment.is_sandbox=true` | Visa sandbox, still labeled |
| Public data | seeded FRED-like series | FRED/Treasury fetch |
| Zenni | HTTP skill routes | Claw custom skill calling those routes |
| Models | n/a this slice | OpenAI Agents SDK behind `mira.agents` |

Adapters live in `packages/mira/integrations`. The API never imports vendor SDKs from routers.

### Zenni Claw surface (designed, not fully implemented)

Safe, idempotent skill routes Mira will expose:

- `GET  /api/v1/skills/cfo/briefing`
- `POST /api/v1/skills/cfo/procurement`
- `POST /api/v1/skills/cfo/invoice-intake`
- `GET  /api/v1/skills/cfo/cash`
- `POST /api/v1/skills/cfo/decisions/{id}/resolve`

Constraints: bearer skill token, authority matrix, no arbitrary SQL/tool execution, sandbox payments only unless a human has approved a live path (out of scope for the hackathon).

### Voice

Deepgram transcribes. A small intent router maps speech onto the same skill routes. Mira replies with a briefing, not an open-ended chat. Confirmation phrases are required before any `Decision` that spends money.

---

## 10. Frontend information architecture

| Route | Purpose |
| --- | --- |
| `/` | Command center. Mira's overnight briefing, cash, savings, exceptions. **No chatbot.** |
| `/office` | Internal finance org as a graph (React Flow). Specialists are roles, not chat avatars. |
| `/decisions` | Human review queue. Evidence, confidence, risk, policy basis. |
| `/evidence` | Searchable evidence layer (Elastic when available). |

Visual language: editorial finance OS — ink navy, brass, ledger green. Mira has one mark and one voice. Specialists appear as function nodes.

---

## 11. Data stores

- **SQLite** default for laptop / CI / demo with zero infra.
- **PostgreSQL 16** via Docker Compose when available (SQLAlchemy URL swap).
- **Alembic** migrations generated from SQLAlchemy metadata.
- **Elastic** optional, search profile in Compose.
- **Local files** under `data/` for the Dropbox-shaped inbox.

Money is `Numeric(18, 2)` in the database and `Decimal` in Python. Never `float`.

---

## 12. Demo company: Northstar Labs

Seeded in `packages/mira/seed/northstar.py`. Series B lab company, messy AP inbox, a duplicate vendor bill, an overdue scientific supplier, a GPU procurement that needs dual approval, a 13-week cash sketch, and a public-market rate signal. This is the Long Lake "skeptic" narrative: chaos in → measured dollars and hours out.

---

## 13. 24-hour sequencing

| Order | Slice | Status in this PR |
| --- | --- | --- |
| 0 | Architecture, scorecard, data model | **this PR** |
| 1 | Monorepo, models, migrations, health, seed, boot tests | **this PR** |
| 2 | Command center UI on seeded data | **this PR** (shell) |
| 3 | Deterministic engines: policy, duplicate, 3-way, risk, savings, recon, contracts, public data, Elastic projection | **this PR (phase 2)** |
| 4 | Mira runtime + specialist agents (OpenAI Agents SDK) | next — **do not start here** |
| 5 | Procurement path (Visa sandbox) | next |
| 6 | Dropbox ingest + textual analysis | next |
| 7 | Elastic evidence index | next |
| 8 | Deepgram voice + Zenni skill | next |
| 9 | Polish, eval harness, demo script | final hours |

---

## 14. Cognition / Devin assignment cuts

Each directory under `packages/mira/` is a vertical with a README, typed interfaces, and tests. Suggested ownership:

- Devin A — `reconciliation` + `finance` math
- Devin B — `policies` + `risk`
- Devin C — `evidence` + Dropbox/Elastic adapters
- Cursor/human — Mira runtime, UI, demo narrative

Do not let two verticals define their own `Invoice`.

---

## 15. Explicitly out of scope for this slice

- Any LLM call or agent loop
- Real card/bank transactions
- Kafka, K8s, Neo4j, microservices
- End-user auth beyond a demo user on Northstar
- pgvector
