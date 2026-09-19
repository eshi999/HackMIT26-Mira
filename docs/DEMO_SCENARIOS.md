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

AP detects the duplicate. Mira blocks payment. Runtime writes dollars protected from the invoice total.

## AWS spike vs auditor

AP three-way-matches AWS-2026-09 ($19,800) and recommends **pay**. The auditor rejects on spend policy + unusual-amount evidence. Mira escalates. Not a scripted dialogue.

## Learned AWS precedent

See `docs/MEMORY_AND_PRECEDENT.md`. Evaluation harness replays run 1 / feedback / run 2 / new-vendor control.

## Month-end close

`month_end_started` plans a dependency-aware DAG (documents, AP, AR, bank, payroll, accruals, balance sheet, audit, variance, board pack). Independent tasks run when ready. Failures block dependents instead of inventing completion.

## Executive requests

`POST /api/v1/executive/request`

Examples:

- Run today's finance review.
- What's blocking month-end close?
- Investigate September AWS variance.
- Show payments requiring approval.
- Can we afford three engineers?

Arithmetic for the hiring scenario is `packages/mira/forecasting/cash.py`.
