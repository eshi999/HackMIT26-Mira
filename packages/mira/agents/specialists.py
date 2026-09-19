"""Specialist workers. They call tools; they do not invent finance truth."""

from __future__ import annotations

from uuid import UUID

from mira.agents.authority import decide_authority
from mira.agents.tools import (
    invoice_operational_action,
    tool_assess_risk,
    tool_detect_duplicates,
    tool_evaluate_contract,
    tool_evaluate_invoice,
    tool_evaluate_policy,
    tool_get_ar_aging,
    tool_get_cash_position,
    tool_reconcile_period,
    tool_retrieve_evidence,
    tool_three_way_match,
)
from mira.core.agent_outputs import (
    AgentTaskResult,
    AuditorVerdict,
    AuthorityBasis,
    InvoiceDecision,
    ToolCallRecord,
)
from mira.core.enums import AgentRole, AgentTaskStatus, MatchStatus, RiskLevel
from mira.core.money import Money
from mira.finance.snapshot import FinanceSnapshot


def _dump_call(tool: str, output) -> dict:
    if hasattr(output, "model_dump"):
        payload = output.model_dump(mode="json")
        if tool == "assess_risk" and isinstance(payload, dict):
            payload = {
                "subject_finding_types": payload.get("subject_finding_types"),
                "max_risk_level": payload.get("max_risk_level"),
                "explanation": payload.get("explanation"),
                "confidence": payload.get("confidence"),
            }
        if tool == "reconcile_period" and isinstance(payload, dict):
            payload = {
                "reconciliation_rate": payload.get("reconciliation_rate"),
                "unresolved": len(payload.get("unresolved") or []),
                "explanation": payload.get("explanation"),
            }
    else:
        payload = output
    return ToolCallRecord(
        tool=tool,
        input={},
        output_type=type(output).__name__ if not isinstance(output, dict) else "dict",
        output=payload if isinstance(payload, dict) else {"value": payload},
    ).model_dump(mode="json")


def run_ap_specialist(snapshot: FinanceSnapshot, invoice_id: UUID) -> AgentTaskResult:
    matched = tool_evaluate_invoice(snapshot, invoice_id)
    duplicates = tool_detect_duplicates(snapshot, invoice_id)
    three_way = tool_three_way_match(snapshot, invoice_id)
    action = invoice_operational_action(matched)
    invoice = snapshot.invoice(invoice_id)
    assert invoice is not None
    decision = InvoiceDecision(
        invoice_id=invoice_id,
        action=action,  # type: ignore[arg-type]
        computed_total=Money(amount=invoice.total, currency=invoice.currency),
        duplicate_of_invoice_id=duplicates.duplicate_invoice_ids[0] if duplicates.duplicate_invoice_ids else None,
        explanation=(
            f"AP operational recommendation is {action} from three-way status "
            f"{matched.status.value} and duplicate={duplicates.is_duplicate}."
        ),
        confidence=matched.confidence,
        risk_level=RiskLevel.LOW if matched.status == MatchStatus.MATCH and not duplicates.is_duplicate else RiskLevel.MEDIUM,
        policy_basis="AP does not evaluate spend policy; auditor does.",
        authority_basis=AuthorityBasis(
            policy_name="AP operating procedure",
            clause="match-then-recommend",
            actor_role=AgentRole.ACCOUNTS_PAYABLE.value,
        ),
        evidence=list(matched.evidence),
        requires_human_approval=action != "pay",
    )
    return AgentTaskResult(
        agent_role=AgentRole.ACCOUNTS_PAYABLE,
        status=AgentTaskStatus.COMPLETED,
        artifact_type="InvoiceDecision",
        artifact={
            "decision": decision.model_dump(mode="json"),
            "three_way": three_way.model_dump(mode="json"),
            "duplicates": duplicates.model_dump(mode="json"),
            "tool_calls": [
                _dump_call("evaluate_invoice", matched),
                _dump_call("detect_duplicates", duplicates),
                _dump_call("three_way_match", three_way),
            ],
        },
        explanation=decision.explanation,
        evidence=list(matched.evidence),
    )


