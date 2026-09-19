"""Invoice vs purchase order vs goods receipt. Deterministic."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from mira.core.agent_outputs import Confidence, EvidenceReference
from mira.core.enums import MatchStatus
from mira.core.money import Money, quantize_money
from mira.finance.normalize import near_invoice_number
from mira.finance.snapshot import FinanceSnapshot, InvoiceView
from mira.policies.engine import evaluate_invoice
from mira.reconciliation.types import ThreeWayMatchResult

AMOUNT_TOLERANCE = Decimal("0.00")
PARTIAL_TOLERANCE = Decimal("0.02")  # 2% of PO → PARTIAL_MATCH, not MATCH


def _money(amount: Decimal, currency: str = "USD") -> Money:
    return Money(amount=quantize_money(amount), currency=currency)


def _line_amount(quantity: Decimal, unit_price: Decimal | None, amount: Decimal | None) -> Decimal:
    if amount is not None:
        return quantize_money(amount)
    if unit_price is not None:
        return quantize_money(quantity * unit_price)
    return quantize_money(Decimal("0"))


def _duplicate_ids(snapshot: FinanceSnapshot, invoice: InvoiceView) -> tuple[UUID, ...]:
    if invoice.vendor_id is None:
        return ()
    found: list[UUID] = []
    for other in snapshot.ap_invoices():
        if other.id == invoice.id or other.vendor_id != invoice.vendor_id:
            continue
        if abs(other.total - invoice.total) > Decimal("1.00"):
            continue
        if abs((other.issue_date - invoice.issue_date).days) > 14:
            continue
        if near_invoice_number(other.invoice_number, invoice.invoice_number):
            found.append(other.id)
    return tuple(found)


def match_invoice(snapshot: FinanceSnapshot, invoice_id: UUID) -> ThreeWayMatchResult:
    invoice = snapshot.invoice(invoice_id)
    if invoice is None:
        raise KeyError(invoice_id)
    currency = invoice.currency
    po = snapshot.purchase_order(invoice.purchase_order_id)
    receipts = snapshot.receipts_for_po(po.id) if po else ()
    evidence: list[EvidenceReference] = [
        EvidenceReference(
            object_type="invoice",
            object_id=invoice.id,
            source_system="seed",
            locator="field:total",
            excerpt=str(invoice.total),
        )
    ]
    duplicates = _duplicate_ids(snapshot, invoice)
    policy = evaluate_invoice(snapshot, invoice.id)
    violated = policy.violated_policy_ids if policy else ()

    if po is None:
        return ThreeWayMatchResult(
            invoice_id=invoice.id,
            po_id=None,
            receipt_ids=(),
            status=MatchStatus.MISSING_EVIDENCE,
            invoice_total=_money(invoice.total, currency),
            duplicate_invoice_ids=duplicates,
            violated_policy_ids=violated,
            confidence=Confidence(
                score=Decimal("0.99"),
                basis="Purchase order id is null on the invoice row; missing evidence is observed, not inferred.",
            ),
            evidence=evidence,
            explanation="No purchase order is linked to this invoice. Three-way match cannot proceed.",
        )

    evidence.append(
        EvidenceReference(
            object_type="purchase_order",
            object_id=po.id,
            source_system="seed",
            locator="field:total",
            excerpt=str(po.total),
        )
    )
    receipt_ids = tuple(row.id for row in receipts)
    received_amount = Decimal("0.00")
    if receipts:
        for receipt in receipts:
            evidence.append(
                EvidenceReference(
                    object_type="goods_receipt",
                    object_id=receipt.id,
                    source_system="seed",
                    locator="field:quantity",
                    excerpt=str(sum((line.quantity for line in receipt.lines), Decimal("0"))),
                )
            )
            po_price_by_line = {line.id: line.unit_price or Decimal("0") for line in po.lines}
            if receipt.lines:
                for line in receipt.lines:
                    price = po_price_by_line.get(line.purchase_order_line_id or UUID(int=0), None)
                    if price is None:
                        # Fall back to PO total / PO qty so a header-only receipt still values.
                        po_qty = sum((pl.quantity for pl in po.lines), Decimal("0")) or Decimal("1")
                        price = po.total / po_qty
                    received_amount += line.quantity * price
            else:
                received_amount += po.total
        received_amount = quantize_money(received_amount)
    else:
        return ThreeWayMatchResult(
            invoice_id=invoice.id,
            po_id=po.id,
            receipt_ids=(),
            status=MatchStatus.MISSING_EVIDENCE,
            invoice_total=_money(invoice.total, currency),
            po_total=_money(po.total, currency),
            duplicate_invoice_ids=duplicates,
            violated_policy_ids=violated,
            confidence=Confidence(
                score=Decimal("0.99"),
                basis="Purchase order exists and no goods receipt rows exist for that PO.",
            ),
            evidence=evidence,
            explanation=f"PO {po.po_number} is present but no goods receipt has been posted. Match is not forced.",
        )

    delta = quantize_money(invoice.total - po.total)
    vendor_mismatch = invoice.vendor_id is not None and invoice.vendor_id != po.vendor_id
    billed_qty = sum((line.quantity for line in invoice.lines), Decimal("0"))
    po_qty = sum((line.quantity for line in po.lines), Decimal("0"))
    received_qty = sum((line.quantity for rec in receipts for line in rec.lines), Decimal("0"))

    if vendor_mismatch or invoice.total > po.total or (received_qty and billed_qty > received_qty):
        status = MatchStatus.MISMATCH
        basis = "Invoice amount or quantity exceeds PO/receipt on complete numeric fields."
        score = Decimal("0.99")
        explanation = (
            f"MISMATCH: invoice {invoice.total} vs PO {po.total} (delta {delta}); "
            f"billed qty {billed_qty} vs received qty {received_qty}."
        )
    elif invoice.total < po.total and po.total != 0 and (po.total - invoice.total) / po.total <= PARTIAL_TOLERANCE:
        status = MatchStatus.PARTIAL_MATCH
        basis = "Amounts differ within the 2% partial window on complete documents."
        score = Decimal("0.90")
        explanation = f"PARTIAL_MATCH: invoice {invoice.total} vs PO {po.total} within 2%."
    elif invoice.total != po.total or (received_qty and billed_qty != received_qty):
        status = MatchStatus.PARTIAL_MATCH
        basis = "Documents exist but quantities or amounts are not identical."
        score = Decimal("0.88")
        explanation = (
            f"PARTIAL_MATCH: invoice {invoice.total} vs PO {po.total}; "
            f"billed qty {billed_qty} vs received {received_qty}."
        )
    else:
        status = MatchStatus.MATCH
        basis = "Vendor, amount, and received quantity agree exactly."
        score = Decimal("0.99")
        explanation = f"MATCH: invoice {invoice.invoice_number} equals PO {po.po_number} and goods receipt."

    if duplicates:
        explanation += f" Duplicate invoice candidates: {len(duplicates)}."
    if violated:
        explanation += f" Policy violations: {', '.join(violated)}."

    return ThreeWayMatchResult(
        invoice_id=invoice.id,
        po_id=po.id,
        receipt_ids=receipt_ids,
        status=status,
        invoice_total=_money(invoice.total, currency),
        po_total=_money(po.total, currency),
        received_amount=_money(received_amount, currency),
        amount_delta=_money(delta, currency),
        duplicate_invoice_ids=duplicates,
        violated_policy_ids=violated,
        confidence=Confidence(score=score, basis=basis),
        evidence=evidence,
        explanation=explanation,
    )


def match_all_ap(snapshot: FinanceSnapshot) -> tuple[ThreeWayMatchResult, ...]:
    return tuple(match_invoice(snapshot, inv.id) for inv in snapshot.ap_invoices())
