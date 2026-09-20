# Mira Context Budgeter

Implemented by Codex on `feat/context-budgeter`, starting from
`8b7e47fe87c53d9cdc3ca1966e70f0be7b06ea34`. No finance, policy, risk,
reconciliation, forecasting, Dropbox, or Elasticsearch algorithms were changed.

## Boundary and entry points

`mira.context.service.prepare_context(snapshot, request)` runs existing deterministic
tools on the **complete canonical snapshot**, then selects and packs context. Model
output is never an input to this API. It performs no approvals, payments, state
transitions, persistence, or external indexing.

`ContextRequest` identifies company, task, profile, optional supported object scopes,
period, headcount, and target tokens. Company mismatch, unknown AP invoices,
inconsistent vendors, and unsupported scope/profile combinations fail explicitly.

`ContextPacket` contains exact deterministic results, structured canonical records,
source IDs, known unknowns, included records, excluded IDs/reasons, an empty
truncation manifest (records are never partially truncated), budget overflow,
retrieval status, and telemetry. Decimal values serialize as strings. Metrics and
forecasts without snapshot UUIDs use explicitly labeled `content:<sha256>` references;
these are not invented evidence IDs. The serialized `model_context` is the measured
model-facing artifact; exclusion manifests and telemetry remain outside it.

## Profiles

All profiles retain applicable canonical approval/decision state and conservatively
retain every active policy. The registry explicitly partitions every snapshot
category into required, optional, or irrelevant. Required means required **within
the task's explicit scope**; missing rows are not fabricated.

| Profile | Deterministic results | Required source context |
| --- | --- | --- |
| AP_INVOICE_REVIEW | Match, policy, contract comparison, risk | Invoice, duplicates, vendor, PO, receipts, linked documents/evidence, contracts, engine-used or explicitly linked precedent |
| TREASURY_RECONCILIATION | Full reconciliation report, cash | Transactions and payments, control state |
| CFO_VARIANCE_INVESTIGATION | Existing AWS period comparison, cash | Current/prior AWS invoices, vendor, contracts, linked precedent |
| FPNA_SCENARIO | Existing hiring forecast, including weekly outputs and assumptions | Canonical metrics and forecasts, control state |
| AUDIT_REVIEW | Full risk and reconciliation reports | Evidence/document metadata, precedent, control state |
| EXECUTIVE_QUESTION | Cash, AR aging, risk | Metrics, control state |

AP scope follows invoice/PO/receipt/document links. AWS retrieval uses the requested
and previous period; the tool's full historical totals remain unmodified. Executive
customer scope filters retrieved invoice/customer records; financial reports remain
explicitly company-wide. Treasury/audit reconciliation is snapshot-wide because that
is the existing engine's contract. The variance profile currently supports AWS;
the executive profile is not a general-purpose financial question solver.

Raw document text is absent from `FinanceSnapshot`. Packets explicitly report this
and missing AP documents/POs/receipts. Unlinked precedent is not guessed from similar
prose. Existing tool evidence pointers and excerpts are retained exactly.

## Budgeting, retrieval, and cache

Required records, all task deterministic outputs, and known unknowns are retained
before any optional records. Optional records rank by existing search hits, then
stable source key. Whole optional records are omitted if they do not fit. If required
context exceeds the target (default 6,000 estimated tokens), the packet reports
`mandatory_over_budget=true` and returns the complete required context.

An in-memory `ElasticAdapter` supplies the existing local search behavior. A configured
live adapter may rank optional sources, with a two-second request timeout. Live hits
are intersected with the canonical company and task-scoped source allowlist. Remote
text and amounts are never copied into packets. Adapter failures/malformed responses
fall back locally. This is application-side filtering after the existing search API,
not a new Elasticsearch tenant-filter API. The budgeter never writes to live Elastic.

`SourceEncodingCache` is optional, bounded, lock-protected, and caller-owned. Keys
include company, task, profile, source, revision, and a SHA-256 hash of exact content.
Only serialized document metadata, evidence records, and policy representations are
cached. Engine results, approval/decision state, and packets are never cached. There
is no global cache, object-ID key, or Python-address dependency. Content must still
be serialized to fingerprint it; this is not claimed as an engine speedup. Runtime
calls currently use fresh preparation without a shared cache.

## Runtime, routing, and telemetry

`run_aws_spend_investigation` is the single integration hook. Its existing bound tools
and deterministic fallback remain in place. It adds the packet to `Runner.run_sync`
input and returns `context_usage` and `context_budget`. Other workflows can call the
additive service; their existing runtime architecture was not rewritten.

