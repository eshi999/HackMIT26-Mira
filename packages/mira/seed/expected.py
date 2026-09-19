"""Known answers for Northstar planted scenarios. Evaluation oracle — not LLM output."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from mira.core.enums import FindingType, MatchStatus, RecommendedAction, ReconStage
from mira.policies.engine import (
    POL_APPR_NO_SELF,
    POL_CLOSED_PERIOD,
    POL_SPEND_CFO_10K,
    POL_VENDOR_NEW_SECONDARY,
)
from mira.risk.scoring import amount_risk_adder, risk_contribution


class ExpectedScenario(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    title: str
    finding_types: tuple[FindingType, ...] = ()
    invoice_numbers: tuple[str, ...] = ()
    amount: Decimal | None = None
    three_way_status: MatchStatus | None = None
    recon_stage: ReconStage | None = None
    violated_policy_ids: tuple[str, ...] = ()
    recommended_action: RecommendedAction | None = None
    risk_score: Decimal | None = None
    confidence_score: Decimal | None = None
    contract_increase_pct: Decimal | None = None
    contract_allowed_pct: Decimal | None = None
    days_overdue: int | None = None
    unexplained_delta: Decimal | None = None


def _risk(finding_type: FindingType, amount: Decimal) -> Decimal:
    return risk_contribution(finding_type, amount)


PLANTED_SCENARIOS: tuple[ExpectedScenario, ...] = (
    ExpectedScenario(
        key="duplicate_4850",
        title="duplicate $4,850 invoice",
        finding_types=(FindingType.DUPLICATE_INVOICE,),
        invoice_numbers=("INV-4850", "INV-4850A"),
        amount=Decimal("4850.00"),
        recommended_action=RecommendedAction.BLOCK_PAYMENT,
        risk_score=_risk(FindingType.DUPLICATE_INVOICE, Decimal("4850.00")),
        confidence_score=Decimal("0.95"),
    ),
    ExpectedScenario(
        key="invoice_exceeds_po",
        title="invoice exceeds PO",
        finding_types=(FindingType.INVOICE_PO_MISMATCH,),
        invoice_numbers=("HG-12500",),
        amount=Decimal("12500.00"),
        three_way_status=MatchStatus.MISMATCH,
        recommended_action=RecommendedAction.HOLD_FOR_REVIEW,
        risk_score=_risk(FindingType.INVOICE_PO_MISMATCH, Decimal("12500.00")),
        confidence_score=Decimal("0.99"),
    ),
    ExpectedScenario(
        key="self_approved",
        title="requester self-approves",
        finding_types=(FindingType.SELF_APPROVED_REQUEST,),
        amount=Decimal("1800.00"),
        violated_policy_ids=(POL_APPR_NO_SELF,),
        recommended_action=RecommendedAction.REVERSE_APPROVAL,
        risk_score=_risk(FindingType.SELF_APPROVED_REQUEST, Decimal("1800.00")),
        confidence_score=Decimal("0.99"),
    ),
    ExpectedScenario(
        key="ach_covers_three",
        title="one ACH covers three invoices",
        invoice_numbers=("BIO-1200", "BIO-1400", "BIO-1000"),
        amount=Decimal("3600.00"),
        recon_stage=ReconStage.ONE_TO_MANY,
        confidence_score=Decimal("0.93"),
    ),
    ExpectedScenario(
        key="duplicated_refund",
        title="duplicated refund",
        finding_types=(FindingType.DUPLICATE_PAYMENT,),
        amount=Decimal("185.00"),
        recommended_action=RecommendedAction.BLOCK_PAYMENT,
        risk_score=_risk(FindingType.DUPLICATE_PAYMENT, Decimal("185.00")),
        confidence_score=Decimal("0.93"),
    ),
    ExpectedScenario(
        key="unexplained_12_40",
        title="unexplained $12.40 difference",
        invoice_numbers=("CL-5000",),
        amount=Decimal("5000.00"),
        recon_stage=ReconStage.UNRESOLVED,
        unexplained_delta=Decimal("12.40"),
        recommended_action=RecommendedAction.NO_FORCED_MATCH,
        confidence_score=Decimal("0.99"),
    ),
    ExpectedScenario(
        key="aws_spend_spike",
        title="AWS monthly spend spike",
        finding_types=(FindingType.UNUSUAL_VENDOR_AMOUNT,),
        invoice_numbers=("AWS-2026-09",),
        amount=Decimal("19800.00"),
        violated_policy_ids=(POL_SPEND_CFO_10K,),
        recommended_action=RecommendedAction.HOLD_FOR_REVIEW,
        risk_score=_risk(FindingType.UNUSUAL_VENDOR_AMOUNT, Decimal("19800.00")),
        confidence_score=Decimal("0.80"),
    ),
    ExpectedScenario(
        key="contract_increase_11_vs_4",
        title="contract permits 4% increase but invoice rises 11%",
        finding_types=(FindingType.CONTRACT_PRICING_VIOLATION,),
        invoice_numbers=("CC-2026-09",),
        amount=Decimal("11100.00"),
        recommended_action=RecommendedAction.REVIEW_CONTRACT_PRICING,
        risk_score=_risk(FindingType.CONTRACT_PRICING_VIOLATION, Decimal("11100.00")),
        confidence_score=Decimal("0.99"),
        contract_increase_pct=Decimal("11.00"),
        contract_allowed_pct=Decimal("4"),
    ),
    ExpectedScenario(
        key="ar_overdue_45",
        title="customer >45 days overdue",
        finding_types=(FindingType.OVERDUE_RECEIVABLE,),
        invoice_numbers=("NSL-AR-4411",),
        amount=Decimal("28000.00"),
        recommended_action=RecommendedAction.COLLECT_RECEIVABLE,
        risk_score=_risk(FindingType.OVERDUE_RECEIVABLE, Decimal("28000.00")),
        confidence_score=Decimal("0.99"),
        days_overdue=50,
    ),
    ExpectedScenario(
        key="unused_figma",
        title="unused recurring SaaS charge",
        finding_types=(FindingType.UNUSED_RECURRING_CHARGE,),
        invoice_numbers=("FIGMA-2026-09",),
        amount=Decimal("75.00"),
        recommended_action=RecommendedAction.CANCEL_SUBSCRIPTION,
        risk_score=_risk(FindingType.UNUSED_RECURRING_CHARGE, Decimal("75.00")),
        confidence_score=Decimal("0.88"),
    ),
    ExpectedScenario(
        key="closed_period",
        title="closed-period invoice",
        finding_types=(FindingType.CLOSED_PERIOD_POSTING,),
        invoice_numbers=("HG-CLOSED-JUN",),
        amount=Decimal("3200.00"),
        violated_policy_ids=(POL_CLOSED_PERIOD,),
        recommended_action=RecommendedAction.REJECT_POSTING,
        risk_score=_risk(FindingType.CLOSED_PERIOD_POSTING, Decimal("3200.00")),
        confidence_score=Decimal("0.99"),
    ),
    ExpectedScenario(
        key="missing_receipt",
        title="missing receipt",
        invoice_numbers=("FDX-4100",),
        amount=Decimal("4100.00"),
        three_way_status=MatchStatus.MISSING_EVIDENCE,
        recommended_action=RecommendedAction.OBTAIN_RECEIPT,
        confidence_score=Decimal("0.99"),
    ),
    ExpectedScenario(
        key="new_vendor_outside_policy",
        title="new vendor outside policy",
        finding_types=(FindingType.NEW_VENDOR,),
        invoice_numbers=("QZ-14200",),
        amount=Decimal("14200.00"),
        violated_policy_ids=(POL_VENDOR_NEW_SECONDARY, POL_SPEND_CFO_10K),
        recommended_action=RecommendedAction.REQUIRE_SECONDARY_APPROVAL,
        risk_score=_risk(FindingType.NEW_VENDOR, Decimal("14200.00")),
        confidence_score=Decimal("0.90"),
    ),
)


SCENARIO_BY_KEY = {row.key: row for row in PLANTED_SCENARIOS}

# Sanity: amount adder is part of the frozen oracle.
assert amount_risk_adder(Decimal("4850.00")) == Decimal("5.00")
assert amount_risk_adder(Decimal("12500.00")) == Decimal("10.00")
assert SCENARIO_BY_KEY["duplicate_4850"].risk_score == Decimal("45.00")
assert SCENARIO_BY_KEY["invoice_exceeds_po"].risk_score == Decimal("45.00")
assert SCENARIO_BY_KEY["self_approved"].risk_score == Decimal("55.00")
assert SCENARIO_BY_KEY["aws_spend_spike"].risk_score == Decimal("35.00")
assert SCENARIO_BY_KEY["contract_increase_11_vs_4"].risk_score == Decimal("45.00")
assert SCENARIO_BY_KEY["ar_overdue_45"].risk_score == Decimal("32.00")
assert SCENARIO_BY_KEY["unused_figma"].risk_score == Decimal("16.00")
assert SCENARIO_BY_KEY["closed_period"].risk_score == Decimal("45.00")
assert SCENARIO_BY_KEY["new_vendor_outside_policy"].risk_score == Decimal("25.00")
assert SCENARIO_BY_KEY["duplicated_refund"].risk_score == Decimal("45.00")
