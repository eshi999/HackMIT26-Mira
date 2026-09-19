# Reconciliation

Duplicate detection, PO–receipt–invoice three-way match, bank match.

Inputs and outputs are canonical objects plus `ThreeWayMatchResult` / `ReconciliationReport`.

Three-way statuses: `MATCH`, `PARTIAL_MATCH`, `MISMATCH`, `MISSING_EVIDENCE`.

Bank reconciliation stages (never force a match):

1. exact one-to-one
2. normalized reference
3. amount/date fuzzy (≤ $1 and 3 days)
4. one bank transaction to several invoices
5. fee-adjusted
6. refund/chargeback
7. unresolved exception
