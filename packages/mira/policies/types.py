"""Machine-evaluable policy results. Agents explain; they do not decide pass/fail."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PolicyCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_id: str
    passed: bool
    reason: str
    used_precedent_id: UUID | None = None


class PolicyEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject_type: str
    subject_id: UUID
    violated_policy_ids: tuple[str, ...] = ()
    passed_policy_ids: tuple[str, ...] = ()
    requires_human_approval: bool = False
    required_roles: tuple[str, ...] = ()
    used_precedent_ids: tuple[UUID, ...] = ()
    checks: tuple[PolicyCheckResult, ...] = ()
    explanation: str = ""


class PolicySubject(BaseModel):
    """Facts the policy engine is allowed to read. Never free text from an LLM."""

    model_config = ConfigDict(frozen=True)

    subject_type: str
    subject_id: UUID
    amount: Decimal
    vendor_id: UUID | None = None
    vendor_name: str | None = None
    vendor_onboarded_at: object | None = None
    is_new_vendor: bool = False
    requested_by_user_id: UUID | None = None
    approver_user_id: UUID | None = None
    as_of: object | None = None
    category: str | None = None
    posted_period: str | None = None
    has_secondary_approval: bool = False
