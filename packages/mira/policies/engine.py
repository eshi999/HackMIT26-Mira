"""Evaluate Policy.rules JSON against a subject. Deterministic."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from mira.core.money import quantize_money
from mira.finance.snapshot import FinanceSnapshot
from mira.policies.types import PolicyCheckResult, PolicyEvaluation, PolicySubject

ENGINE_VERSION = "policy-1"

POL_SPEND_CFO_10K = "POL-SPEND-CFO-10K"
POL_VENDOR_NEW_SECONDARY = "POL-VENDOR-NEW-SECONDARY"
POL_APPR_NO_SELF = "POL-APPR-NO-SELF"
POL_PREC_AWS_12K = "POL-PREC-AWS-12K"
POL_PO_REQUIRED = "POL-PO-REQUIRED"
POL_CLOSED_PERIOD = "POL-CLOSED-PERIOD"
POL_DOC_REQUIRED = "POL-DOC-REQUIRED"

NEW_VENDOR_DAYS_DEFAULT = 30


def _money(value: object) -> Decimal:
    return quantize_money(value if not isinstance(value, Decimal) else value)


def is_new_vendor(onboarded_at: date | None, as_of: date, window_days: int = NEW_VENDOR_DAYS_DEFAULT) -> bool:
    if onboarded_at is None:
        return False
    return (as_of - onboarded_at) <= timedelta(days=window_days)


def _aws_vendor(name: str | None) -> bool:
    if not name:
        return False
    lowered = name.lower()
    return "amazon web services" in lowered or lowered.strip() in {"aws", "amazon web services (aws)"}


def evaluate_subject(snapshot: FinanceSnapshot, subject: PolicySubject) -> PolicyEvaluation:
    rules = snapshot.merged_rules()
    cfo_threshold = _money(rules.get("dual_approval_above", rules.get("cfo_approval_above", 10000)))
    aws_precedent_limit = _money(rules.get("aws_precedent_limit", 12000))
    new_vendor_days = int(rules.get("new_vendor_days", NEW_VENDOR_DAYS_DEFAULT))
    closed_periods = set(rules.get("closed_periods", []))
    as_of = subject.as_of if isinstance(subject.as_of, date) else snapshot.as_of

    checks: list[PolicyCheckResult] = []
    required_roles: list[str] = []
    used_precedents: list[UUID] = []

    aws_carveout = False
    if _aws_vendor(subject.vendor_name) and subject.amount < aws_precedent_limit:
        precedent = next(
            (row for row in snapshot.precedents if "aws" in (row.reusable_rule or "").lower() or "aws" in row.summary.lower()),
            None,
        )
        aws_carveout = True
        used_precedents.append(precedent.id) if precedent is not None else None
        checks.append(
            PolicyCheckResult(
                policy_id=POL_PREC_AWS_12K,
                passed=True,
                reason=(
                    f"AWS infrastructure {subject.amount} is below the {aws_precedent_limit} "
                    "precedent ceiling; dual-approval spend rule is not applied."
                ),
                used_precedent_id=precedent.id if precedent is not None else None,
            )
        )
    else:
        checks.append(
            PolicyCheckResult(
                policy_id=POL_PREC_AWS_12K,
                passed=True,
                reason="AWS precedent carve-out does not apply to this subject.",
            )
        )

    if (not aws_carveout) and subject.amount > cfo_threshold:
        checks.append(
            PolicyCheckResult(
                policy_id=POL_SPEND_CFO_10K,
                passed=False,
                reason=f"Amount {subject.amount} exceeds CFO approval threshold {cfo_threshold}.",
            )
        )
        required_roles.append("cfo")
    else:
        checks.append(
            PolicyCheckResult(
                policy_id=POL_SPEND_CFO_10K,
                passed=True,
                reason=(
                    "AWS precedent covers this amount."
                    if aws_carveout
                    else f"Amount {subject.amount} is within the CFO threshold {cfo_threshold}."
                ),
            )
        )

    vendor_is_new = subject.is_new_vendor or (
        isinstance(subject.vendor_onboarded_at, date) and is_new_vendor(subject.vendor_onboarded_at, as_of, new_vendor_days)
    )
    if vendor_is_new and not subject.has_secondary_approval:
        checks.append(
            PolicyCheckResult(
                policy_id=POL_VENDOR_NEW_SECONDARY,
                passed=False,
                reason="New vendor requires secondary approval before spend.",
            )
        )
        required_roles.append("controller")
    else:
        checks.append(
            PolicyCheckResult(
                policy_id=POL_VENDOR_NEW_SECONDARY,
                passed=True,
                reason="Vendor is established or secondary approval is present.",
            )
        )

    if (
        subject.requested_by_user_id is not None
        and subject.approver_user_id is not None
        and subject.requested_by_user_id == subject.approver_user_id
    ):
        checks.append(
            PolicyCheckResult(
                policy_id=POL_APPR_NO_SELF,
                passed=False,
                reason="Requester cannot approve their own purchase.",
            )
        )
    else:
        checks.append(
            PolicyCheckResult(
                policy_id=POL_APPR_NO_SELF,
                passed=True,
                reason="Requester and approver are distinct or approval is not yet recorded.",
            )
        )

    if subject.posted_period and subject.posted_period in closed_periods:
        checks.append(
            PolicyCheckResult(
                policy_id=POL_CLOSED_PERIOD,
                passed=False,
                reason=f"Period {subject.posted_period} is closed.",
            )
        )
    else:
        checks.append(
            PolicyCheckResult(
                policy_id=POL_CLOSED_PERIOD,
                passed=True,
                reason="Posted period is open or not supplied.",
            )
        )

    violated = tuple(c.policy_id for c in checks if not c.passed)
    passed = tuple(c.policy_id for c in checks if c.passed)
    requires_human = bool(violated)
    explanation = " ".join(c.reason for c in checks if not c.passed) or "All machine-evaluable policy checks passed."
    return PolicyEvaluation(
        subject_type=subject.subject_type,
        subject_id=subject.subject_id,
        violated_policy_ids=violated,
        passed_policy_ids=passed,
        requires_human_approval=requires_human,
        required_roles=tuple(dict.fromkeys(required_roles)),
        used_precedent_ids=tuple(p for p in used_precedents if p is not None),
        checks=tuple(checks),
        explanation=explanation,
    )


def evaluate_invoice(snapshot: FinanceSnapshot, invoice_id: UUID) -> PolicyEvaluation | None:
    invoice = snapshot.invoice(invoice_id)
    if invoice is None:
        return None
    vendor = snapshot.vendor(invoice.vendor_id)
    approval = next(
        (
            row
            for row in snapshot.approvals
            if row.subject_type in {"invoice", "purchase_order"}
            and row.subject_id in {invoice.id, invoice.purchase_order_id}
        ),
        None,
    )
    secondary = any(
        row.approver_user_id
        and row.requested_by_user_id
        and row.approver_user_id != row.requested_by_user_id
        and row.status == "approved"
        and row.subject_id in {invoice.id, invoice.purchase_order_id}
        for row in snapshot.approvals
    )
    posted = invoice.posted_period or f"{invoice.issue_date.year:04d}-{invoice.issue_date.month:02d}"
    return evaluate_subject(
        snapshot,
        PolicySubject(
            subject_type="invoice",
            subject_id=invoice.id,
            amount=invoice.total,
            vendor_id=invoice.vendor_id,
            vendor_name=vendor.name if vendor else None,
            vendor_onboarded_at=vendor.onboarded_at if vendor else None,
            requested_by_user_id=invoice.requested_by_user_id or (approval.requested_by_user_id if approval else None),
            approver_user_id=invoice.approved_by_user_id or (approval.approver_user_id if approval else None),
            as_of=snapshot.as_of,
            posted_period=posted,
            has_secondary_approval=secondary,
        ),
    )


def evaluate_purchase_order(snapshot: FinanceSnapshot, po_id: UUID) -> PolicyEvaluation | None:
    po = snapshot.purchase_order(po_id)
    if po is None:
        return None
    vendor = snapshot.vendor(po.vendor_id)
    approval = next(
        (row for row in snapshot.approvals if row.subject_type == "purchase_order" and row.subject_id == po.id),
        None,
    )
    secondary = any(
        row.subject_id == po.id
        and row.approver_user_id
        and row.requested_by_user_id
        and row.approver_user_id != row.requested_by_user_id
        and row.status == "approved"
        for row in snapshot.approvals
    )
    return evaluate_subject(
        snapshot,
        PolicySubject(
            subject_type="purchase_order",
            subject_id=po.id,
            amount=po.total,
            vendor_id=po.vendor_id,
            vendor_name=vendor.name if vendor else None,
            vendor_onboarded_at=vendor.onboarded_at if vendor else None,
            requested_by_user_id=po.requested_by_user_id or (approval.requested_by_user_id if approval else None),
            approver_user_id=approval.approver_user_id if approval else None,
            as_of=snapshot.as_of,
            has_secondary_approval=secondary,
        ),
    )


def po_required(snapshot: FinanceSnapshot, invoice_id: UUID) -> bool:
    invoice = snapshot.invoice(invoice_id)
    if invoice is None or invoice.direction != "ap":
        return False
    rules = snapshot.merged_rules()
    threshold = _money(rules.get("po_required_above", 2500))
    exempt = {str(v) for v in rules.get("po_exempt_vendor_ids", [])}
    if invoice.vendor_id and str(invoice.vendor_id) in exempt:
        return False
    return invoice.total > threshold and invoice.purchase_order_id is None
