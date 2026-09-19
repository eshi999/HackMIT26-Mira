"""Risk points and confidence are computed here. They are never combined into one score."""

from __future__ import annotations

from decimal import Decimal

from mira.core.agent_outputs import Confidence
from mira.core.enums import FindingType, RecommendedAction, RiskLevel, Severity
from mira.core.money import quantize_money
from mira.risk.types import ScoringBreakdown, ScoringFactor, TypedFinding

ENGINE_VERSION = "risk-1"

# Consequential seriousness of the situation — not certainty.
RISK_POINTS: dict[FindingType, Decimal] = {
    FindingType.DUPLICATE_INVOICE: Decimal("40.00"),
    FindingType.DUPLICATE_PAYMENT: Decimal("45.00"),
    FindingType.INVOICE_PO_MISMATCH: Decimal("35.00"),
    FindingType.INVOICE_GR_MISMATCH: Decimal("30.00"),
    FindingType.MISSING_PURCHASE_ORDER: Decimal("20.00"),
    FindingType.NEW_VENDOR: Decimal("15.00"),
    FindingType.VENDOR_BANK_DETAIL_CHANGE: Decimal("50.00"),
    FindingType.UNUSUAL_VENDOR_AMOUNT: Decimal("25.00"),
    FindingType.SELF_APPROVED_REQUEST: Decimal("55.00"),
    FindingType.APPROVAL_AUTHORITY_EXCEEDED: Decimal("50.00"),
    FindingType.MISSING_SUPPORTING_DOCUMENT: Decimal("15.00"),
    FindingType.CLOSED_PERIOD_POSTING: Decimal("40.00"),
    FindingType.ABNORMAL_TRANSACTION_TIMING: Decimal("10.00"),
    FindingType.CONTRACT_PRICING_VIOLATION: Decimal("35.00"),
    FindingType.SUSPICIOUS_ROUND_NUMBER_PAYMENT: Decimal("12.00"),
    FindingType.PREVIOUSLY_FLAGGED_VENDOR: Decimal("20.00"),
    FindingType.UNEXPECTED_RECURRING_SUBSCRIPTION: Decimal("18.00"),
    FindingType.OVERDUE_RECEIVABLE: Decimal("22.00"),
    FindingType.UNUSED_RECURRING_CHARGE: Decimal("16.00"),
}

# How sure the detector is when its inputs are complete. Independent of dollars at stake.
DETECTOR_CONFIDENCE: dict[FindingType, Decimal] = {
    FindingType.DUPLICATE_INVOICE: Decimal("0.95"),
    FindingType.DUPLICATE_PAYMENT: Decimal("0.93"),
    FindingType.INVOICE_PO_MISMATCH: Decimal("0.99"),
    FindingType.INVOICE_GR_MISMATCH: Decimal("0.99"),
    FindingType.MISSING_PURCHASE_ORDER: Decimal("0.99"),
    FindingType.NEW_VENDOR: Decimal("0.90"),
    FindingType.VENDOR_BANK_DETAIL_CHANGE: Decimal("0.99"),
    FindingType.UNUSUAL_VENDOR_AMOUNT: Decimal("0.80"),
    FindingType.SELF_APPROVED_REQUEST: Decimal("0.99"),
    FindingType.APPROVAL_AUTHORITY_EXCEEDED: Decimal("0.99"),
    FindingType.MISSING_SUPPORTING_DOCUMENT: Decimal("0.99"),
    FindingType.CLOSED_PERIOD_POSTING: Decimal("0.99"),
    FindingType.ABNORMAL_TRANSACTION_TIMING: Decimal("0.85"),
    FindingType.CONTRACT_PRICING_VIOLATION: Decimal("0.99"),
    FindingType.SUSPICIOUS_ROUND_NUMBER_PAYMENT: Decimal("0.70"),
    FindingType.PREVIOUSLY_FLAGGED_VENDOR: Decimal("0.99"),
    FindingType.UNEXPECTED_RECURRING_SUBSCRIPTION: Decimal("0.75"),
    FindingType.OVERDUE_RECEIVABLE: Decimal("0.99"),
    FindingType.UNUSED_RECURRING_CHARGE: Decimal("0.88"),
}

