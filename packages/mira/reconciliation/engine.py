"""Bank-to-invoice reconciliation in ordered stages. Never force a match."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from itertools import combinations
from uuid import UUID

from mira.core.agent_outputs import Confidence, EvidenceReference
from mira.core.enums import ReconStage
from mira.core.money import quantize_money
from mira.finance.normalize import normalize_reference
from mira.finance.snapshot import FinanceSnapshot, InvoiceView, TransactionView
from mira.reconciliation.types import ReconciliationReport, ReconMatch

ENGINE_VERSION = "recon-1"

FUZZY_AMOUNT = Decimal("1.00")
FUZZY_DAYS = 3
KNOWN_FEES = (
    Decimal("0.25"),
    Decimal("1.50"),
    Decimal("15.00"),
    Decimal("25.00"),
)
CARD_FEE_PCT = Decimal("0.029")
ONE_TO_MANY_MAX = 6


def _party_compatible(txn: TransactionView, invoice: InvoiceView) -> bool:
    if txn.vendor_id and invoice.vendor_id == txn.vendor_id:
        return True
    if txn.customer_id and invoice.customer_id == txn.customer_id:
        return True
    if txn.vendor_id is None and txn.customer_id is None:
        return True
    return False


def _abs_amount(txn: TransactionView) -> Decimal:
    return quantize_money(txn.amount.copy_abs())


def _is_refund(txn: TransactionView) -> bool:
    blob = f"{txn.description} {txn.external_ref or ''}".upper()
    return "REFUND" in blob or "CHARGEBACK" in blob or txn.amount > 0 and "CREDIT" in blob


def _txn_evidence(txn: TransactionView) -> EvidenceReference:
    return EvidenceReference(
        object_type="transaction",
        object_id=txn.id,
        source_system="seed",
        locator=f"ref:{txn.external_ref or txn.id}",
        excerpt=f"{txn.description} {txn.amount}",
    )


def _inv_evidence(invoice: InvoiceView) -> EvidenceReference:
    return EvidenceReference(
        object_type="invoice",
        object_id=invoice.id,
        source_system="seed",
        locator=f"invoice:{invoice.invoice_number}",
        excerpt=str(invoice.total),
    )


def _match(
    txn: TransactionView,
    invoices: Iterable[InvoiceView],
    stage: ReconStage,
    delta: Decimal,
    score: Decimal,
    basis: str,
    explanation: str,
) -> ReconMatch:
    invoices = tuple(invoices)
    return ReconMatch(
        transaction_id=txn.id,
        counterpart_ids=tuple(inv.id for inv in invoices),
        counterpart_type="invoice",
        stage=stage,
        amount_delta=quantize_money(delta),
        confidence=Confidence(score=score, basis=basis),
        evidence=[_txn_evidence(txn), *(_inv_evidence(inv) for inv in invoices)],
        explanation=explanation,
        forced=False,
    )


def _unresolved(txn: TransactionView, note: str) -> ReconMatch:
    return ReconMatch(
        transaction_id=txn.id,
        counterpart_ids=(),
        counterpart_type="invoice",
        stage=ReconStage.UNRESOLVED,
        amount_delta=_abs_amount(txn),
        confidence=Confidence(
            score=Decimal("0.99"),
            basis="No allowed stage produced a match; the engine refused to force one.",
        ),
        evidence=[_txn_evidence(txn)],
        explanation=note,
        forced=False,
    )


def reconcile(snapshot: FinanceSnapshot) -> ReconciliationReport:
    """Match bank transactions to AP/AR invoices through seven exclusive stages."""
    bank = [txn for txn in snapshot.bank_transactions()]
    invoices = list(snapshot.invoices)
    used_tx: set[UUID] = set()
    used_inv: set[UUID] = set()
    matches: list[ReconMatch] = []

    def open_invoices() -> list[InvoiceView]:
        return [inv for inv in invoices if inv.id not in used_inv]

    # 1. Exact one-to-one: amount and (optional) same-day + vendor.
    for txn in bank:
        if txn.id in used_tx:
            continue
        amt = _abs_amount(txn)
        candidates = [
            inv
            for inv in open_invoices()
            if inv.total == amt and _party_compatible(txn, inv)
        ]
        exact = [
            inv
            for inv in candidates
            if txn.posted_at.date() == inv.issue_date
            or (inv.due_date and txn.posted_at.date() == inv.due_date)
            or (txn.external_ref and normalize_reference(txn.external_ref) == normalize_reference(inv.invoice_number))
        ]
        pick = exact[0] if len(exact) == 1 else (candidates[0] if len(candidates) == 1 else None)
        if pick is None:
            continue
        used_tx.add(txn.id)
        used_inv.add(pick.id)
        matches.append(
            _match(
                txn,
                [pick],
                ReconStage.EXACT_ONE_TO_ONE,
                Decimal("0.00"),
                Decimal("0.99"),
                "Single invoice total equals bank amount exactly.",
                f"Exact one-to-one: {txn.id} ↔ invoice {pick.invoice_number} for {amt}.",
            )
        )

    # 2. Normalized reference match (amount may still need to equal).
    for txn in bank:
        if txn.id in used_tx or not txn.external_ref:
            continue
        ref = normalize_reference(txn.external_ref)
        desc = normalize_reference(txn.description)
        hits = [
            inv
            for inv in open_invoices()
            if normalize_reference(inv.invoice_number) and (
                normalize_reference(inv.invoice_number) in ref
                or ref in normalize_reference(inv.invoice_number)
                or normalize_reference(inv.invoice_number) in desc
            )
        ]
        if len(hits) == 1 and hits[0].total == _abs_amount(txn):
            used_tx.add(txn.id)
            used_inv.add(hits[0].id)
            matches.append(
                _match(
                    txn,
                    hits,
                    ReconStage.NORMALIZED_REFERENCE,
                    Decimal("0.00"),
                    Decimal("0.95"),
                    "Normalized bank reference contains the invoice number and amounts agree.",
                    f"Normalized reference match on {txn.external_ref} → {hits[0].invoice_number}.",
                )
            )

    # 3. Amount/date fuzzy (NOT used for deltas above FUZZY_AMOUNT).
    for txn in bank:
        if txn.id in used_tx:
            continue
        amt = _abs_amount(txn)
        hits = []
        for inv in open_invoices():
            if not _party_compatible(txn, inv):
                continue
            if abs(inv.total - amt) > FUZZY_AMOUNT:
                continue
            days = abs((txn.posted_at.date() - inv.issue_date).days)
            if days > FUZZY_DAYS:
                continue
            hits.append(inv)
        if len(hits) == 1:
            delta = quantize_money(hits[0].total - amt)
            used_tx.add(txn.id)
            used_inv.add(hits[0].id)
            matches.append(
                _match(
                    txn,
                    hits,
                    ReconStage.AMOUNT_DATE_FUZZY,
                    delta,
                    Decimal("0.72"),
                    f"Single candidate within ${FUZZY_AMOUNT} and {FUZZY_DAYS} days; match is not forced beyond that window.",
                    f"Fuzzy amount/date match to {hits[0].invoice_number} (delta {delta}).",
                )
            )

    # 4. One bank transaction to several invoices (exact subset sum).
    for txn in bank:
        if txn.id in used_tx:
            continue
        amt = _abs_amount(txn)
        pool = [
            inv
            for inv in open_invoices()
            if (txn.vendor_id is None or inv.vendor_id == txn.vendor_id)
            and inv.direction == "ap"
            and inv.total <= amt
        ]
        chosen: tuple[InvoiceView, ...] | None = None
        pool = pool[:12]
        for size in range(2, min(ONE_TO_MANY_MAX, len(pool)) + 1):
            for combo in combinations(pool, size):
                if sum((inv.total for inv in combo), Decimal("0.00")) == amt:
                    chosen = combo
                    break
            if chosen:
                break
        if chosen:
            used_tx.add(txn.id)
            for inv in chosen:
                used_inv.add(inv.id)
            matches.append(
                _match(
                    txn,
                    chosen,
                    ReconStage.ONE_TO_MANY,
                    Decimal("0.00"),
                    Decimal("0.93"),
                    "Exact subset of open invoices sums to the bank amount.",
                    "One bank transaction covers "
                    + ", ".join(inv.invoice_number for inv in chosen)
                    + f" totaling {amt}.",
                )
            )

    # 5. Fee-adjusted matches.
    for txn in bank:
        if txn.id in used_tx:
            continue
        amt = _abs_amount(txn)
        hits: list[InvoiceView] = []
        for inv in open_invoices():
            delta = abs(inv.total - amt)
            pct = abs(inv.total * CARD_FEE_PCT - delta)
            if delta in KNOWN_FEES or pct <= Decimal("0.05"):
                if not _party_compatible(txn, inv):
                    continue
                hits.append(inv)
        if len(hits) == 1:
            delta = quantize_money(hits[0].total - amt)
            used_tx.add(txn.id)
            used_inv.add(hits[0].id)
            matches.append(
                _match(
                    txn,
                    hits,
                    ReconStage.FEE_ADJUSTED,
                    delta,
                    Decimal("0.84"),
                    "Amount difference equals a known fee schedule entry or card percentage.",
                    f"Fee-adjusted match to {hits[0].invoice_number} (delta {delta}).",
                )
            )

    # 6. Known refund / chargeback handling.
    for txn in bank:
        if txn.id in used_tx or not _is_refund(txn):
            continue
        amt = _abs_amount(txn)
        hits = [
            inv
            for inv in open_invoices()
            if inv.total == amt
            and (
                "refund" in inv.invoice_number.lower()
                or "cr" in inv.invoice_number.lower()
                or inv.status in {"void", "rejected"}
                or (txn.vendor_id and inv.vendor_id == txn.vendor_id)
            )
        ]
        if len(hits) == 1:
            used_tx.add(txn.id)
            used_inv.add(hits[0].id)
            matches.append(
                _match(
                    txn,
                    hits,
                    ReconStage.REFUND_CHARGEBACK,
                    Decimal("0.00"),
                    Decimal("0.90"),
                    "Refund/chargeback marker on the bank transaction equals one credit/refund invoice.",
                    f"Refund/chargeback matched to {hits[0].invoice_number}.",
                )
            )

    # 7. Unresolved exception — never force.
    unresolved: list[ReconMatch] = []
    for txn in bank:
        if txn.id in used_tx:
            continue
        unresolved.append(
            _unresolved(
                txn,
                "Unresolved exception: no exact, reference, fuzzy, one-to-many, fee, or refund stage matched. Match was not forced.",
            )
        )

    matched_tx = tuple(used_tx)
    matched_inv = tuple(used_inv)
    denom = Decimal(len(bank)) if bank else Decimal("1")
    rate = quantize_money(Decimal(len(matched_tx)) / denom)
    return ReconciliationReport(
        matches=tuple(matches),
        unresolved=tuple(unresolved),
        matched_transaction_ids=matched_tx,
        matched_invoice_ids=matched_inv,
        reconciliation_rate=rate,
        explanation=(
            f"{len(matches)} matched bank transaction(s), {len(unresolved)} unresolved, "
            f"reconciliation_rate={rate}. Matches were never forced."
        ),
    )
