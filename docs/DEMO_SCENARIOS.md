# Demo scenarios (Phase 3 runtime)

Northstar Labs remains the company. Seed still plants the Phase 2 known answers. The runtime **acts** on those rows.

## Command center (not a chat)

Overnight work runs on first briefing load:

- `invoice_received` for duplicate-suspect and needs-review AP
- treasury cash + reconciliation
- September month-end DAG
- `SavingsEvent` rows with `source=runtime`

If the office has not yet written impact rows, the scoreboard is zero — it does not reuse seed marketing copy.

## HelixCloud duplicate

AP detects the duplicate. Mira blocks payment. Runtime writes **one** duplicate-group savings event for the canonical obligation. LabBench INV-4850 / INV-4850A protects **$4,850**, not $9,700. Helix 10441 / 10441-A protects **$18,400** once.

## AWS spike vs auditor

AP three-way-matches AWS-2026-09 ($19,800) and recommends **pay**. The auditor rejects on spend policy + unusual-amount evidence. Mira escalates to `awaiting_human`. The decision is not `executed`; no payment rail ran.

## Learned AWS precedent

See `docs/MEMORY_AND_PRECEDENT.md`. Evaluation harness uses typed `teach_precedent` with Elena's demo actor, not free-text feedback.

## Month-end close

`month_end_started` plans a dependency-aware DAG. Completion is predicate-based: missing documents fail document readiness; unresolved bank items fail reconciliation; auditor rejection fails audit review; outstanding human decisions prevent 100%. Close runs are scoped by period (`month_end_close:2026-09` vs `month_end_close:2026-10`).

## Executive requests

Mutating routes require `Authorization: Bearer mira-demo-elena`.

`POST /api/v1/executive/request`

Examples:

- Run today's finance review.
- What's blocking month-end close?
- What's the September status? / What's the October status?
- Why did September AWS spend increase?
- Show payments requiring approval.
- Can we afford 20 engineers?

Bounded OpenAI path (same question also on `POST /api/v1/executive/investigate`):

executive request → `run_aws_spend_investigation` → OpenAI Agents SDK `Runner.run_sync` when `OPENAI_API_KEY` is set → Mira planner → `investigate_aws_spend` / `get_cash_position` tools → ledger evidence → evidence-grounded explanation. Without a key, the same evidence is returned by a deterministic fallback.

Arithmetic for the hiring scenario is `packages/mira/forecasting/cash.py`. Affordability uses **minimum 13-week cash**, not ending cash.

## Seeded demo baseline

Measured from a fresh `seed_northstar` + overnight (`limit=20`) + September close, twice. Values are engine/workflow authored, not marketing constants.

| Metric | Value |
| --- | --- |
| Protected dollars | `23250.00` (LabBench duplicate group `4850.00` + Helix duplicate group `18400.00`) |
| Hours returned | `9.50` |
| Pending approvals | `14` |
| Open incidents | `44` |
| Close % | `0.10` |
| Reconciliation rate | `0.35` |
| Autonomous completion rate | `0.07` |
| Autonomy score | `57.25` |

`test_seeded_demo_metrics_are_deterministic` asserts the two runs match. LabBench protection is asserted exactly as `$4850.00`.
