"""Typed agent I/O.

Agents MUST NOT communicate through unstructured prose alone.
These schemas are the only legal payloads on AgentTask.result_payload
and Decision.structured_output.

No agent runtime lives in this slice — only the contract.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mira.core.enums import AgentRole, AgentTaskStatus, RiskLevel, Severity
from mira.core.money import Money, quantize_money


class EvidenceReference(BaseModel):
    """Pointer back to a source document, row, clause, or public series."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID | None = None
    object_type: str
    object_id: UUID | None = None
    source_system: str
    locator: str | None = None
    uri: str | None = None
    excerpt: str | None = None
    content_hash: str | None = None
    captured_at: datetime | None = None
    role: str = "supporting"


class Confidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: Decimal = Field(ge=0, le=1)
    basis: str
    model: str | None = None

    @field_validator("score", mode="before")
    @classmethod
    def _score(cls, v: Any) -> Decimal:
        return quantize_money(v) if not isinstance(v, Decimal) else v


class AuthorityBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: UUID | None = None
    policy_name: str
    clause: str
    actor_role: str
    limit_amount: Money | None = None


class RiskFinding(BaseModel):
    """A factor the risk engine scored. Agents explain; they do not set the score."""

    model_config = ConfigDict(extra="forbid")

    code: str
    title: str
    severity: Severity
    points: Decimal
    note: str
    evidence: list[EvidenceReference] = Field(default_factory=list)


class ReconciliationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_type: Literal["three_way", "bank", "duplicate", "po_invoice"]
    status: Literal["matched", "mismatch", "duplicate", "unmatched"]
    left_object_type: str
    left_object_id: UUID
    right_object_type: str | None = None
    right_object_id: UUID | None = None
    amount_delta: Money | None = None
    explanation: str
    evidence: list[EvidenceReference] = Field(default_factory=list)


class InvoiceDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_id: UUID
    action: Literal["pay", "hold", "reject", "escalate", "request_credit"]
    computed_total: Money
    duplicate_of_invoice_id: UUID | None = None
    explanation: str
    confidence: Confidence
    risk_level: RiskLevel
    policy_basis: str
    authority_basis: AuthorityBasis
    evidence: list[EvidenceReference] = Field(default_factory=list)
    requires_human_approval: bool


class AuditFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    control: str
    severity: Severity
    clause_locator: str | None = None
    explanation: str
    evidence: list[EvidenceReference] = Field(default_factory=list)


class AgentTaskResult(BaseModel):
    """Envelope every specialist returns to Mira."""

    model_config = ConfigDict(extra="forbid")

    task_id: UUID | None = None
    agent_role: AgentRole
    status: AgentTaskStatus
    artifact_type: str
    artifact: dict[str, Any]
    errors: list[str] = Field(default_factory=list)
    explanation: str
    evidence: list[EvidenceReference] = Field(default_factory=list)


class CFORecommendation(BaseModel):
    """The only user-facing recommendation type. Mira speaks this."""

    model_config = ConfigDict(extra="forbid")

    headline: str
    body: str
    action: str
    priority: Literal["info", "action", "urgent"]
    confidence: Confidence
    risk_level: RiskLevel
    policy_basis: str
    authority_basis: AuthorityBasis
    dollars_impact: Money | None = None
    hours_saved_estimate: Decimal | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)
    requires_human_approval: bool = False


class HumanEscalation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    why_uncertain: str
    recommended_if_yes: str | None = None
    recommended_if_no: str | None = None
    due_by: datetime | None = None
    approver_role: str
    confidence: Confidence
    risk_level: RiskLevel
    evidence: list[EvidenceReference] = Field(default_factory=list)


class ProcurementProposal(BaseModel):
    """Visa-path intermediate object. Still not a payment."""

    model_config = ConfigDict(extra="forbid")

    need: str
    vendor_id: UUID | None = None
    vendor_name: str
    estimated_total: Money
    budget_remaining: Money
    policy_ok: bool
    policy_basis: str
    requires_human_approval: bool
    is_sandbox_purchase: bool = True
    explanation: str
    evidence: list[EvidenceReference] = Field(default_factory=list)
    confidence: Confidence
    risk_level: RiskLevel
    authority_basis: AuthorityBasis
