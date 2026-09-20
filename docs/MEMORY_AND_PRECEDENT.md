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

- authenticated canonical actor who is allowed to create that precedent
- explicit outcome
- scope
- vendor/category constraints
- amount threshold
- effective date
- audit evidence
- active, revoked, or rejected status

Table: `precedents` (extended, not replaced). The policy engine consults **active** granting precedents only. A rejected precedent does not grant an exemption.

Free-text human feedback may record a comment. It must not create approval authority, pre-approval precedent, spending authority, or policy exemptions.

Demo auth: `Authorization: Bearer mira-demo-elena` (CFO, can authorize and resolve). `mira-demo-jordan` (controller, resolve only). `mira-demo-sam` (AP, neither). Override Elena's token with `MIRA_DEMO_TOKEN`.

Typed write: `POST /api/v1/precedents/authorize`.

## Required self-improvement demo

1. AWS invoice below $12,000 **without** an active AWS precedent → spend policy escalates.
2. Elena authorizes a typed AWS $12k precedent via `teach_precedent` / `POST /api/v1/precedents/authorize`.
3. A comparable AWS invoice may auto-process if match, risk, and other controls pass.
4. A **new vendor** at the same amount still escalates.
5. The Codex exploit *"AWS invoices under $12,000 are NOT pre-approved"* as free text must not create an ACTIVE pre_approved precedent.

`python -m mira.evaluation` prints baseline vs learned-state metrics.
