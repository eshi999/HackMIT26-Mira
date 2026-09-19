"""Typed findings and financial incidents. Risk and confidence are separate fields."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from mira.core.agent_outputs import Confidence
from mira.core.enums import FindingType, RecommendedAction, RiskLevel, Severity


class RelatedObject(BaseModel):
    model_config = ConfigDict(frozen=True)

    object_type: str
    object_id: UUID
    label: str | None = None


class ScoringFactor(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    points: Decimal
    note: str
    finding_id: UUID | None = None


class ScoringBreakdown(BaseModel):
    model_config = ConfigDict(frozen=True)

    factors: tuple[ScoringFactor, ...]
    risk_total: Decimal
    risk_level: RiskLevel
    confidence_score: Decimal
    confidence_basis: str


class TypedFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    finding_type: FindingType
    title: str
    description: str
    severity: Severity
    risk_contribution: Decimal
    confidence: Confidence
    evidence_ids: tuple[UUID, ...] = ()
    related_objects: tuple[RelatedObject, ...] = ()
    facts: dict = Field(default_factory=dict)
    detector_version: str = "risk-1"


class FinancialIncident(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    title: str
    findings: tuple[TypedFinding, ...]
    risk_score: Decimal
    risk_level: RiskLevel
    confidence: Confidence
    evidence_ids: tuple[UUID, ...] = ()
    related_objects: tuple[RelatedObject, ...] = ()
    recommended_action: RecommendedAction
    scoring_breakdown: ScoringBreakdown
    explanation: str
    engine_version: str = "risk-1"


class RiskEngineResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    findings: tuple[TypedFinding, ...]
    incidents: tuple[FinancialIncident, ...]
    engine_version: str = "risk-1"
