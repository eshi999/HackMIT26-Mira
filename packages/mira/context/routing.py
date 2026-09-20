"""Model preference only. No policy, authority, or execution decisions."""

import os
from enum import StrEnum

from pydantic import BaseModel

from mira.context.models import Profile


class Complexity(StrEnum):
    LOW_COMPLEXITY = "LOW_COMPLEXITY"
    STANDARD = "STANDARD"
    HIGH_REASONING = "HIGH_REASONING"


class Route(BaseModel):
    tier: Complexity
    model: str | None


def route(profile: Profile, models: dict[Complexity, str] | None = None) -> Route:
    tier = {
        Profile.AP_INVOICE_REVIEW: Complexity.STANDARD,
        Profile.TREASURY_RECONCILIATION: Complexity.LOW_COMPLEXITY,
        Profile.CFO_VARIANCE_INVESTIGATION: Complexity.HIGH_REASONING,
        Profile.FPNA_SCENARIO: Complexity.HIGH_REASONING,
        Profile.AUDIT_REVIEW: Complexity.STANDARD,
        Profile.EXECUTIVE_QUESTION: Complexity.STANDARD,
    }[profile]
    model = models.get(tier) if models is not None else os.getenv(f"MIRA_MODEL_{tier.value}")
    return Route(tier=tier, model=model or None)