CONFIDENCE_BASIS: dict[FindingType, str] = {
    FindingType.DUPLICATE_INVOICE: "Same vendor, amount within $1, invoice numbers within edit distance 2, dates within 14 days.",
    FindingType.DUPLICATE_PAYMENT: "Two settled payments share vendor/amount/window or the same invoice id.",
    FindingType.INVOICE_PO_MISMATCH: "Invoice total and PO total are both present numeric fields.",
    FindingType.INVOICE_GR_MISMATCH: "Invoice and goods-receipt quantities are both present.",
    FindingType.MISSING_PURCHASE_ORDER: "purchase_order_id is null above the PO-required threshold.",
    FindingType.NEW_VENDOR: "Vendor onboarded_at is within the policy new-vendor window versus as_of.",
    FindingType.VENDOR_BANK_DETAIL_CHANGE: "previous_bank_account_ref and bank_changed_at are populated on the vendor row.",
    FindingType.UNUSUAL_VENDOR_AMOUNT: "Current invoice exceeds 1.5× the vendor's trailing mean on complete history.",
    FindingType.SELF_APPROVED_REQUEST: "requested_by_user_id equals approver_user_id on the approval row.",
    FindingType.APPROVAL_AUTHORITY_EXCEEDED: "Approved amount is greater than the employee's approval_limit.",
    FindingType.MISSING_SUPPORTING_DOCUMENT: "Invoice.document_id is null.",
    FindingType.CLOSED_PERIOD_POSTING: "Posted period is listed in policy closed_periods.",
    FindingType.ABNORMAL_TRANSACTION_TIMING: "Posted timestamp falls on a weekend or outside 08:00–18:00 local clock.",
    FindingType.CONTRACT_PRICING_VIOLATION: "Invoice total exceeds compounded contract ceiling from numeric term sheet.",
    FindingType.SUSPICIOUS_ROUND_NUMBER_PAYMENT: "Payment amount is a whole thousand with no cents; weak signal by design.",
    FindingType.PREVIOUSLY_FLAGGED_VENDOR: "Vendor.risk_tier is watch or high on the canonical vendor row.",
    FindingType.UNEXPECTED_RECURRING_SUBSCRIPTION: "Recurring charges exist for a vendor with no expected subscription row.",
    FindingType.OVERDUE_RECEIVABLE: "as_of minus due_date is a calendar difference on an open AR invoice.",
    FindingType.UNUSED_RECURRING_CHARGE: "Expected subscription is_in_use is false and a current charge exists.",
}

ACTION_BY_TYPE: dict[FindingType, RecommendedAction] = {
    FindingType.DUPLICATE_INVOICE: RecommendedAction.BLOCK_PAYMENT,
    FindingType.DUPLICATE_PAYMENT: RecommendedAction.BLOCK_PAYMENT,
    FindingType.INVOICE_PO_MISMATCH: RecommendedAction.HOLD_FOR_REVIEW,
    FindingType.INVOICE_GR_MISMATCH: RecommendedAction.HOLD_FOR_REVIEW,
    FindingType.MISSING_PURCHASE_ORDER: RecommendedAction.OBTAIN_PO,
    FindingType.NEW_VENDOR: RecommendedAction.REQUIRE_SECONDARY_APPROVAL,
    FindingType.VENDOR_BANK_DETAIL_CHANGE: RecommendedAction.INVESTIGATE_BANK_CHANGE,
    FindingType.UNUSUAL_VENDOR_AMOUNT: RecommendedAction.HOLD_FOR_REVIEW,
    FindingType.SELF_APPROVED_REQUEST: RecommendedAction.REVERSE_APPROVAL,
    FindingType.APPROVAL_AUTHORITY_EXCEEDED: RecommendedAction.ESCALATE_TO_CFO,
    FindingType.MISSING_SUPPORTING_DOCUMENT: RecommendedAction.OBTAIN_RECEIPT,
    FindingType.CLOSED_PERIOD_POSTING: RecommendedAction.REJECT_POSTING,
    FindingType.ABNORMAL_TRANSACTION_TIMING: RecommendedAction.HOLD_FOR_REVIEW,
    FindingType.CONTRACT_PRICING_VIOLATION: RecommendedAction.REVIEW_CONTRACT_PRICING,
    FindingType.SUSPICIOUS_ROUND_NUMBER_PAYMENT: RecommendedAction.HOLD_FOR_REVIEW,
    FindingType.PREVIOUSLY_FLAGGED_VENDOR: RecommendedAction.HOLD_FOR_REVIEW,
    FindingType.UNEXPECTED_RECURRING_SUBSCRIPTION: RecommendedAction.CANCEL_SUBSCRIPTION,
    FindingType.OVERDUE_RECEIVABLE: RecommendedAction.COLLECT_RECEIVABLE,
    FindingType.UNUSED_RECURRING_CHARGE: RecommendedAction.CANCEL_SUBSCRIPTION,
}