def run_ar_specialist(snapshot: FinanceSnapshot) -> AgentTaskResult:
    aging = tool_get_ar_aging(snapshot, min_days=1)
    return AgentTaskResult(
        agent_role=AgentRole.ACCOUNTS_RECEIVABLE,
        status=AgentTaskStatus.COMPLETED,
        artifact_type="ARAgingResult",
        artifact={"aging": aging.model_dump(mode="json"), "tool_calls": [_dump_call("get_ar_aging", aging)]},
        explanation=aging.explanation,
        evidence=[],
    )


def run_treasury_specialist(snapshot: FinanceSnapshot) -> AgentTaskResult:
    cash = tool_get_cash_position(snapshot)
    recon = tool_reconcile_period(snapshot)
    return AgentTaskResult(
        agent_role=AgentRole.TREASURY,
        status=AgentTaskStatus.COMPLETED,
        artifact_type="TreasuryPacket",
        artifact={
            "cash": cash.model_dump(mode="json"),
            "reconciliation_rate": str(recon.reconciliation_rate),
            "unresolved": len(recon.unresolved),
            "tool_calls": [
                _dump_call("get_cash_position", cash),
                _dump_call("reconcile_period", recon),
            ],
        },
        explanation=f"{cash.explanation} Period reconciliation rate {recon.reconciliation_rate}.",
        evidence=list(cash.evidence),
    )


def run_controller_specialist(snapshot: FinanceSnapshot, period: str) -> AgentTaskResult:
    closed = set(snapshot.merged_rules().get("closed_periods", []))
    posted = [inv for inv in snapshot.invoices if (inv.posted_period or "") == period]
    missing_docs = [inv for inv in posted if inv.document_id is None]
    return AgentTaskResult(
        agent_role=AgentRole.CONTROLLER,
        status=AgentTaskStatus.COMPLETED if period not in closed else AgentTaskStatus.BLOCKED,
        artifact_type="CloseReadiness",
        artifact={
            "period": period,
            "posted_invoices": len(posted),
            "missing_documents": [str(i.id) for i in missing_docs],
            "period_closed": period in closed,
        },
        explanation=(
            f"Period {period} is closed in policy."
            if period in closed
            else f"Controller reviewed {len(posted)} postings; {len(missing_docs)} missing documents."
        ),
        evidence=[],
    )


def run_auditor_specialist(
    snapshot: FinanceSnapshot,
    invoice_id: UUID,
    proposed_action: str,
) -> AgentTaskResult:
    policy = tool_evaluate_policy(snapshot, subject_type="invoice", subject_id=invoice_id)
    risk = tool_assess_risk(snapshot, subject_id=invoice_id)
    try:
        contract = tool_evaluate_contract(snapshot, invoice_id)
    except Exception as exc:
        contract = {"has_contract": False, "is_violation": False, "explanation": str(exc)}
    matched = tool_three_way_match(snapshot, invoice_id)
    evidence = tool_retrieve_evidence(snapshot, str(invoice_id))
    reasons: list[str] = []
    missing: list[str] = []
    conflicting: list[str] = []
    if policy.evaluation.violated_policy_ids:
        reasons.append(policy.evaluation.explanation)
    if matched.status.value in {"MISMATCH", "MISSING_EVIDENCE"}:
        missing.append(matched.explanation)
        reasons.append(matched.explanation)
    if isinstance(contract, dict) and contract.get("is_violation"):
        conflicting.append(str(contract.get("explanation")))
        reasons.append(str(contract.get("explanation")))
    if risk.max_risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
        reasons.append(f"Risk engine max level {risk.max_risk_level.value}: {risk.explanation}")
    if not evidence.hits and matched.status.value == "MISSING_EVIDENCE":
        missing.append("No supporting evidence hits for this invoice.")
    reject = bool(reasons) and proposed_action in {"pay", "schedule"}
    verdict = AuditorVerdict(
        accepted=not reject,
        rejected=reject,
        proposed_action=proposed_action,
        verdict="reject" if reject else "accept",
        reasons=reasons,
        policy_violations=list(policy.evaluation.violated_policy_ids),
        missing_evidence=missing,
        conflicting_evidence=conflicting,
        risk_level=risk.max_risk_level,
        confidence=risk.confidence,
        evidence=list(matched.evidence),
        explanation=(
            "Auditor rejects the AP recommendation based on deterministic control evidence."
            if reject
            else "Auditor accepts the AP recommendation; controls did not contradict it."
        ),
    )
    return AgentTaskResult(
        agent_role=AgentRole.AUDIT,
        status=AgentTaskStatus.COMPLETED,
        artifact_type="AuditorVerdict",
        artifact={
            "verdict": verdict.model_dump(mode="json"),
            "tool_calls": [
                _dump_call("evaluate_policy", policy),
                _dump_call("assess_risk", risk),
                _dump_call("three_way_match", matched),
                _dump_call("retrieve_evidence", evidence),
            ],
        },
        explanation=verdict.explanation,
        evidence=list(matched.evidence),
    )


