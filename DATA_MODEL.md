# MIRA Data Model

Canonical financial objects. One type means the same thing in every workflow, UI surface, agent tool, and audit event.

Implementation: SQLAlchemy 2.0 in `packages/mira/core/models`. API/JSON shapes: Pydantic in `packages/mira/core/schemas` and `packages/mira/core/agent_outputs.py`.

Money is always `Decimal` / `Numeric(18, 2)` plus an ISO currency code. Never `float`.

Multi-tenancy: almost every row has `company_id`. The demo tenant is Northstar Labs with a stable UUID.

---

## Invariants

1. **Canonical objects are not duplicated per workflow.** Procurement, AP, and audit all point at the same `Invoice` id.
2. **A `Decision` is the only way Mira proposes a material action.** It must include evidence references, confidence, risk level, policy basis, and authority basis. Application code should reject incomplete decisions.
3. **`AuditEvent` is append-only.** No updates, no deletes from application repositories.
4. **Sandbox money is infectious.** If a `Payment` is sandbox, related `Transaction` rows are sandbox. UI must label them.
5. **Risk scores come from `RiskAssessment.engine_version`**, not from free-text.
6. **Ledger entries for a `Transaction` must balance** (sum of debits = sum of credits). Enforced later in `packages/mira/finance`, not by an LLM.
7. **EvidenceReference can sit in JSON or as a row** (`evidence_references`). The Pydantic shape is identical.

---

## Shared value types (not tables)

### Money

| Field | Type | Notes |
| --- | --- | --- |
| amount | Decimal | Major units, 2-decimal quantize |
| currency | str | ISO 4217, default `USD` |

### Confidence

| Field | Type | Notes |
| --- | --- | --- |
| score | Decimal | 0–1 inclusive |
| basis | str | Why the score is that high/low |
| model | str \| null | Optional model id; engines leave this null |

### EvidenceReference

| Field | Type | Notes |
| --- | --- | --- |
| evidence_id | UUID \| null | When materialized as an `Evidence` row |
| object_type | str | `invoice`, `document`, `transaction`, `policy`, `contract`, `signal`, … |
| object_id | UUID \| null | Canonical object |
| source_system | str | `dropbox`, `local`, `ledger`, `elastic`, `public_data`, `seed` |
| locator | str \| null | `page:3`, `field:total`, `clause:5.2`, `series:DGS3MO` |
| uri | str \| null | File or URL |
| excerpt | str \| null | Short quote |
| content_hash | str \| null | SHA-256 of bytes or canonical JSON |
| captured_at | datetime \| null | |
| role | str | `supporting`, `contradicting`, `policy_basis`, `authority_basis` |

---

## Core parties

### Company

The tenant. Demo: Northstar Labs.

| Field | Type |
| --- | --- |
| id | UUID |
| slug | str unique |
| name | str |
| legal_name | str |
| industry | str |
| stage | str |
| fiscal_year_start_month | int |
| base_currency | str |
| timezone | str |
| employee_count | int \| null |
| description | text \| null |
| created_at | datetime |

### User

A human who can approve, override, or view.

| Field | Type |
| --- | --- |
| id | UUID |
| company_id | UUID FK |
| email | str |
| full_name | str |
| role | enum `UserRole`: `admin`, `cfo`, `controller`, `ap`, `executive`, `auditor` |
| is_active | bool |
| created_at | datetime |

### Employee

Workforce / org chart. May or may not have a `User`.

| Field | Type |
| --- | --- |
| id | UUID |
| company_id | UUID FK |
| user_id | UUID FK \| null |
| employee_number | str |
| full_name | str |
| title | str |
| department | str |
| cost_center | str \| null |
| manager_id | UUID FK self \| null |
| hire_date | date \| null |
| status | enum `EmployeeStatus` |
| created_at | datetime |

### Vendor

| Field | Type |
| --- | --- |
| id | UUID |
| company_id | UUID FK |
| name | str |
| tax_id | str \| null |
| email | str \| null |
| payment_terms | str \| null |
| default_currency | str |
| risk_tier | enum `RiskTier` |
| status | enum `PartyStatus` |
| is_preferred | bool |
| notes | text \| null |
| created_at | datetime |

### Customer

Symmetric to vendor for AR. Same status/risk pattern.

---

## Ledger

### Account

Chart of accounts.

| Field | Type |
| --- | --- |
| id | UUID |
| company_id | UUID FK |
| code | str |
| name | str |
| account_type | enum `AccountType`: `asset`, `liability`, `equity`, `revenue`, `expense` |
| parent_id | UUID FK self \| null |
| currency | str |
| is_active | bool |
| is_cash | bool |

Unique `(company_id, code)`.

### Transaction

Bank, card, sandbox, or manual movement. Not a ledger line.

| Field | Type |
| --- | --- |
| id | UUID |
| company_id | UUID FK |
| account_id | UUID FK |
| vendor_id | UUID FK \| null |
| customer_id | UUID FK \| null |
| amount | Numeric(18,2) |
| currency | str |
| posted_at | datetime |
| description | str |
| source | enum `TransactionSource`: `bank`, `card`, `sandbox`, `manual`, `seed` |
| external_ref | str \| null |
| is_sandbox | bool |
| document_id | UUID FK \| null |

