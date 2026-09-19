"""Zenni Claw CFO skill contract.

Safe routes (implemented later on the API, invoked by Claw):

    GET  /api/v1/skills/cfo/briefing
    GET  /api/v1/skills/cfo/cash
    POST /api/v1/skills/cfo/procurement
    POST /api/v1/skills/cfo/invoice-intake
    POST /api/v1/skills/cfo/decisions/{id}/resolve

Constraints: skill bearer token, authority matrix, idempotency keys,
sandbox payments only unless a human approved a live path (out of scope).
"""

from __future__ import annotations

from mira.integrations.base import AdapterStatus

SKILL_ROUTES = (
    "GET /api/v1/skills/cfo/briefing",
    "GET /api/v1/skills/cfo/cash",
    "POST /api/v1/skills/cfo/procurement",
    "POST /api/v1/skills/cfo/invoice-intake",
    "POST /api/v1/skills/cfo/decisions/{id}/resolve",
)


class ZenniAdapter:
    name = "zenni"

    def __init__(self, skill_token: str | None = None) -> None:
        self.skill_token = skill_token

    def status(self) -> AdapterStatus:
        return AdapterStatus.LIVE if self.skill_token else AdapterStatus.DEMO