def run_fpna_specialist(snapshot: FinanceSnapshot, question: str | None = None) -> AgentTaskResult:
    from mira.agents.tools import tool_afford_engineers, tool_obtain_public_signal

    cash = tool_get_cash_position(snapshot)
    signal = tool_obtain_public_signal("DGS3MO")
    artifact: dict = {
        "cash": cash.model_dump(mode="json"),
        "public_signal": signal.model_dump(mode="json"),
        "tool_calls": [
            _dump_call("get_cash_position", cash),
            _dump_call("obtain_public_signal", signal),
        ],
    }
    if question and "engineer" in question.lower():
        scenario = tool_afford_engineers(snapshot, 3)
        artifact["scenario"] = scenario.model_dump(mode="json")
        artifact["tool_calls"].append(_dump_call("calculate_finance_metrics", scenario))
        explanation = scenario.recommendation
    else:
        explanation = (
            f"FP&A context: cash {cash.cash.amount}. Public {signal.observation.series_id}="
            f"{signal.observation.value} {signal.observation.unit} as of {signal.observation.as_of}."
        )
    return AgentTaskResult(
        agent_role=AgentRole.FPNA,
        status=AgentTaskStatus.COMPLETED,
        artifact_type="FpnaPacket",
        artifact=artifact,
        explanation=explanation,
        evidence=list(cash.evidence),
    )


def adjudicate_invoice(
    snapshot: FinanceSnapshot,
    invoice_id: UUID,
    ap: AgentTaskResult,
    auditor: AgentTaskResult,
) -> tuple[InvoiceDecision, AgentTaskResult]:
    invoice = snapshot.invoice(invoice_id)
    assert invoice is not None
    ap_decision = InvoiceDecision.model_validate(ap.artifact["decision"])
    verdict = AuditorVerdict.model_validate(auditor.artifact["verdict"])
    policy = tool_evaluate_policy(snapshot, subject_type="invoice", subject_id=invoice_id)
    risk = tool_assess_risk(snapshot, subject_id=invoice_id)
    gate = decide_authority(
        confidence=ap_decision.confidence,
        risk_level=verdict.risk_level if verdict.rejected else risk.max_risk_level,
        is_payment=ap_decision.action == "pay",
        is_sandbox=True,
        policy_requires_human=policy.evaluation.requires_human_approval,
        auditor_rejected=verdict.rejected,
    )
    action = ap_decision.action
    if verdict.rejected:
        action = "escalate" if gate.requires_human_approval else "hold"
        if gate.blocks_action:
            action = "hold"
    final = InvoiceDecision(
        invoice_id=invoice_id,
        action=action,  # type: ignore[arg-type]
        computed_total=ap_decision.computed_total,
        duplicate_of_invoice_id=ap_decision.duplicate_of_invoice_id,
        explanation=(
            f"Mira adjudication: AP recommended {ap_decision.action}; auditor {verdict.verdict}. "
            f"{gate.reason}"
        ),
        confidence=ap_decision.confidence,
        risk_level=verdict.risk_level,
        policy_basis=policy.evaluation.explanation,
        authority_basis=AuthorityBasis(
            policy_name="HITL authority matrix",
            clause=gate.disposition,
            actor_role=AgentRole.MIRA_CFO.value,
        ),
        evidence=list(ap_decision.evidence) + list(verdict.evidence),
        requires_human_approval=gate.requires_human_approval,
    )
    result = AgentTaskResult(
        agent_role=AgentRole.MIRA_CFO,
        status=AgentTaskStatus.COMPLETED,
        artifact_type="InvoiceDecision",
        artifact={
            "decision": final.model_dump(mode="json"),
            "authority": gate.model_dump(mode="json"),
            "ap_action": ap_decision.action,
            "auditor_verdict": verdict.verdict,
        },
        explanation=final.explanation,
        evidence=list(final.evidence),
    )
    return final, result
