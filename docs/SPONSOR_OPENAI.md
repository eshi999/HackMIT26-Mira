# OpenAI — The Fifth Teammate

This is not a "powered by OpenAI" sticker. Mira's planner is wired to the **OpenAI Agents SDK** in `packages/mira/agents/openai_runtime.py`.

## What the runtime actually does

`build_org()` constructs:

- **Mira** — master planner with `handoffs` to specialists
- **AP/AR, Treasury, Controller, Auditor, FP&A** — each an `Agent` with the same deterministic tool list

When `OPENAI_API_KEY` is set **and** the `openai-agents` package is installed, `run_aws_spend_investigation` constructs a Mira `Agent` with snapshot-bound tools and calls `agents.Runner.run_sync`.

**Endpoint:** `POST /api/v1/executive/request` with `"Why did September AWS spend increase?"`  
**Alias:** `POST /api/v1/executive/investigate`

**Path:** executive request → `mira.agents.openai_runtime.run_aws_spend_investigation` → `Runner.run_sync(Mira, bound tools)` → `collect_aws_spend_evidence` / `tool_get_cash_position` → model explains those results.

Without `OPENAI_API_KEY` or on provider failure, the same ledger evidence is returned by a deterministic fallback. Tests mock `Runner.run_sync` at the provider boundary.

The model may choose tools, organize investigation, and explain deterministic results. It may not invent calculations, official risk, policy, authority, execution, or evidence.

## Tools the agents call

All of these wrap Phase 2 engines. None of them ask the model for a number.

`evaluate_invoice`, `three_way_match`, `detect_duplicates`, `evaluate_policy`, `assess_risk`, `reconcile_transaction`, `reconcile_period`, `get_cash_position`, `get_ar_aging`, `evaluate_contract`, `get_company_context`, `retrieve_evidence`, `calculate_finance_metrics`, `calculate_autonomy_score`, `obtain_public_signal`.

## Example handoff

Mira → AP specialist, persisted as `AgentTask`:

| Field | Example |
| --- | --- |
| originating_agent | `mira_cfo` |
| destination_agent | `accounts_payable` |
| objective | Process invoice AWS-2026-09: match, duplicates, operational recommendation |
| related_object_ids | `[INV_AWS_SEP]` |
| tool_calls | `evaluate_invoice`, `detect_duplicates`, `three_way_match` |
| structured_result | `InvoiceDecision` JSON |
| confidence / risk | engine fields, copied onto the task |

The SDK `handoffs=[ap, treasury, …]` list is the model-facing equivalent of that typed task. Prose is never the only payload.

## Why the LLM cannot override finance truth

1. Amounts, matches, risk, policy, savings, and forecasts are computed in Python engines.
2. Tool functions return Pydantic objects; specialists copy those objects into `AgentTask.result_payload`.
3. Mira's adjudication reads those payloads and the HITL matrix. It does not recompute them.
4. Tests assert AP **pay** vs auditor **reject** on seeded AWS-2026-09 using tools only — no transcript fixture.

## Sample task trace

`GET /api/v1/decisions/{id}/trace` returns the `AgentRun`, ordered `AgentTask`s (origin, destination, tools, result), and append-only `AuditEvent`s with `correlation_id = agent_run_id`.
