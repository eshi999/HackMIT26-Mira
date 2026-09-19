from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from mira.core.agent_outputs import (
    AgentTaskResult,
    AuditFinding,
    AuthorityBasis,
    CFORecommendation,
    Confidence,
    EvidenceReference,
    HumanEscalation,
    InvoiceDecision,
    ReconciliationResult,
    RiskFinding,
)
from mira.core.enums import AgentRole, AgentTaskStatus, RiskLevel, Severity
from mira.core.models import CANONICAL_MODELS
from mira.core.money import Money


def test_invoice_decision_rejects_prose_only_payload() -> None:
    decision = InvoiceDecision(
        invoice_id=uuid4(),
        action="reject",
        computed_total=Money(amount="18400.00", currency="USD"),
        explanation="Duplicate of 10441",
        confidence=Confidence(score=Decimal("0.96"), basis="exact amount + near number"),
        risk_level=RiskLevel.HIGH,
        policy_basis="clause 6",
        authority_basis=AuthorityBasis(
            policy_name="Spend v3",
            clause="6",
            actor_role="mira_cfo",
        ),
        evidence=[
            EvidenceReference(
                object_type="invoice",
                source_system="local",
                locator="invoice:10441-A",
            )
        ],
        requires_human_approval=False,
    )
    dumped = decision.model_dump()
    assert dumped["computed_total"]["amount"] == Decimal("18400.00")
    assert dumped["evidence"]


def test_all_required_output_types_importable() -> None:
    assert RiskFinding
    assert ReconciliationResult
    assert InvoiceDecision
    assert AuditFinding
    assert AgentTaskResult
    assert CFORecommendation
    assert HumanEscalation
    assert AgentRole.MIRA_CFO
    assert AgentTaskStatus.COMPLETED
    assert Severity.HIGH
    assert CANONICAL_MODELS
