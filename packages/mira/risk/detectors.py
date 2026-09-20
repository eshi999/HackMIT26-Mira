"""Deterministic detection rules. Each function returns zero or more TypedFindings."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from uuid import UUID, uuid5

from mira.core.enums import FindingType
from mira.core.money import Money, quantize_money
from mira.finance.contracts import compare_invoice_to_contract, facts_from_extracted
from mira.finance.normalize import is_round_amount, near_invoice_number, period_from_date
from mira.finance.snapshot import FinanceSnapshot, InvoiceView
from mira.policies.engine import is_new_vendor, po_required
from mira.risk.scoring import ENGINE_VERSION, confidence_for, risk_contribution, severity_for
from mira.risk.types import RelatedObject as Rel
from mira.risk.types import TypedFinding as Finding

FINDING_NS = UUID("aaaaaaaa-bbbb-cccc-dddd-000000000099")


def _fid(*parts: object) -> UUID:
    return uuid5(FINDING_NS, "|".join(str(p) for p in parts))


def _rel(*pairs: tuple[str, UUID, str | None]) -> tuple[Rel, ...]:
    return tuple(Rel(object_type=t, object_id=i, label=lbl) for t, i, lbl in pairs)


def _finding(
    *,
    finding_type: FindingType,
    title: str,
    description: str,
    amount: Decimal,
    related: tuple[Rel, ...],
    facts: dict,
    evidence_ids: tuple[UUID, ...] = (),
) -> Finding:
    points = risk_contribution(finding_type, amount)
    return Finding(
        id=_fid(finding_type.value, title, *(str(r.object_id) for r in related)),
        finding_type=finding_type,
        title=title,
        description=description,
        severity=severity_for(points),
        risk_contribution=points,
        confidence=confidence_for(finding_type),
        evidence_ids=evidence_ids,
        related_objects=related,
        facts=facts,
        detector_version=ENGINE_VERSION,
    )


def detect_duplicate_invoices(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[UUID, UUID]] = set()
    ap = snapshot.ap_invoices()
    for left in ap:
        if left.vendor_id is None:
            continue
        for right in ap:
            if right.id <= left.id or right.vendor_id != left.vendor_id:
                continue
            if abs(left.total - right.total) > Decimal("1.00"):
                continue
            if abs((left.issue_date - right.issue_date).days) > 14:
                continue
            if not near_invoice_number(left.invoice_number, right.invoice_number):
                continue
            key = (left.id, right.id)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                _finding(
                    finding_type=FindingType.DUPLICATE_INVOICE,
                    title=f"Duplicate invoice {left.invoice_number}/{right.invoice_number} ${left.total}",
                    description=(
                        f"Vendor invoices {left.invoice_number} and {right.invoice_number} share vendor, "
                        f"amount {left.total}, and near invoice numbers within 14 days."
                    ),
                    amount=left.total,
                    related=_rel(
                        ("invoice", left.id, left.invoice_number),
                        ("invoice", right.id, right.invoice_number),
                        ("vendor", left.vendor_id, None),
                    ),
                    facts={
                        "invoice_numbers": [left.invoice_number, right.invoice_number],
                        "amount": str(left.total),
                    },
                )
            )
    return findings


def detect_duplicate_payments(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    settled = [p for p in snapshot.payments if p.status in {"settled", "authorized"}]
    for i, left in enumerate(settled):
        for right in settled[i + 1 :]:
            same_invoice = left.invoice_id and left.invoice_id == right.invoice_id
            same_amount = left.amount == right.amount
            close = True
            if left.paid_at and right.paid_at:
                close = abs((left.paid_at - right.paid_at).days) <= 5
            if not (same_invoice and same_amount and close):
                continue
            related = _rel(("payment", left.id, None), ("payment", right.id, None))
            if left.invoice_id:
                related = related + _rel(("invoice", left.invoice_id, None))
            findings.append(
                _finding(
                    finding_type=FindingType.DUPLICATE_PAYMENT,
                    title=f"Duplicate payment ${left.amount}",
                    description=f"Payments {left.id} and {right.id} look like the same disbursement.",
                    amount=left.amount,
                    related=related,
                    facts={"amount": str(left.amount), "same_invoice": bool(same_invoice)},
                )
            )
    # Duplicated refunds: two inbound REFUND bank transactions, same amount, same vendor.
    refunds = [
        txn
        for txn in snapshot.bank_transactions()
        if "REFUND" in f"{txn.description} {txn.external_ref or ''}".upper()
    ]
    for i, left in enumerate(refunds):
        for right in refunds[i + 1 :]:
            if left.amount.copy_abs() != right.amount.copy_abs():
                continue
            if left.vendor_id and right.vendor_id and left.vendor_id != right.vendor_id:
                continue
            if abs((left.posted_at - right.posted_at).days) > 7:
                continue
            findings.append(
                _finding(
                    finding_type=FindingType.DUPLICATE_PAYMENT,
                    title=f"Duplicated refund ${left.amount.copy_abs()}",
                    description=f"Refund transactions {left.external_ref} and {right.external_ref} repeat the same amount.",
                    amount=left.amount.copy_abs(),
                    related=_rel(("transaction", left.id, left.external_ref), ("transaction", right.id, right.external_ref)),
                    facts={
                        "amount": str(left.amount.copy_abs()),
                        "kind": "refund",
                        "external_refs": [left.external_ref, right.external_ref],
                    },
                )
            )
    return findings


def detect_invoice_po_mismatch(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for invoice in snapshot.ap_invoices():
        po = snapshot.purchase_order(invoice.purchase_order_id)
        if po is None:
            continue
        if invoice.total <= po.total and invoice.vendor_id in {po.vendor_id, None}:
            continue
        findings.append(
            _finding(
                finding_type=FindingType.INVOICE_PO_MISMATCH,
                title=f"Invoice {invoice.invoice_number} exceeds PO {po.po_number}",
                description=f"Invoice {invoice.total} vs PO {po.total} (delta {invoice.total - po.total}).",
                amount=invoice.total,
                related=_rel(
                    ("invoice", invoice.id, invoice.invoice_number),
                    ("purchase_order", po.id, po.po_number),
                ),
                facts={
                    "invoice_total": str(invoice.total),
                    "po_total": str(po.total),
                    "delta": str(invoice.total - po.total),
                },
            )
        )
    return findings


def detect_invoice_gr_mismatch(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for invoice in snapshot.ap_invoices():
        po = snapshot.purchase_order(invoice.purchase_order_id)
        if po is None:
            continue
        receipts = snapshot.receipts_for_po(po.id)
        if not receipts:
            continue
        billed = sum((line.quantity for line in invoice.lines), Decimal("0"))
        received = sum((line.quantity for rec in receipts for line in rec.lines), Decimal("0"))
        if billed <= received and billed != 0:
            continue
        if billed == 0 and invoice.total <= po.total:
            continue
        findings.append(
            _finding(
                finding_type=FindingType.INVOICE_GR_MISMATCH,
                title=f"Invoice {invoice.invoice_number} vs goods receipt mismatch",
                description=f"Billed qty {billed} vs received qty {received}.",
                amount=invoice.total,
                related=_rel(("invoice", invoice.id, invoice.invoice_number), ("purchase_order", po.id, po.po_number)),
                facts={"billed_qty": str(billed), "received_qty": str(received)},
            )
        )
    return findings


def detect_missing_purchase_order(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for invoice in snapshot.ap_invoices():
        if not po_required(snapshot, invoice.id):
            continue
        findings.append(
            _finding(
                finding_type=FindingType.MISSING_PURCHASE_ORDER,
                title=f"Invoice {invoice.invoice_number} missing purchase order",
                description="AP invoice exceeds the PO-required threshold and has no purchase_order_id.",
                amount=invoice.total,
                related=_rel(("invoice", invoice.id, invoice.invoice_number)),
                facts={"invoice_number": invoice.invoice_number, "total": str(invoice.total)},
            )
        )
    return findings


def detect_new_vendor(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    rules = snapshot.merged_rules()
    window = int(rules.get("new_vendor_days", 30))
    for invoice in snapshot.ap_invoices():
        vendor = snapshot.vendor(invoice.vendor_id)
        if vendor is None or not is_new_vendor(vendor.onboarded_at, snapshot.as_of, window):
            continue
        findings.append(
            _finding(
                finding_type=FindingType.NEW_VENDOR,
                title=f"New vendor {vendor.name} on invoice {invoice.invoice_number}",
                description=f"{vendor.name} onboarded {vendor.onboarded_at}, within {window} days of {snapshot.as_of}.",
                amount=invoice.total,
                related=_rel(("vendor", vendor.id, vendor.name), ("invoice", invoice.id, invoice.invoice_number)),
                facts={"vendor": vendor.name, "onboarded_at": str(vendor.onboarded_at)},
            )
        )
    return findings


def detect_vendor_bank_detail_change(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for vendor in snapshot.vendors:
        if not vendor.bank_changed_at or not vendor.previous_bank_account_ref:
            continue
        related_invoices = [inv for inv in snapshot.ap_invoices() if inv.vendor_id == vendor.id]
        amount = related_invoices[0].total if related_invoices else Decimal("0")
        related = _rel(("vendor", vendor.id, vendor.name))
        for inv in related_invoices[:3]:
            related = related + _rel(("invoice", inv.id, inv.invoice_number))
        findings.append(
            _finding(
                finding_type=FindingType.VENDOR_BANK_DETAIL_CHANGE,
                title=f"Vendor bank details changed: {vendor.name}",
                description=(
                    f"{vendor.name} bank ref changed from {vendor.previous_bank_account_ref} "
                    f"to {vendor.bank_account_ref} at {vendor.bank_changed_at.date()}."
                ),
                amount=amount,
                related=related,
                facts={
                    "previous": vendor.previous_bank_account_ref,
                    "current": vendor.bank_account_ref,
                    "changed_at": vendor.bank_changed_at.isoformat(),
                },
            )
        )
    return findings


def detect_unusual_vendor_amount(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    by_vendor: dict[UUID, list[InvoiceView]] = defaultdict(list)
    for invoice in snapshot.ap_invoices():
        if invoice.vendor_id:
            by_vendor[invoice.vendor_id].append(invoice)
    for vendor_id, invoices in by_vendor.items():
        ordered = sorted(invoices, key=lambda r: r.issue_date)
        for idx, current in enumerate(ordered):
            history = [inv for inv in ordered[:idx] if inv.id != current.id]
            if len(history) < 2:
                continue
            mean = sum((inv.total for inv in history), Decimal("0.00")) / Decimal(len(history))
            if current.total > mean * Decimal("1.5") and current.total - mean > Decimal("1000"):
                vendor = snapshot.vendor(vendor_id)
                findings.append(
                    _finding(
                        finding_type=FindingType.UNUSUAL_VENDOR_AMOUNT,
                        title=f"Unusual amount {current.total} for {vendor.name if vendor else vendor_id}",
                        description=f"Invoice {current.invoice_number} is {current.total} vs trailing mean {quantize_money(mean)}.",
                        amount=current.total,
                        related=_rel(
                            ("invoice", current.id, current.invoice_number),
                            ("vendor", vendor_id, vendor.name if vendor else None),
                        ),
                        facts={
                            "amount": str(current.total),
                            "trailing_mean": str(quantize_money(mean)),
                            "invoice_number": current.invoice_number,
                        },
                    )
                )
    return findings


def detect_self_approved(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for approval in snapshot.approvals:
        if not approval.requested_by_user_id or not approval.approver_user_id:
            continue
        if approval.requested_by_user_id != approval.approver_user_id:
            continue
        amount = Decimal("0.00")
        related = _rel(("approval", approval.id, None))
        if approval.subject_type == "purchase_order":
            po = snapshot.purchase_order(approval.subject_id)
            if po:
                amount = po.total
                related = related + _rel(("purchase_order", po.id, po.po_number))
        elif approval.subject_type == "invoice":
            inv = snapshot.invoice(approval.subject_id)
            if inv:
                amount = inv.total
                related = related + _rel(("invoice", inv.id, inv.invoice_number))
        findings.append(
            _finding(
                finding_type=FindingType.SELF_APPROVED_REQUEST,
                title="Requester approved their own purchase",
                description="requested_by_user_id equals approver_user_id.",
                amount=amount,
                related=related,
                facts={
                    "requested_by_user_id": str(approval.requested_by_user_id),
                    "approver_user_id": str(approval.approver_user_id),
                    "subject_type": approval.subject_type,
                },
            )
        )
    return findings


def detect_approval_authority_exceeded(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    users = {u.id: u for u in snapshot.users}
    for approval in snapshot.approvals:
        if approval.approver_user_id is None:
            continue
        approver = users.get(approval.approver_user_id)
        if approver is None or approver.approval_limit is None:
            continue
        amount = Decimal("0.00")
        related = _rel(("approval", approval.id, approver.full_name))
        if approval.subject_type == "purchase_order":
            po = snapshot.purchase_order(approval.subject_id)
            if po:
                amount = po.total
                related = related + _rel(("purchase_order", po.id, po.po_number))
        elif approval.subject_type == "invoice":
            inv = snapshot.invoice(approval.subject_id)
            if inv:
                amount = inv.total
                related = related + _rel(("invoice", inv.id, inv.invoice_number))
        if amount <= approver.approval_limit:
            continue
        findings.append(
            _finding(
                finding_type=FindingType.APPROVAL_AUTHORITY_EXCEEDED,
                title=f"{approver.full_name} approved {amount} over limit {approver.approval_limit}",
                description="Approved amount exceeds the employee's approval_limit.",
                amount=amount,
                related=related,
                facts={
                    "approval_limit": str(approver.approval_limit),
                    "amount": str(amount),
                    "approver": approver.full_name,
                },
            )
        )
    return findings


def detect_missing_supporting_document(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    rules = snapshot.merged_rules()
    required_above = Decimal(str(rules.get("document_required_above", "0")))
    for invoice in snapshot.ap_invoices():
        if invoice.document_id is not None:
            continue
        if invoice.total <= required_above:
            continue
        findings.append(
            _finding(
                finding_type=FindingType.MISSING_SUPPORTING_DOCUMENT,
                title=f"Invoice {invoice.invoice_number} missing supporting document",
                description="AP invoice has no document_id.",
                amount=invoice.total,
                related=_rel(("invoice", invoice.id, invoice.invoice_number)),
                facts={"invoice_number": invoice.invoice_number},
            )
        )
    return findings


def detect_closed_period_posting(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    closed = set(snapshot.merged_rules().get("closed_periods", []))
    if not closed:
        return findings
    for invoice in snapshot.invoices:
        period = invoice.posted_period or period_from_date(invoice.issue_date)
        if period not in closed:
            continue
        findings.append(
            _finding(
                finding_type=FindingType.CLOSED_PERIOD_POSTING,
                title=f"Closed-period posting {invoice.invoice_number} in {period}",
                description=f"Invoice posted to closed period {period}.",
                amount=invoice.total,
                related=_rel(("invoice", invoice.id, invoice.invoice_number)),
                facts={"posted_period": period, "invoice_number": invoice.invoice_number},
            )
        )
    return findings


def detect_abnormal_transaction_timing(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for txn in snapshot.bank_transactions():
        posted = txn.posted_at
        weekend = posted.weekday() >= 5
        outside = posted.hour < 8 or posted.hour >= 18
        if not (weekend or outside):
            continue
        findings.append(
            _finding(
                finding_type=FindingType.ABNORMAL_TRANSACTION_TIMING,
                title=f"Abnormal timing {posted.isoformat()} {txn.description[:40]}",
                description="Bank transaction posted on a weekend or outside 08:00–18:00.",
                amount=txn.amount.copy_abs(),
                related=_rel(("transaction", txn.id, txn.external_ref)),
                facts={
                    "posted_at": posted.isoformat(),
                    "weekday": posted.weekday(),
                    "hour": posted.hour,
                    "amount": str(txn.amount),
                },
            )
        )
    return findings


def detect_contract_pricing_violation(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for contract in snapshot.contracts:
        terms = contract.extracted_terms or {}
        if "agreed_price" not in terms and "agreed_price_amount" not in terms:
            continue
        facts = facts_from_extracted(terms)
        if facts is None:
            continue
        for invoice in snapshot.ap_invoices():
            if invoice.vendor_id != contract.vendor_id:
                continue
            # Compare only invoices tagged as the contracted recurring charge, or matching the term sheet cadence.
            if terms.get("applies_invoice_numbers") and invoice.invoice_number not in terms["applies_invoice_numbers"]:
                continue
            if not terms.get("applies_invoice_numbers"):
                if invoice.total < facts.agreed_price.amount * Decimal("0.5"):
                    continue
                if invoice.total > facts.agreed_price.amount * Decimal("2"):
                    continue
            comparison = compare_invoice_to_contract(
                contract_id=contract.id,
                invoice_id=invoice.id,
                facts=facts,
                invoice_amount=Money(amount=invoice.total, currency=invoice.currency),
                invoice_date=invoice.issue_date,
            )
            if comparison.is_violation is not True:
                continue
            findings.append(
                _finding(
                    finding_type=FindingType.CONTRACT_PRICING_VIOLATION,
                    title=f"Contract pricing violation on {invoice.invoice_number}",
                    description=comparison.explanation,
                    amount=invoice.total,
                    related=_rel(
                        ("contract", contract.id, contract.title),
                        ("invoice", invoice.id, invoice.invoice_number),
                    ),
                    facts={
                        "increase_pct": str(comparison.increase_pct),
                        "allowed_annual_increase_pct": str(comparison.allowed_increase_pct),
                        "expected_price": str(comparison.expected_price.amount),
                        "actual_price": str(comparison.actual_price.amount),
                    },
                )
            )
    return findings


def detect_suspicious_round_number_payment(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for payment in snapshot.payments:
        if payment.status not in {"settled", "authorized", "pending"}:
            continue
        if not is_round_amount(payment.amount):
            continue
        related = _rel(("payment", payment.id, str(payment.amount)))
        if payment.invoice_id:
            related = related + _rel(("invoice", payment.invoice_id, None))
        findings.append(
            _finding(
                finding_type=FindingType.SUSPICIOUS_ROUND_NUMBER_PAYMENT,
                title=f"Round-number payment ${payment.amount}",
                description="Payment is a whole thousand with no cents.",
                amount=payment.amount,
                related=related,
                facts={"amount": str(payment.amount)},
            )
        )
    return findings


def detect_previously_flagged_vendor(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    flagged = {v.id: v for v in snapshot.vendors if v.risk_tier in {"watch", "high"}}
    for invoice in snapshot.ap_invoices():
        vendor = flagged.get(invoice.vendor_id) if invoice.vendor_id else None
        if vendor is None:
            continue
        # Avoid flooding: only current open/received invoices
        if invoice.status in {"paid", "void", "rejected"}:
            continue
        findings.append(
            _finding(
                finding_type=FindingType.PREVIOUSLY_FLAGGED_VENDOR,
                title=f"Flagged vendor {vendor.name} invoice {invoice.invoice_number}",
                description=f"Vendor risk_tier={vendor.risk_tier}.",
                amount=invoice.total,
                related=_rel(("vendor", vendor.id, vendor.name), ("invoice", invoice.id, invoice.invoice_number)),
                facts={"risk_tier": vendor.risk_tier, "vendor": vendor.name},
            )
        )
    return findings


def detect_unexpected_recurring_subscription(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    expected_vendors = {row.vendor_id for row in snapshot.subscriptions}
    # Recurring = 2+ AP invoices same vendor similar amount ~30 days apart, not in catalog.
    by_vendor: dict[UUID, list[InvoiceView]] = defaultdict(list)
    for invoice in snapshot.ap_invoices():
        if invoice.vendor_id:
            by_vendor[invoice.vendor_id].append(invoice)
    for vendor_id, invoices in by_vendor.items():
        if vendor_id in expected_vendors:
            continue
        if len(invoices) < 2:
            continue
        ordered = sorted(invoices, key=lambda r: r.issue_date)
        recurring = False
        for a, b in zip(ordered, ordered[1:], strict=False):
            days = abs((b.issue_date - a.issue_date).days)
            if 25 <= days <= 35 and abs(a.total - b.total) <= Decimal("5.00"):
                recurring = True
                break
        if not recurring:
            continue
        vendor = snapshot.vendor(vendor_id)
        latest = ordered[-1]
        findings.append(
            _finding(
                finding_type=FindingType.UNEXPECTED_RECURRING_SUBSCRIPTION,
                title=f"Unexpected recurring charges from {vendor.name if vendor else vendor_id}",
                description="Monthly-like charges exist with no expected subscription row.",
                amount=latest.total,
                related=_rel(("vendor", vendor_id, vendor.name if vendor else None), ("invoice", latest.id, latest.invoice_number)),
                facts={"invoice_numbers": [inv.invoice_number for inv in ordered], "amount": str(latest.total)},
            )
        )
    return findings


def detect_overdue_receivable(snapshot: FinanceSnapshot, *, min_days: int = 45) -> list[Finding]:
    findings: list[Finding] = []
    for invoice in snapshot.ar_invoices():
        if invoice.status in {"paid", "void"}:
            continue
        if invoice.due_date is None:
            continue
        days = (snapshot.as_of - invoice.due_date).days
        if days <= min_days:
            continue
        customer = next((c for c in snapshot.customers if c.id == invoice.customer_id), None)
        findings.append(
            _finding(
                finding_type=FindingType.OVERDUE_RECEIVABLE,
                title=f"AR {invoice.invoice_number} overdue {days} days",
                description=f"Customer {customer.name if customer else invoice.customer_id} is {days} days past due.",
                amount=invoice.total,
                related=_rel(("invoice", invoice.id, invoice.invoice_number))
                + (() if not invoice.customer_id else _rel(("customer", invoice.customer_id, customer.name if customer else None))),
                facts={"days_overdue": days, "due_date": str(invoice.due_date), "invoice_number": invoice.invoice_number},
            )
        )
    return findings


def detect_unused_recurring_charge(snapshot: FinanceSnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for sub in snapshot.subscriptions:
        if sub.is_in_use:
            continue
        charges = [
            inv
            for inv in snapshot.ap_invoices()
            if inv.vendor_id == sub.vendor_id and abs(inv.total - sub.expected_amount) <= Decimal("5.00")
        ]
        if not charges:
            continue
        latest = max(charges, key=lambda r: r.issue_date)
        findings.append(
            _finding(
                finding_type=FindingType.UNUSED_RECURRING_CHARGE,
                title=f"Unused recurring charge {sub.name}",
                description=f"{sub.name} is marked is_in_use=false but invoice {latest.invoice_number} still billed {latest.total}.",
                amount=latest.total,
                related=_rel(
                    ("subscription", sub.id, sub.name),
                    ("invoice", latest.id, latest.invoice_number),
                    ("vendor", sub.vendor_id, None),
                ),
                facts={"subscription": sub.name, "invoice_number": latest.invoice_number, "amount": str(latest.total)},
            )
        )
    return findings


DETECTORS = (
    detect_duplicate_invoices,
    detect_duplicate_payments,
    detect_invoice_po_mismatch,
    detect_invoice_gr_mismatch,
    detect_missing_purchase_order,
    detect_new_vendor,
    detect_vendor_bank_detail_change,
    detect_unusual_vendor_amount,
    detect_self_approved,
    detect_approval_authority_exceeded,
    detect_missing_supporting_document,
    detect_closed_period_posting,
    detect_abnormal_transaction_timing,
    detect_contract_pricing_violation,
    detect_suspicious_round_number_payment,
    detect_previously_flagged_vendor,
    detect_unexpected_recurring_subscription,
    detect_overdue_receivable,
    detect_unused_recurring_charge,
)


def run_detectors(snapshot: FinanceSnapshot) -> tuple[Finding, ...]:
    out: list[Finding] = []
    for detector in DETECTORS:
        out.extend(detector(snapshot))
    return tuple(out)
