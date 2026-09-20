from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Profile(StrEnum):
    AP_INVOICE_REVIEW = "AP_INVOICE_REVIEW"
    TREASURY_RECONCILIATION = "TREASURY_RECONCILIATION"
    CFO_VARIANCE_INVESTIGATION = "CFO_VARIANCE_INVESTIGATION"
    FPNA_SCENARIO = "FPNA_SCENARIO"
    AUDIT_REVIEW = "AUDIT_REVIEW"
    EXECUTIVE_QUESTION = "EXECUTIVE_QUESTION"


class ContextRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    company_id: UUID
    task_id: str = Field(min_length=1)
    profile: Profile
    subject_id: UUID | None = None
    vendor_id: UUID | None = None
    customer_id: UUID | None = None
    period: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    query: str = ""
    headcount: int = Field(default=2, ge=0, le=10000)
    target_tokens: int = Field(default=6000, ge=1)
    mode: Literal["off", "on"] | None = None


class ContextProfile(BaseModel):
    model_config = ConfigDict(frozen=True)
    required: frozenset[str]
    optional: frozenset[str]
    irrelevant: frozenset[str]


class ContextItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    key: str
    category: str
    source_id: str
    required: bool
    facts: dict[str, Any]


class ExcludedItem(BaseModel):
    key: str
    reason: Literal["out_of_scope", "irrelevant", "budget"]


class UsageTelemetry(BaseModel):
    task_id: str
    company_id: UUID
    profile: Profile
    model: str | None
    context_items: int
    context_bytes: int
    input_tokens: int
    output_tokens: int | None = None
    optimization_enabled: bool
    timestamp: datetime
    usage_source: Literal["estimated", "provider_reported"]
    scope: str


class ContextPacket(BaseModel):
    model_config = ConfigDict(frozen=True)
    request: ContextRequest
    mode: Literal["off", "on"]
    deterministic_results: dict[str, Any]
    items: tuple[ContextItem, ...]
    known_unknowns: tuple[str, ...]
    excluded: tuple[ExcludedItem, ...]
    truncated: tuple[str, ...] = ()
    model_context: str
    context_bytes: int
    estimated_input_tokens: int
    mandatory_tokens: int
    mandatory_over_budget: bool
    retrieval_source: str
    telemetry: UsageTelemetry
