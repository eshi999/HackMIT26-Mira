"""AP three-way match and bank reconciliation result types."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from mira.core.agent_outputs import Confidence, EvidenceReference
from mira.core.enums import MatchStatus, ReconStage
from mira.core.money import Money


class ThreeWayMatchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    invoice_id: UUID
    po_id: UUID | None
    receipt_ids: tuple[UUID, ...] = ()
    status: MatchStatus
    invoice_total: Money
    po_total: Money | None = None
    received_amount: Money | None = None
    amount_delta: Money | None = None
    duplicate_invoice_ids: tuple[UUID, ...] = ()
    violated_policy_ids: tuple[str, ...] = ()
    confidence: Confidence
    evidence: list[EvidenceReference] = Field(default_factory=list)
    explanation: str


class ReconLeg(BaseModel):
    model_config = ConfigDict(frozen=True)

    object_type: str
    object_id: UUID
    amount: Decimal
    reference: str | None = None


class ReconMatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    transaction_id: UUID
    counterpart_ids: tuple[UUID, ...]
    counterpart_type: str
    stage: ReconStage
    amount_delta: Decimal
    confidence: Confidence
    evidence: list[EvidenceReference] = Field(default_factory=list)
    explanation: str
    forced: bool = False
    economic_kind: str | None = None


class ReconciliationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    matches: tuple[ReconMatch, ...] = ()
    unresolved: tuple[ReconMatch, ...] = ()
    matched_transaction_ids: tuple[UUID, ...] = ()
    matched_invoice_ids: tuple[UUID, ...] = ()
    reconciliation_rate: Decimal
    explanation: str
