from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from mira.core.money import Money
from mira.evaluation.metrics import autonomy_score
from mira.finance.contracts import (
    compare_invoice_to_contract,
    expected_price_as_of,
    facts_from_extracted,
)
from mira.finance.snapshot import FinanceSnapshot, PolicyView, PrecedentView, VendorView
from mira.policies.engine import (
    POL_APPR_NO_SELF,
    POL_PREC_AWS_12K,
    POL_SPEND_CFO_10K,
    POL_VENDOR_NEW_SECONDARY,
    evaluate_subject,
)
from mira.policies.types import PolicySubject


def test_aws_precedent_carveout_under_12k() -> None:
    snapshot = FinanceSnapshot(
        company_id=uuid4(),
        as_of=date(2026, 9, 19),
        vendors=(
            VendorView(
                id=uuid4(),
                name="Amazon Web Services",
                risk_tier="low",
                status="active",
                is_preferred=True,
            ),
        ),
        policies=(
            PolicyView(
                id=uuid4(),
                name="spend",
                policy_type="spend",
                version="3",
                body="",
                rules={"cfo_approval_above": 10000, "aws_precedent_limit": 12000},
                status="active",
            ),
        ),
        precedents=(
            PrecedentView(
                id=uuid4(),
                situation_hash="aws",
                summary="AWS infrastructure precedent",
                outcome="approved",
                reusable_rule="AWS infrastructure below $12,000 may use this approved precedent.",
                period="2026-06",
            ),
        ),
    )
    vendor = snapshot.vendors[0]
    under = evaluate_subject(
        snapshot,
        PolicySubject(
            subject_type="invoice",
            subject_id=uuid4(),
            amount=Decimal("11000.00"),
            vendor_id=vendor.id,
            vendor_name=vendor.name,
            as_of=date(2026, 9, 19),
        ),
    )
    over = evaluate_subject(
        snapshot,
        PolicySubject(
            subject_type="invoice",
            subject_id=uuid4(),
            amount=Decimal("19800.00"),
            vendor_id=vendor.id,
            vendor_name=vendor.name,
            as_of=date(2026, 9, 19),
        ),
    )
    assert POL_SPEND_CFO_10K not in under.violated_policy_ids
    assert POL_PREC_AWS_12K in under.passed_policy_ids
    assert POL_SPEND_CFO_10K in over.violated_policy_ids


def test_aws_without_precedent_still_hits_spend_threshold() -> None:
    snapshot = FinanceSnapshot(
        company_id=uuid4(),
        as_of=date(2026, 9, 19),
        policies=(
            PolicyView(
                id=uuid4(),
                name="spend",
                policy_type="spend",
                version="3",
                body="",
                rules={"cfo_approval_above": 10000, "aws_precedent_limit": 12000},
                status="active",
            ),
        ),
    )
    result = evaluate_subject(
        snapshot,
        PolicySubject(
            subject_type="invoice",
            subject_id=uuid4(),
            amount=Decimal("11000.00"),
            vendor_name="Amazon Web Services",
            as_of=date(2026, 9, 19),
        ),
    )
    assert POL_SPEND_CFO_10K in result.violated_policy_ids


def test_self_approve_and_new_vendor_policy() -> None:
    requester = uuid4()
    snapshot = FinanceSnapshot(
        company_id=uuid4(),
        as_of=date(2026, 9, 19),
        policies=(
            PolicyView(
                id=uuid4(),
                name="spend",
                policy_type="spend",
                version="3",
                body="",
                rules={"cfo_approval_above": 10000, "new_vendor_days": 30},
                status="active",
            ),
        ),
    )
    self_eval = evaluate_subject(
        snapshot,
        PolicySubject(
            subject_type="purchase_order",
            subject_id=uuid4(),
            amount=Decimal("1800.00"),
            requested_by_user_id=requester,
            approver_user_id=requester,
            as_of=date(2026, 9, 19),
        ),
    )
    new_eval = evaluate_subject(
        snapshot,
        PolicySubject(
            subject_type="invoice",
            subject_id=uuid4(),
            amount=Decimal("14200.00"),
            is_new_vendor=True,
            as_of=date(2026, 9, 19),
        ),
    )
    assert POL_APPR_NO_SELF in self_eval.violated_policy_ids
    assert POL_VENDOR_NEW_SECONDARY in new_eval.violated_policy_ids
    assert POL_SPEND_CFO_10K in new_eval.violated_policy_ids


def test_contract_compounded_ceiling() -> None:
    facts = facts_from_extracted(
        {
            "agreed_price": "10000.00",
            "allowed_annual_increase_pct": "4",
            "payment_terms": "Net 30",
            "price_basis_date": "2025-09-01",
        }
    )
    expected, years = expected_price_as_of(facts, date(2026, 9, 1))
    assert years == Decimal("1")
    assert expected.amount == Decimal("10400.00")
    comparison = compare_invoice_to_contract(
        contract_id=uuid4(),
        invoice_id=uuid4(),
        facts=facts,
        invoice_amount=Money(amount=Decimal("11100.00")),
        invoice_date=date(2026, 9, 1),
    )
    assert comparison.is_violation is True
    assert comparison.increase_pct == Decimal("11.00")
    assert comparison.confidence.score == Decimal("0.99")


def test_autonomy_score_formula() -> None:
    score = autonomy_score(
        reconciliation_rate=Decimal("0.80"),
        tasks_completed=Decimal("10"),
        tasks_auto_completed=Decimal("6"),
        tasks_escalated=Decimal("4"),
        false_escalations=Decimal("1"),
        decision_accuracy=Decimal("1.00"),
    )
    # 100 * (0.30*0.80 + 0.25*0.60 + 0.25*1.00 + 0.20*0.75)
    # = 100 * (0.24 + 0.15 + 0.25 + 0.15) = 79.00
    assert score == Decimal("79.00")