### LedgerEntry

Journal line. A transaction's entries must balance.

| Field | Type |
| --- | --- |
| id | UUID |
| company_id | UUID FK |
| transaction_id | UUID FK \| null |
| account_id | UUID FK |
| debit | Numeric(18,2) |
| credit | Numeric(18,2) |
| period | str | `YYYY-MM` |
| memo | str \| null |

---

## Procure-to-pay / order-to-cash

### Budget / BudgetLine

Period envelope used by procurement checks.

| Budget | Type |
| --- | --- |
| id, company_id | UUID |
| name | str |
| period | str |
| currency | str |
| owner_employee_id | UUID \| null |

| BudgetLine | Type |
| --- | --- |
| id, budget_id, account_id | UUID |
| amount | Numeric |
| spent_amount | Numeric | maintained by engines, not LLMs |

### PurchaseOrder / PurchaseOrderLine

| PO | Type |
| --- | --- |
| id, company_id, vendor_id | UUID |
| po_number | str |
| status | enum `POStatus` |
| currency | str |
| requested_by_user_id | UUID \| null |
| needed_by | date \| null |
| total | Numeric |
| budget_id | UUID \| null |
| notes | text \| null |

Lines: description, qty, unit_price, amount, account_id.

### GoodsReceipt / GoodsReceiptLine

Warehouse/receipt against a PO. Required for 3-way match.

### Invoice / InvoiceLine

AP or AR.

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| vendor_id / customer_id | UUID \| null |
| invoice_number | str |
| direction | enum `InvoiceDirection`: `ap`, `ar` |
| issue_date, due_date | date |
| currency | str |
| subtotal, tax_total, total | Numeric |
| status | enum `InvoiceStatus` |
| purchase_order_id | UUID \| null |
| document_id | UUID \| null |
| is_duplicate_suspect | bool |

Line amounts must sum to `subtotal` (engine-enforced).

### Payment

| Field | Type |
| --- | --- |
| id, company_id, invoice_id | UUID |
| amount, currency | money |
| method | enum `PaymentMethod` including `visa_sandbox` |
| status | enum `PaymentStatus` |
| is_sandbox | bool **required true for hackathon Visa path** |
| processor_ref | str \| null |
| paid_at | datetime \| null |
| transaction_id | UUID \| null |

---

## Documents, contracts, policy

### Document

Ingested file (Dropbox or local inbox).

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| filename | str |
| mime_type | str |
| storage_backend | enum `StorageBackend`: `local`, `dropbox` |
| storage_uri | str |
| document_class | enum `DocumentClass`: `invoice`, `receipt`, `contract`, `statement`, `policy`, `other` |
| extraction_status | enum |
| content_hash | str \| null |
| ingested_at | datetime |
| raw_text | text \| null | demo/extracted text |

### Contract

| Field | Type |
| --- | --- |
| id, company_id, vendor_id, document_id | UUID |
| title | str |
| start_date, end_date | date \| null |
| value | Numeric \| null |
| currency | str |
| status | enum `ContractStatus` |
| extracted_terms | JSON | structured term sheet |

### Policy

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| name | str |
| policy_type | enum `PolicyType`: `spend`, `approval`, `vendor`, `treasury`, `data` |
| version | str |
| body | text |
| rules | JSON | deterministic rule payload |
| effective_at | datetime |
| status | enum `PolicyStatus` |
| document_id | UUID \| null |

---

## Control plane

### Evidence

Materialized evidence object.

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| evidence_type | str |
| source_system | str |
| uri | str \| null |
| title | str |
| snippet | text \| null |
| content_hash | str \| null |
| extra | JSON |

### EvidenceReference (table `evidence_references`)

Row form of the value type, attaching evidence to any object (`object_type`, `object_id`).

### Finding

Something the office noticed: duplicate, overdue, clause conflict, anomaly.

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| finding_type | str |
| severity | enum `Severity` |
| title, description | str / text |
| status | enum `FindingStatus` |
| related_object_type, related_object_id | str / UUID \| null |

### Incident

Group of findings (optional escalation container). M2M via `incident_findings`.

### RiskAssessment

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| subject_type, subject_id | str / UUID |
| risk_level | enum `RiskLevel` |
| risk_score | Numeric | 0–100, **engine-computed** |
| factors | JSON | list of `{code, points, note}` |
| engine_version | str |
| assessed_at | datetime |

### Decision

Mira's (or a specialist's, via Mira) proposed or executed action.

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| decision_type | str |
| status | enum `DecisionStatus` |
| action | str |
| rationale | text | human-readable, not the only payload |
| structured_output | JSON | typed agent output |
| confidence_score | Numeric 0–1 |
| risk_level | enum |
| policy_basis | str |
| authority_basis | str |
| requires_human_approval | bool |
| agent_run_id | UUID \| null |
| subject_type, subject_id | str / UUID \| null |
| dollars_impact | Numeric \| null |
| hours_saved_estimate | Numeric \| null |

### Approval

