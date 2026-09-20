"""Hackathon demo authentication: bearer token → canonical employee.

Not a production IdP. Mutating financial authority requires a mapped actor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import UUID

from mira.core.enums import UserRole
from mira.seed import ids

DEFAULT_DEMO_TOKEN = "mira-demo-elena"


@dataclass(frozen=True)
class CanonicalActor:
    token_id: str
    user_id: UUID
    employee_id: UUID | None
    name: str
    role: str
    can_authorize_spend: bool
    can_resolve_approvals: bool


def _actors() -> dict[str, CanonicalActor]:
    return {
        os.environ.get("MIRA_DEMO_TOKEN", DEFAULT_DEMO_TOKEN): CanonicalActor(
            token_id="elena",
            user_id=ids.ELENA,
            employee_id=ids.ELENA_EMP,
            name="Elena Voss",
            role=UserRole.CFO.value,
            can_authorize_spend=True,
            can_resolve_approvals=True,
        ),
        "mira-demo-jordan": CanonicalActor(
            token_id="jordan",
            user_id=ids.JORDAN,
            employee_id=ids.JORDAN_EMP,
            name="Jordan Hale",
            role=UserRole.CONTROLLER.value,
            can_authorize_spend=False,
            can_resolve_approvals=True,
        ),
        "mira-demo-sam": CanonicalActor(
            token_id="sam",
            user_id=ids.SAM,
            employee_id=ids.SAM_EMP,
            name="Sam Okonkwo",
            role=UserRole.AP.value,
            can_authorize_spend=False,
            can_resolve_approvals=False,
        ),
    }


def resolve_demo_token(token: str | None) -> CanonicalActor | None:
    if not token:
        return None
    return _actors().get(token.strip())


def parse_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()
