"""OpenAI Agents SDK wiring.

Mira and specialists are real Agent objects. Tools wrap Phase 2 engines.
When OPENAI_API_KEY is absent, the deterministic runtime in mira.agents.runtime
still executes the same tools — tests never call the network.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from mira.agents.tools import TOOL_NAMES

HAS_OPENAI_AGENTS = False
_import_error: str | None = None

try:
    from agents import Agent, function_tool

    HAS_OPENAI_AGENTS = True
except Exception as exc:  # ImportError or SDK API drift
    Agent = None  # type: ignore[misc, assignment]
    function_tool = None  # type: ignore[misc, assignment]
    _import_error = str(exc)


MIRA_INSTRUCTIONS = """You are Mira, Northstar Labs' digital CFO — one employee, not a chatbot.

You may plan, investigate, interpret, delegate, explain, and choose which tool to call.
You may NOT invent: financial arithmetic, reconciliation results, risk scores, confidence
scores, policy violations, savings amounts, ledger values, approval authority, or contract
calculations. Those come only from tools. If a tool is available, you must call it.
Specialists speak to you in structured results, never as a user-facing swarm.
"""

AP_INSTRUCTIONS = """You are Mira's AP/AR specialist. Call evaluate_invoice, three_way_match,
detect_duplicates, get_ar_aging. Never invent a total or a match status.
"""

TREASURY_INSTRUCTIONS = """You are Mira's treasury specialist. Call get_cash_position,
reconcile_transaction, reconcile_period. Never invent cash.
"""

CONTROLLER_INSTRUCTIONS = """You are Mira's controller. Use company context, evidence, and
policy tools. Never close a period because the prose sounds done.
"""

AUDITOR_INSTRUCTIONS = """You are adversarial. Review other specialists. Call evaluate_policy,
assess_risk, retrieve_evidence, evaluate_contract. Reject when policy, controls, evidence,
risk, or confidence require it. You do not set scores; the tools do.
"""

FPNA_INSTRUCTIONS = """You are FP&A / board specialist. Call get_cash_position,
calculate_finance_metrics, obtain_public_signal. Scenarios must use tool arithmetic.
"""


def openai_configured() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY")) and HAS_OPENAI_AGENTS


def _passthrough(fn: Callable) -> Callable:
    return fn


def sdk_function_tool(fn: Callable) -> Callable:
    if function_tool is None:
        return _passthrough(fn)
    return function_tool(fn)


@sdk_function_tool
def evaluate_invoice(invoice_id: str) -> str:
    """Run the deterministic invoice evaluation / three-way match engine."""
    return (
        "Deterministic tool evaluate_invoice must be executed by mira.agents.runtime "
        f"for invoice {invoice_id}. The model may not compute the match."
    )


@sdk_function_tool
def three_way_match(invoice_id: str) -> str:
    """Run PO / receipt / invoice matching. Engine-owned."""
    return f"Call mira.agents.tools.tool_three_way_match for {invoice_id}."


@sdk_function_tool
def detect_duplicates(invoice_id: str) -> str:
    """Detect duplicate invoices using the reconciliation engine."""
    return f"Call mira.agents.tools.tool_detect_duplicates for {invoice_id}."


@sdk_function_tool
def evaluate_policy(subject_type: str, subject_id: str) -> str:
    """Evaluate spend/vendor/approval policy. Engine-owned pass/fail."""
    return f"Call mira.agents.tools.tool_evaluate_policy for {subject_type} {subject_id}."


@sdk_function_tool
def assess_risk(subject_id: str) -> str:
    """Score risk from the risk engine. Do not invent a score."""
    return f"Call mira.agents.tools.tool_assess_risk for {subject_id}."


@sdk_function_tool
def reconcile_transaction(transaction_id: str) -> str:
    """Reconcile one bank transaction."""
    return f"Call mira.agents.tools.tool_reconcile_transaction for {transaction_id}."


@sdk_function_tool
def reconcile_period() -> str:
    """Reconcile the current period bank feed."""
    return "Call mira.agents.tools.tool_reconcile_period."


@sdk_function_tool
def get_cash_position() -> str:
    """Return operating cash, open AP, open AR from the ledger snapshot."""
    return "Call mira.agents.tools.tool_get_cash_position."


@sdk_function_tool
def get_ar_aging() -> str:
    """Return AR aging from invoice due dates."""
    return "Call mira.agents.tools.tool_get_ar_aging."


@sdk_function_tool
def evaluate_contract(invoice_id: str) -> str:
    """Compare an invoice to extracted contract facts."""
    return f"Call mira.agents.tools.tool_evaluate_contract for {invoice_id}."


@sdk_function_tool
def get_company_context() -> str:
    """Return company facts, memory, and active precedents."""
    return "Call mira.agents.tools.tool_get_company_context."


@sdk_function_tool
def retrieve_evidence(query: str) -> str:
    """Search the evidence index. Do not invent documents."""
    return f"Call mira.agents.tools.tool_retrieve_evidence for {query!r}."


@sdk_function_tool
def calculate_finance_metrics() -> str:
    """Ramp scoreboard metrics from SavingsEvent and engine rates."""
    return "Call mira.agents.tools.tool_calculate_finance_metrics."


@sdk_function_tool
def calculate_autonomy_score() -> str:
    """Autonomy score from the published formula."""
    return "Call mira.agents.tools.tool_calculate_autonomy_score."


@sdk_function_tool
def obtain_public_signal(series_id: str = "DGS3MO") -> str:
    """Fetch a public data observation. Not an interpretation."""
    return f"Call mira.agents.tools.tool_obtain_public_signal for {series_id}."


def _agent(name: str, instructions: str, tools: list) -> Any:
    if Agent is None:
        return {"name": name, "instructions": instructions, "tools": [t.__name__ for t in tools]}
    return Agent(name=name, instructions=instructions, tools=tools)


def build_org() -> dict[str, Any]:
    """Construct the OpenAI Agents SDK org chart. Handoffs are typed in the deterministic runtime."""
    tools = [
        evaluate_invoice,
        three_way_match,
        detect_duplicates,
        evaluate_policy,
        assess_risk,
        reconcile_transaction,
        reconcile_period,
        get_cash_position,
        get_ar_aging,
        evaluate_contract,
        get_company_context,
        retrieve_evidence,
        calculate_finance_metrics,
        calculate_autonomy_score,
        obtain_public_signal,
    ]
    ap = _agent("AP/AR Specialist", AP_INSTRUCTIONS, tools)
    treasury = _agent("Treasury Specialist", TREASURY_INSTRUCTIONS, tools)
    controller = _agent("Controller Specialist", CONTROLLER_INSTRUCTIONS, tools)
    auditor = _agent("Auditor Specialist", AUDITOR_INSTRUCTIONS, tools)
    fpna = _agent("FP&A / Board Specialist", FPNA_INSTRUCTIONS, tools)
    mira_kwargs: dict[str, Any] = {
        "name": "Mira",
        "instructions": MIRA_INSTRUCTIONS,
        "tools": tools,
    }
    if Agent is not None:
        mira = Agent(
            name="Mira",
            instructions=MIRA_INSTRUCTIONS,
            tools=tools,
            handoffs=[ap, treasury, controller, auditor, fpna],
        )
    else:
        mira = {**mira_kwargs, "handoffs": ["ap", "treasury", "controller", "auditor", "fpna"]}
    return {
        "mira": mira,
        "ap": ap,
        "treasury": treasury,
        "controller": controller,
        "auditor": auditor,
        "fpna": fpna,
        "tool_names": list(TOOL_NAMES),
        "sdk_available": HAS_OPENAI_AGENTS,
        "sdk_configured": openai_configured(),
        "import_error": _import_error,
    }


def example_handoff() -> dict[str, str]:
    return {
        "from": "mira_cfo",
        "to": "accounts_payable",
        "objective": "Process invoice AWS-2026-08: match, duplicates, operational recommendation.",
        "persistence": "AgentTask with originating_role, agent_role, related_object_ids, tool_calls, result_payload",
        "note": "The SDK Agent.handoffs list is the model-facing equivalent of that typed task.",
    }