Human gate for a decision or other subject.

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| subject_type, subject_id | str / UUID |
| requested_by_user_id | UUID \| null |
| approver_user_id | UUID \| null |
| status | enum `ApprovalStatus` |
| decision_id | UUID \| null |
| risk_level | enum |
| confidence_score | Numeric \| null |
| decided_at | datetime \| null |
| comment | text \| null |

### Precedent

Memory across periods.

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| situation_hash | str |
| decision_id | UUID \| null |
| summary | text |
| outcome | str |
| period | str |
| reusable_rule | text \| null |

### Forecast

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| metric_name | str |
| period | str |
| method | str | e.g. `linear_13w`, `seasonal_naive` |
| value, lower, upper | Numeric |
| currency | str \| null |
| inputs_hash | str |
| engine_version | str |

### Metric

Point-in-time measured or computed value (including Ramp scoreboard inputs).

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| name | str |
| period | str |
| value | Numeric |
| unit | str | `usd`, `hours`, `ratio`, `count` |
| source | enum `MetricSource`: `computed`, `external`, `seed` |

### SavingsEvent

Ramp-facing, workflow-authored.

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| category | enum `SavingsCategory` |
| amount_usd | Numeric |
| hours_saved | Numeric |
| workflow | str |
| period | str |
| related_object_type / id | str / UUID \| null |
| note | text \| null |

### ExternalSignal

Voloridge-facing public data.

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| source | str | `FRED`, `Treasury`, `seed` |
| series_id | str |
| as_of | date |
| value | Numeric |
| unit | str |
| title | str |
| note | text \| null |
| uri | str \| null |

### ReconciliationCase

Placeholder for AP/bank matching work (engine comes later).

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| case_type | str | `three_way`, `bank`, `duplicate` |
| status | enum |
| payload | JSON |

---

## Agent plane

### AgentRun

A long-horizon or request-scoped body of work Mira owns.

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| workflow_type | str | `ap_intake`, `procurement`, `close`, `briefing` |
| status | enum `AgentRunStatus` |
| initiated_by | enum `ActorType` |
| initiator_id | str \| null |
| plan | JSON |
| started_at, completed_at | datetime \| null |

### AgentTask

| Field | Type |
| --- | --- |
| id, company_id, agent_run_id | UUID |
| agent_role | enum `AgentRole` |
| parent_task_id | UUID \| null |
| status | enum `AgentTaskStatus` |
| input_payload | JSON | must match a known schema name |
| result_type | str \| null |
| result_payload | JSON \| null | `AgentTaskResult` |
| started_at, completed_at | datetime \| null |

**No agent runtime writes these in this slice.** Seeded rows show the shape the UI and future runtime will use.

---

## Audit

### AuditEvent

| Field | Type |
| --- | --- |
| id, company_id | UUID |
| occurred_at | datetime | server clock |
| actor_type | enum `ActorType` |
| actor_id | str \| null |
| event_type | str |
| object_type, object_id | str / UUID \| null |
| correlation_id | UUID \| null | usually `agent_run_id` |
| payload | JSON | no secrets |

Repository rule: `insert()` only.

---

## Typed agent outputs (JSON, not tables)

Defined in `packages/mira/core/agent_outputs.py`. Persisted on `Decision.structured_output` and `AgentTask.result_payload`.

| Type | Purpose |
| --- | --- |
| `RiskFinding` | Factor-level finding; score still comes from the risk engine |
| `ReconciliationResult` | Match / mismatch / duplicate with ids and amounts |
| `InvoiceDecision` | Pay / hold / reject / escalate + computed totals |
| `AuditFinding` | Control exception with clause locators |
| `AgentTaskResult` | Envelope: role, status, artifacts, errors |
| `CFORecommendation` | Mira's user-facing recommendation |
| `HumanEscalation` | Why a human is required, question asked, due |

All include `evidence: list[EvidenceReference]`.

---

## Northstar Labs seed (stable ids)

The seed module uses fixed UUIDs so tests and UI fixtures can assert identity:

- Company slug `northstar-labs`
- Users: Elena Voss (CFO), Jordan Hale (Controller), Sam Okonkwo (AP)
- Vendors: HelixCloud, Apex Scientific Supply, plus others
- Duplicate AP pair on HelixCloud (~$18,400)
- Overdue Apex invoice
- GPU procurement PO awaiting dual approval (~$67,000)
- Savings events and public-data signals
- Messy `data/demo/inbox` filenames

See `packages/mira/seed/northstar.py`.

---

## Entity relationship (logical)

```
Company
  ├── User / Employee
  ├── Vendor / Customer
  ├── Account → Transaction → LedgerEntry
  ├── Budget → BudgetLine
  ├── PurchaseOrder → POLine → GoodsReceipt → GRLine
  ├── Invoice → InvoiceLine → Payment
  ├── Document → Contract / Policy
  ├── Evidence → EvidenceReference → (any object)
  ├── Finding → Incident
  ├── RiskAssessment
  ├── Decision → Approval
  ├── AgentRun → AgentTask
  ├── Precedent / Forecast / Metric / SavingsEvent / ExternalSignal
  └── AuditEvent (append-only)
```
