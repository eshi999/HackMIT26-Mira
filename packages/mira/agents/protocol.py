"""Protocols and org chart for Mira and specialist agents."""

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
        tools=("plan", "review", "escalate", "recommend", "delegate"),
        speaks_to_user=True,
    ),
    SpecialistSpec(
        role=AgentRole.ACCOUNTS_PAYABLE,
        title="AP / AR specialist",
        tools=(
            "evaluate_invoice",
            "three_way_match",
            "detect_duplicates",
            "evaluate_policy",
            "get_ar_aging",
        ),
    ),
    SpecialistSpec(
        role=AgentRole.TREASURY,
        title="Treasury specialist",
        tools=("get_cash_position", "reconcile_transaction", "reconcile_period"),
    ),
    SpecialistSpec(
        role=AgentRole.CONTROLLER,
        title="Controller specialist",
        tools=("get_company_context", "retrieve_evidence", "evaluate_policy"),
    ),
    SpecialistSpec(
        role=AgentRole.PROCUREMENT,
        title="Procurement specialist",
        tools=("budget_check", "vendor_select", "sandbox_payment"),
    ),
    SpecialistSpec(
        role=AgentRole.AUDIT,
        title="Audit specialist",
        tools=("policy_cite", "control_test", "evaluate_policy", "assess_risk", "retrieve_evidence"),
    ),
    SpecialistSpec(
        role=AgentRole.FPNA,
        title="FP&A specialist",
        tools=("forecast", "runway", "calculate_finance_metrics", "obtain_public_signal"),
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
        """Return a typed result from tools. The LLM must not invent the payload."""
        ...
