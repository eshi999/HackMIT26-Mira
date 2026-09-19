# Memory and precedent

Three separate stores. None of them is a chat log.

## Factual memory

Stable company facts.

Example: *AWS is an approved infrastructure vendor.*

Table: `factual_memories`. Written from preferred-vendor rows and explicit runtime facts.

## Historical memory

Observed ranges across periods.

Example: *AWS normally costs $8,000–$12,000/month.*

Table: `historical_memories`. Bootstrapped from invoice history (min / max / typical).

## Decision precedent

A reusable authorization with:

- scope
- conditions
- authorizer
- date/time (`authorized_at`)
- supporting decision / evidence ids
- active or revoked status

Table: `precedents` (extended, not replaced). The policy engine consults **active** precedents.

Precedent may change a future spend-threshold outcome. It must not bypass unrelated controls (new vendor, self-approval, closed period, missing evidence).

## Required self-improvement demo

1. AWS invoice below $12,000 **without** an active AWS precedent → spend policy escalates.
2. Human: *"AWS infrastructure invoices under $12,000 are pre-approved."* → `human_feedback_received` writes a precedent.
3. A comparable AWS invoice may auto-process if match, risk, and other controls pass.
4. A **new vendor** at the same amount still escalates.

`python -m mira.evaluation` prints baseline vs learned-state metrics.
