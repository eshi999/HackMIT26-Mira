"""Phase 3 agent runtime, memory, close, and tool-boundary tests. No live sponsor APIs."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from mira.agents.authority import decide_authority
from mira.agents.close import CLOSE_NODES, execute_close
from mira.agents.persist import trace_for_decision
from mira.agents.runtime import (
    executive_request,
    handle_event,
    handle_human_feedback,
    overnight_review,
    process_invoice,
)
from mira.agents.specialists import run_ap_specialist, run_auditor_specialist
from mira.agents.tools import (
    TOOL_NAMES,
    tool_assess_risk,
    tool_calculate_autonomy_score,
    tool_calculate_finance_metrics,
    tool_detect_duplicates,
    tool_evaluate_policy,
    tool_get_ar_aging,
    tool_get_cash_position,
    tool_get_company_context,
    tool_obtain_public_signal,
    tool_three_way_match,
)
from mira.core.agent_outputs import Confidence
from mira.core.enums import (
    AgentRole,
    AgentTaskStatus,
    AuthorityDisposition,
    OfficeEventType,
    RiskLevel,
    SavingsSource,
)
from mira.core.models import AgentRun, AgentTask, OfficeEvent, Precedent, SavingsEvent
from mira.evaluation.harness import run_precedent_evaluation
from mira.finance.snapshot import load_snapshot
from mira.forecasting.cash import afford_engineers
from mira.policies.engine import POL_SPEND_CFO_10K, POL_VENDOR_NEW_SECONDARY, evaluate_invoice
from mira.seed import ids


def _snap(session, as_of):
    return load_snapshot(session, ids.COMPANY, as_of)


def test_tools_return_typed_engine_outputs(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    matched = tool_three_way_match(snapshot, ids.INV_EXCEED)
    dups = tool_detect_duplicates(snapshot, ids.INV_4850A)
    policy = tool_evaluate_policy(snapshot, subject_type="invoice", subject_id=ids.INV_AWS_SEP)
    risk = tool_assess_risk(snapshot, ids.INV_AWS_SEP)
    cash = tool_get_cash_position(snapshot)
    aging = tool_get_ar_aging(snapshot, min_days=45)
    ctx = tool_get_company_context(snapshot)
    metrics = tool_calculate_finance_metrics(snapshot)
    autonomy = tool_calculate_autonomy_score(snapshot)
    signal = tool_obtain_public_signal("DGS3MO")
    assert matched.invoice_id == ids.INV_EXCEED
    assert dups.is_duplicate is True
    assert POL_SPEND_CFO_10K in policy.evaluation.violated_policy_ids
    assert risk.max_risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.LOW}
    assert cash.cash.amount > 0
    assert aging.overdue
    assert ctx.company_id == ids.COMPANY
    assert metrics.autonomy_score >= 0
    assert autonomy.autonomy_score == metrics.autonomy_score
    assert signal.observation.series_id == "DGS3MO"
    assert set(TOOL_NAMES) >= {
        "evaluate_invoice",
        "three_way_match",
        "detect_duplicates",
        "evaluate_policy",
        "assess_risk",
        "get_cash_position",
    }


def test_invoice_event_creates_typed_handoffs(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    packet = handle_event(
        seeded_session,
        snapshot,
        OfficeEventType.INVOICE_RECEIVED,
        {"invoice_id": str(ids.INV_EXCEED)},
    )
    seeded_session.flush()
    run = seeded_session.get(AgentRun, UUID(packet["run_id"]))
    tasks = seeded_session.scalars(select(AgentTask).where(AgentTask.agent_run_id == run.id)).all()
    roles = {t.agent_role for t in tasks}
    assert AgentRole.ACCOUNTS_PAYABLE.value in roles
    assert AgentRole.AUDIT.value in roles
    assert AgentRole.MIRA_CFO.value in roles
    for task in tasks:
        assert task.originating_role
        assert task.objective
        assert task.related_object_ids
        assert task.status in {AgentTaskStatus.COMPLETED.value, AgentTaskStatus.BLOCKED.value}
        assert task.result_payload is not None
    events = seeded_session.scalars(select(OfficeEvent).where(OfficeEvent.agent_run_id == run.id)).all()
    assert events
    traces = trace_for_decision(seeded_session, UUID(packet["decision_id"]))
    assert traces[0]["tasks"]
    assert traces[0]["audit_events"]


def test_auditor_disagrees_with_ap_on_seeded_aws_spike(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    ap = run_ap_specialist(snapshot, ids.INV_AWS_SEP)
    auditor = run_auditor_specialist(snapshot, ids.INV_AWS_SEP, ap.artifact["decision"]["action"])
    packet = process_invoice(seeded_session, snapshot, ids.INV_AWS_SEP)
    assert ap.artifact["decision"]["action"] == "pay"
    assert auditor.artifact["verdict"]["rejected"] is True
    assert packet["ap_action"] == "pay"
    assert packet["auditor_verdict"] == "reject"
    assert packet["disagreement"] is True
    assert packet["requires_human_approval"] is True


def test_high_risk_blocks_even_with_high_confidence() -> None:
    gate = decide_authority(
        confidence=Confidence(score=Decimal("0.99"), basis="engine"),
        risk_level=RiskLevel.HIGH,
        is_payment=True,
        is_sandbox=True,
    )
    assert gate.auto_complete is False
    assert gate.blocks_action is True
    assert gate.disposition == AuthorityDisposition.BLOCK.value


def test_low_confidence_escalates() -> None:
    gate = decide_authority(
        confidence=Confidence(score=Decimal("0.40"), basis="incomplete evidence"),
        risk_level=RiskLevel.LOW,
        is_payment=False,
        is_sandbox=True,
    )
    assert gate.requires_human_approval is True
    assert gate.auto_complete is False


def test_real_world_payment_never_auto_executes() -> None:
    gate = decide_authority(
        confidence=Confidence(score=Decimal("0.99"), basis="engine"),
        risk_level=RiskLevel.LOW,
        is_payment=True,
        is_sandbox=False,
    )
    assert gate.blocks_action is True
    assert gate.is_sandbox is False


def test_aws_precedent_learning_and_new_vendor_control(seeded_session, as_of) -> None:
    report = run_precedent_evaluation(seeded_session, as_of)
    assert report["baseline"]["aws_requires_human"] is True
    assert report["learned"]["aws_requires_human"] is False
    assert report["learned"]["precedent_id"]
    assert report["new_vendor_control"]["requires_human"] is True
    assert report["trace_complete"] is True
    remaining = seeded_session.get(Precedent, ids.PRECEDENT_AWS)
    assert remaining is None or remaining.status != "placeholder"


def test_month_end_dependency_ordering(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    status = execute_close(seeded_session, snapshot, fail_keys=frozenset({"document_readiness"}))
    by_key = {t.key: t for t in status.tasks}
    assert by_key["document_readiness"].status == AgentTaskStatus.FAILED
    assert by_key["ap_close"].status == AgentTaskStatus.BLOCKED
    assert by_key["ar_close"].status == AgentTaskStatus.BLOCKED
    assert by_key["bank_reconciliation"].status == AgentTaskStatus.BLOCKED
    assert by_key["payroll_readiness"].status == AgentTaskStatus.COMPLETED
    assert by_key["report_board_preparation"].status == AgentTaskStatus.BLOCKED
    assert "ap_close" in status.blocked
    assert status.completion_pct < Decimal("1.00")
    keys = [n[0] for n in CLOSE_NODES]
    assert keys.index("ap_close") < keys.index("accrual_prepaid_review")
    assert keys.index("document_readiness") < keys.index("ap_close")


def test_workflow_writes_runtime_savings_not_seed_copy(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    overnight_review(seeded_session, snapshot)
    seeded_session.flush()
    runtime = seeded_session.scalars(
        select(SavingsEvent).where(SavingsEvent.source == SavingsSource.RUNTIME.value)
    ).all()
    assert runtime
    protected = sum((row.amount_usd for row in runtime if row.category == "duplicate_prevented"), Decimal("0"))
    hours = sum((row.hours_saved for row in runtime), Decimal("0"))
    assert protected >= Decimal("18400.00")
    assert hours >= Decimal("6.50")
    assert all(row.workflow.startswith("runtime.") for row in runtime)


def test_scenario_analysis_is_deterministic(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    first = afford_engineers(snapshot, headcount=3)
    second = afford_engineers(snapshot, headcount=3)
    assert first.base_case.cash_end_13w == second.base_case.cash_end_13w
    assert first.delayed_receivable_case.weekly[0]["ar_in"] != first.base_case.weekly[0]["ar_in"]
    assert "assumption" in " ".join(first.assumptions).lower() or first.assumptions
    result = executive_request(seeded_session, snapshot, "Can we afford three new engineers?")
    assert result["kind"] == "scenario"
    assert "scenario" in result["recommendation"]["headline"].lower()
    assert result["artifact"]["fpna"]


def test_human_feedback_preserves_policy_controls(
    seeded_session,
    as_of,
) -> None:
    snapshot = _snap(seeded_session, as_of)

    result = handle_human_feedback(
        seeded_session,
        snapshot,
        "AWS infrastructure invoices under $12,000 are pre-approved.",
    )

    assert result["precedent_id"] is None
    assert result["authority_created"] is False

    policy = evaluate_invoice(
        _snap(seeded_session, as_of),
        ids.INV_QUARTZ,
    )

    assert policy is not None
    assert POL_VENDOR_NEW_SECONDARY in policy.violated_policy_ids



def test_runtime_metrics_include_maximor_fields(seeded_session, as_of) -> None:
    metrics = tool_calculate_finance_metrics(_snap(seeded_session, as_of))
    assert metrics.autonomous_completion_rate >= 0
    assert metrics.false_escalation_rate >= 0
    assert metrics.correct_escalation_rate >= 0
    assert metrics.evidence_completeness >= 0
    assert metrics.human_interventions >= 0
    assert Decimal("0.00") <= metrics.reconciliation_rate <= Decimal("1.00")
