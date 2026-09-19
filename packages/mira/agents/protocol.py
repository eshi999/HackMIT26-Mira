"""Protocols for Mira and specialist agents. No runtime."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from mira.core.agent_outputs import AgentTaskResult
from mira.core.enums import AgentRole


class SpecialistSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: AgentRole
    title: str
    reports_to: AgentRole = AgentRole.MIRA_CFO
    tools: tuple[str, ...] = ()
    speaks_to_user: bool = False


MIRA_ORG: tuple[SpecialistSpec, ...] = (
    SpecialistSpec(
        role=AgentRole.MIRA_CFO,
        title="Digital CFO",
        reports_to=AgentRole.MIRA_CFO,
        tools=("plan", "review", "escalate", "recommend"),
        speaks_to_user=True,
    ),
    SpecialistSpec(
        role=AgentRole.ACCOUNTS_PAYABLE,
        title="AP specialist",
        tools=("extract_invoice", "detect_duplicates"),
    ),
    SpecialistSpec(
        role=AgentRole.TREASURY,
        title="Treasury specialist",
        tools=("cash_position", "read_public_signals"),
    ),
    SpecialistSpec(
        role=AgentRole.PROCUREMENT,
        title="Procurement specialist",
        tools=("budget_check", "vendor_select", "sandbox_payment"),
    ),
    SpecialistSpec(
        role=AgentRole.AUDIT,
        title="Audit specialist",
        tools=("policy_cite", "control_test"),
    ),
    SpecialistSpec(
        role=AgentRole.FPNA,
        title="FP&A specialist",
        tools=("forecast", "runway"),
    ),
    SpecialistSpec(
        role=AgentRole.POLICY,
        title="Policy specialist",
        tools=("evaluate_policy",),
    ),
    SpecialistSpec(
        role=AgentRole.EVIDENCE,
        title="Evidence specialist",
        tools=("ingest_document", "search_evidence"),
    ),
)


class Agent(Protocol):
    role: AgentRole

    def run(self, payload: dict) -> AgentTaskResult:
        """Return a typed result. Implementations belong in a later slice."""
        ...
