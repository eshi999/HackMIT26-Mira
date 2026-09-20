"""API-facing Pydantic schemas. Keep these aligned with DATA_MODEL.md."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CompanyOut(ORMModel):
    id: UUID
    slug: str
    name: str
    legal_name: str
    industry: str
    stage: str
    base_currency: str
    timezone: str
    employee_count: int | None
    description: str | None


class HealthOut(BaseModel):
    status: str
    service: str = "mira-api"
    version: str = "0.1.0"


class ReadyOut(HealthOut):
    database: str
    company: str | None = None
    seeded: bool = False


class SavingsTotals(BaseModel):
    dollars_protected: Decimal
    dollars_saved: Decimal = Decimal("0.00")
    hours_saved: Decimal
    period: str
    source: str = "runtime"


class SignalOut(BaseModel):
    series_id: str
    title: str
    value: Decimal
    unit: str
    as_of: date
    source: str
    note: str | None = None


class DecisionBrief(BaseModel):
    id: UUID
    decision_type: str
    status: str
    action: str
    rationale: str
    confidence_score: Decimal
    risk_level: str
    policy_basis: str
    authority_basis: str
    requires_human_approval: bool
    dollars_impact: Decimal | None = None
    hours_saved_estimate: Decimal | None = None
    subject_type: str | None = None


class FindingBrief(BaseModel):
    id: UUID
    finding_type: str
    severity: str
    title: str
    description: str
    status: str


class InvoiceBrief(BaseModel):
    id: UUID
    invoice_number: str
    vendor_name: str | None = None
    total: Decimal
    currency: str
    status: str
    due_date: date | None = None
    is_duplicate_suspect: bool = False


class DocumentBrief(BaseModel):
    id: UUID
    filename: str
    document_class: str
    storage_backend: str
    storage_uri: str
    content_hash: str | None = None
    extraction_status: str | None = None
    ingested_at: datetime | None = None
    lineage: str | None = None
    evidence_title: str | None = None


class CashPosition(BaseModel):
    amount: Decimal
    currency: str = "USD"
    as_of: datetime | None = None
    account_name: str = "Operating cash"


class CloseBrief(BaseModel):
    period: str
    completion_pct: Decimal
    completed: list[str] = Field(default_factory=list)
    blocked: list[str] = Field(default_factory=list)
    audit_status: str = "not_started"


class BriefingOut(BaseModel):
    company: CompanyOut
    mira_status: str = "on_duty"
    headline: str
    narrative: str
    cash: CashPosition
    open_ap: Decimal
    savings: SavingsTotals
    pending_decisions: list[DecisionBrief] = Field(default_factory=list)
    findings: list[FindingBrief] = Field(default_factory=list)
    invoices: list[InvoiceBrief] = Field(default_factory=list)
    signals: list[SignalOut] = Field(default_factory=list)
    documents_ingested: int = 0
    inbox: list[DocumentBrief] = Field(default_factory=list)
    sandbox_notice: str = (
        "Any purchase or payment shown as sandbox/simulated is not a live transfer."
    )
    autonomous_completion_rate: Decimal = Decimal("0.00")
    reconciliation_rate: Decimal = Decimal("0.00")
    open_incidents: int = 0
    blocked_payments: int = 0
    pending_approvals: int = 0
    close: CloseBrief | None = None