ACTION_PRIORITY = [
    RecommendedAction.INVESTIGATE_BANK_CHANGE,
    RecommendedAction.REVERSE_APPROVAL,
    RecommendedAction.REJECT_POSTING,
    RecommendedAction.BLOCK_PAYMENT,
    RecommendedAction.ESCALATE_TO_CFO,
    RecommendedAction.REVIEW_DUPLICATE_REFUND,
    RecommendedAction.REVIEW_CONTRACT_PRICING,
    RecommendedAction.REQUIRE_SECONDARY_APPROVAL,
    RecommendedAction.HOLD_FOR_REVIEW,
    RecommendedAction.OBTAIN_PO,
    RecommendedAction.OBTAIN_RECEIPT,
    RecommendedAction.COLLECT_RECEIVABLE,
    RecommendedAction.CANCEL_SUBSCRIPTION,
    RecommendedAction.NO_FORCED_MATCH,
]


def amount_risk_adder(amount: Decimal) -> Decimal:
    amount = amount.copy_abs()
    if amount >= Decimal("10000.00"):
        return Decimal("10.00")
    if amount >= Decimal("2500.00"):
        return Decimal("5.00")
    return Decimal("0.00")


def risk_contribution(finding_type: FindingType, amount: Decimal) -> Decimal:
    return RISK_POINTS[finding_type] + amount_risk_adder(amount)


def confidence_for(finding_type: FindingType) -> Confidence:
    return Confidence(score=DETECTOR_CONFIDENCE[finding_type], basis=CONFIDENCE_BASIS[finding_type])


def severity_for(points: Decimal) -> Severity:
    if points >= Decimal("50.00"):
        return Severity.CRITICAL
    if points >= Decimal("35.00"):
        return Severity.HIGH
    if points >= Decimal("20.00"):
        return Severity.MEDIUM
    return Severity.LOW


def risk_level_for(score: Decimal) -> RiskLevel:
    if score >= Decimal("70.00"):
        return RiskLevel.CRITICAL
    if score >= Decimal("45.00"):
        return RiskLevel.HIGH
    if score >= Decimal("25.00"):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def incident_risk_score(findings: tuple[TypedFinding, ...]) -> Decimal:
    if not findings:
        return Decimal("0.00")
    ranked = sorted(findings, key=lambda f: f.risk_contribution, reverse=True)
    total = ranked[0].risk_contribution
    for extra in ranked[1:]:
        total += extra.risk_contribution * Decimal("0.50")
    return min(Decimal("100.00"), quantize_money(total))


def incident_confidence(findings: tuple[TypedFinding, ...]) -> Confidence:
    if not findings:
        return Confidence(score=Decimal("0.00"), basis="No findings.")
    weight = sum((f.risk_contribution for f in findings), Decimal("0.00"))
    if weight == 0:
        score = min(f.confidence.score for f in findings)
    else:
        score = sum((f.confidence.score * f.risk_contribution for f in findings), Decimal("0.00")) / weight
    score = min(Decimal("1.00"), quantize_money(score))
    basis = "Weighted by finding risk_contribution (not mixed into the risk score): " + "; ".join(
        f"{f.finding_type.value} confidence {f.confidence.score}" for f in findings
    )
    return Confidence(score=score, basis=basis)


def recommended_action(findings: tuple[TypedFinding, ...]) -> RecommendedAction:
    actions = [ACTION_BY_TYPE[f.finding_type] for f in findings]
    for candidate in ACTION_PRIORITY:
        if candidate in actions:
            return candidate
    return RecommendedAction.HOLD_FOR_REVIEW


def scoring_breakdown(findings: tuple[TypedFinding, ...]) -> ScoringBreakdown:
    risk = incident_risk_score(findings)
    conf = incident_confidence(findings)
    factors = tuple(
        ScoringFactor(
            code=f.finding_type.value,
            points=f.risk_contribution,
            note=f.title,
            finding_id=f.id,
        )
        for f in findings
    )
    return ScoringBreakdown(
        factors=factors,
        risk_total=risk,
        risk_level=risk_level_for(risk),
        confidence_score=conf.score,
        confidence_basis=conf.basis,
    )


def explain_incident(
    *,
    risk_score: Decimal,
    risk_level: RiskLevel,
    confidence: Confidence,
    breakdown: ScoringBreakdown,
    action: RecommendedAction,
    findings: tuple[TypedFinding, ...],
) -> str:
    factor_bits = "; ".join(f"{fac.code} {fac.points} pts ({fac.note})" for fac in breakdown.factors)
    return (
        f"Risk {risk_score}/100 ({risk_level.value}) from {len(findings)} finding(s). "
        f"Scoring: {factor_bits}. "
        f"Confidence {confidence.score} is independent of risk and is {confidence.basis} "
        f"Recommended action: {action.value}."
    )
