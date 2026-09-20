# Agent architecture

Mira is one digital CFO. Specialists are an internal office. The user never manages a swarm.

## Who may do what

| Actor | May | Must not |
| --- | --- | --- |
| Mira (CFO / master planner) | Intake events, decompose goals, plan a DAG, delegate `AgentTask`s, review `AgentTaskResult`s, adjudicate, escalate, speak to the user | Invent amounts, scores, matches, policy outcomes |
| AP / AR specialist | Call invoice, match, duplicate, aging, cash-application tools | Set a total or a match status in prose |
| Treasury specialist | Call cash, bank recon, payment-scheduling tools | Invent cash or force a match |
| Controller specialist | Close checklist, period controls, balance-sheet evidence | Close a period because the narrative sounds done |
| Auditor specialist | Adversarial review: policy, controls, evidence, risk, confidence | Rubber-stamp another agent |
| FP&A / board specialist | Variance, scenarios, 13-week forecast, board summaries from tools | Assert unaudited certainty |
| OpenAI Agents SDK | Plan, investigate, interpret, choose which tool to call, explain | Override a tool result |

## Runtime shape

```
event / executive request
        │
        v
   Mira planner  (OpenAI Agents SDK when configured; deterministic planner in tests)
        │  typed AgentTask
        v
  specialist  ──function tools──►  Phase 2 engines (finance, recon, risk, policy)
        │  typed AgentTaskResult
        v
   Mira review + HITL authority
        │
        v
   Decision + AuditEvent + optional SavingsEvent
```

## Persistence on every handoff

`AgentTask` rows store:

- `task_id`, originating agent, destination agent, objective
- related business-object ids, evidence ids, tool calls
- structured result, confidence, risk, status, timestamps

A `Decision` points at its `agent_run_id`. `GET /api/v1/decisions/{id}/trace` walks the chain.

## HITL

- High confidence + low risk → auto-complete a **safe internal or sandbox** action
- High confidence + high risk → block / escalate
- Low confidence → human review
- Real-world (non-sandbox) payments never execute

## Tools

See `packages/mira/agents/tools.py`. Names: `evaluate_invoice`, `three_way_match`, `detect_duplicates`, `evaluate_policy`, `assess_risk`, `reconcile_transaction`, `reconcile_period`, `get_cash_position`, `get_ar_aging`, `evaluate_contract`, `get_company_context`, `retrieve_evidence`, `calculate_finance_metrics`, `calculate_autonomy_score`, `obtain_public_signal`.