`CONTEXT_OPTIMIZATION=off` (default) packs the complete structured snapshot plus task
outputs. `on` selects scoped records and applies the optional-context budget. This
OFF baseline is new and explicitly defined; it is **not a measurement of the previous
AWS prompt**, which was already narrow. The evaluation therefore establishes paired
packet efficiency, not historical production savings.

Routing changes only the model preference passed to the existing SDK Agent:

| Tier | Profiles | Optional environment variable |
| --- | --- | --- |
| LOW_COMPLEXITY | Treasury | `MIRA_MODEL_LOW_COMPLEXITY` |
| STANDARD | AP, audit, executive | `MIRA_MODEL_STANDARD` |
| HIGH_REASONING | AWS variance, FP&A | `MIRA_MODEL_HIGH_REASONING` |

No model name or price is guessed. An unset model uses the existing SDK default.
Routing cannot change tool outputs, policy applicability, authority, or human review.
See [official OpenAI model configuration](https://developers.openai.com/api/docs/guides/agents/models).

Offline estimates use `ceil(UTF-8 bytes / 4)`. `usage_source=estimated` covers only
serialized context, excluding instructions, user text, tool definitions, repeated
tool calls, and output. A separate `provider_usage` record is returned only when an
SDK result actually supplies input/output counts, with `usage_source=provider_reported`
and `scope=provider_run`. Timestamps are telemetry only, so they cannot change context
bytes or financial outputs. No prices or dollar savings are configured.

## Evaluation and small UI surface

```sh
make token-eval
```

This creates a fresh in-memory database using the existing Northstar seed and pairs
OFF/ON requests for AP review, AWS variance, reconciliation, hiring, audit, and an
executive cash/risk question. The existing seed may create missing demo inbox files;
no persistent database or external provider is used. The evaluator compares actual
serialized financial results to fresh direct tool outputs, verifies required facts
and unknowns, and rejects snapshot mutation. Any mismatch exits nonzero. Corruption
tests prove that changed results, removed evidence, and removed unknowns fail.

Authenticated `GET /api/v1/context/efficiency` performs the same read-only comparison
on the current Northstar snapshot. It uses the existing demo bearer authentication,
not a new multi-tenant authentication scheme. The Office page shows measured
reduction, tokens avoided, equivalence, and mandatory overflow. Errors show
unavailability rather than fabricated values. The endpoint creates no agent tasks,
findings, approvals, decisions, or savings events.

Measured seeded totals: **382,044 → 181,473 estimated tokens**; **200,571 avoided
(52.50%)**. Bytes: **1,528,169 → 725,884**. Source records: **1,650 → 200**.
Financial equivalence: six of six scenarios, correctness delta zero. Four required
packets exceed the target; especially large full-company risk/reconciliation outputs
are deliberately preserved. These reports are candidates for future independently
validated task projections, not silent truncation here.

## Validation and limitations

Starting baseline: **100 passed, 1 failed**. The pre-existing failure is
`test_openai_live_path_invokes_runner_and_tools` in `test_codex_correctness.py:449`:
its fake runner expects callable tools/`.fn`, whereas the installed SDK supplies
`FunctionTool` objects. The failure was reproduced before feature changes. Existing
tests were not weakened, deleted, or rewritten to hide it.

Final complete Python run: **156 passed, 1 failed (157 collected)**, including
**56 new passing tests**. Ruff, TypeScript typecheck, the production frontend build,
`make token-eval`, and the existing `make eval` all passed. The same baseline
fake-runner failure remains; this branch does not claim a fully green Python suite.

Tests cover profiles, required evidence/control retention, source lineage, precision,
unknowns, scopes, cache invalidation/isolation, object-ID regression, search fallback,
routing, telemetry sources, both modes, repeatability, corruption rejection, runtime
fallback, and API read-only behavior. Existing snapshot-isolation regressions remain
part of the complete suite.

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check packages apps/api
npm run typecheck --prefix apps/web
npm run build --prefix apps/web
make token-eval
CONTEXT_OPTIMIZATION=on make api
# In another terminal: make web, then open /office
curl -H 'Authorization: Bearer mira-demo-elena' http://localhost:8000/api/v1/context/efficiency
```

OpenAI and Elasticsearch live services were not invoked for validation; runtime
integration is tested with injected runners/adapters and deterministic fallbacks.
Token Company is disabled/not integrated; there are no invented endpoints or SDK
calls. Equivalence tests validate deterministic truth and retained facts, not the
quality of an unexecuted model explanation. Telemetry is returned, not persisted to
a new usage database. No billed-token or dollar-savings claim is made.
