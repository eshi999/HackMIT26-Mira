from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from mira.core.enums import (
    ApprovalStatus,
    DecisionStatus,
    FindingStatus,
    IncidentStatus,
    RiskLevel,
    Severity,
)
from mira.core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

MONEY = Numeric(18, 2)


class Evidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evidence"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(80))
    source_system: Mapped[str] = mapped_column(String(40))
    uri: Mapped[str | None] = mapped_column(String(800), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class EvidenceReferenceRow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Row form of EvidenceReference. Attaches evidence to any canonical object."""

    __tablename__ = "evidence_references"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    evidence_id: Mapped[UUID | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    object_type: Mapped[str] = mapped_column(String(80), index=True)
    object_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    source_system: Mapped[str] = mapped_column(String(40), default="seed")
    locator: Mapped[str | None] = mapped_column(String(120), nullable=True)
    uri: Mapped[str | None] = mapped_column(String(800), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    role: Mapped[str] = mapped_column(String(40), default="supporting")


class Finding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "findings"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    finding_type: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(16), default=Severity.MEDIUM.value)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default=FindingStatus.OPEN.value)
    related_object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    related_object_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)


class Incident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "incidents"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    severity: Mapped[str] = mapped_column(String(16), default=Severity.MEDIUM.value)
    status: Mapped[str] = mapped_column(String(32), default=IncidentStatus.OPEN.value)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IncidentFinding(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "incident_findings"

    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    finding_id: Mapped[UUID] = mapped_column(ForeignKey("findings.id"), index=True)


class RiskAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_assessments"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    subject_type: Mapped[str] = mapped_column(String(80))
    subject_id: Mapped[UUID] = mapped_column(index=True)
    risk_level: Mapped[str] = mapped_column(String(16), default=RiskLevel.MEDIUM.value)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    factors: Mapped[list | dict] = mapped_column(JSON)
    engine_version: Mapped[str] = mapped_column(String(32), default="risk-0")
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Decision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "decisions"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    decision_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(32), default=DecisionStatus.PROPOSED.value)
    action: Mapped[str] = mapped_column(String(200))
    rationale: Mapped[str] = mapped_column(Text)
    structured_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    risk_level: Mapped[str] = mapped_column(String(16), default=RiskLevel.MEDIUM.value)
    policy_basis: Mapped[str] = mapped_column(String(400))
    authority_basis: Mapped[str] = mapped_column(String(400))
    requires_human_approval: Mapped[bool] = mapped_column(default=False)
    agent_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_runs.id"), nullable=True, index=True
    )
    subject_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    subject_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    dollars_impact: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    hours_saved_estimate: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)


class Approval(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approvals"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    subject_type: Mapped[str] = mapped_column(String(80))
    subject_id: Mapped[UUID] = mapped_column(index=True)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approver_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=ApprovalStatus.PENDING.value)
    decision_id: Mapped[UUID | None] = mapped_column(ForeignKey("decisions.id"), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(16), default=RiskLevel.MEDIUM.value)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
