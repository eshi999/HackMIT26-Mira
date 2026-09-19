"""Persist AgentRun / AgentTask / Decision / AuditEvent / SavingsEvent."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from mira.core.enums import (
    ActorType,
    AgentRole,
    AgentRunStatus,
    AgentTaskStatus,
    ApprovalStatus,
    DecisionStatus,
    SavingsCategory,
    SavingsSource,
)
from mira.core.models import AgentRun, AgentTask, Approval, AuditEvent, Decision, SavingsEvent


def now() -> datetime:
    return datetime.now(UTC)


def dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def write_audit(
    session: Session,
    *,
    company_id: UUID,
    event_type: str,
    actor_type: ActorType = ActorType.MIRA,
    actor_id: str | None = None,
    object_type: str | None = None,
    object_id: UUID | None = None,
    correlation_id: UUID | None = None,
    payload: dict | None = None,
) -> AuditEvent:
    row = AuditEvent(
        id=uuid4(),
        company_id=company_id,
        occurred_at=now(),
        actor_type=actor_type.value,
        actor_id=actor_id,
        event_type=event_type,
        object_type=object_type,
        object_id=object_id,
        correlation_id=correlation_id,
        payload=payload or {},
    )
    session.add(row)
    session.flush()
    return row


def start_run(
    session: Session,
    *,
    company_id: UUID,
    workflow_type: str,
    initiated_by: ActorType = ActorType.MIRA,
    initiator_id: str | None = None,
    plan: dict | None = None,
) -> AgentRun:
    run = AgentRun(
        id=uuid4(),
        company_id=company_id,
        workflow_type=workflow_type,
        status=AgentRunStatus.RUNNING.value,
        initiated_by=initiated_by.value,
        initiator_id=initiator_id,
        plan=plan,
        started_at=now(),
    )
    session.add(run)
    session.flush()
    write_audit(
        session,
        company_id=company_id,
        event_type="agent_run_started",
        object_type="agent_run",
        object_id=run.id,
        correlation_id=run.id,
        payload={"workflow_type": workflow_type, "plan": plan or {}},
    )
    return run


def finish_run(session: Session, run: AgentRun, status: AgentRunStatus) -> AgentRun:
    run.status = status.value
    run.completed_at = now()
    session.flush()
    write_audit(
        session,
        company_id=run.company_id,
        event_type="agent_run_finished",
        object_type="agent_run",
        object_id=run.id,
        correlation_id=run.id,
        payload={"status": status.value},
    )
    return run


def create_task(
    session: Session,
    *,
    run: AgentRun,
    destination: AgentRole,
    originating: AgentRole,
    objective: str,
    input_payload: dict | None = None,
    related_object_ids: list[str] | None = None,
    parent_task_id: UUID | None = None,
    depends_on: list[str] | None = None,
) -> AgentTask:
    payload = dict(input_payload or {})
    if depends_on:
        payload["depends_on"] = depends_on
    task = AgentTask(
        id=uuid4(),
        company_id=run.company_id,
        agent_run_id=run.id,
        agent_role=destination.value,
        parent_task_id=parent_task_id,
        originating_role=originating.value,
        objective=objective,
        related_object_ids=related_object_ids or [],
        evidence_ids=[],
        tool_calls=[],
        status=AgentTaskStatus.QUEUED.value,
        input_payload=payload,
        started_at=None,
    )
    session.add(task)
    session.flush()
    write_audit(
        session,
        company_id=run.company_id,
        event_type="agent_task_created",
        actor_type=ActorType.AGENT,
        actor_id=originating.value,
        object_type="agent_task",
        object_id=task.id,
        correlation_id=run.id,
        payload={
            "originating_agent": originating.value,
            "destination_agent": destination.value,
            "objective": objective,
            "related_object_ids": related_object_ids or [],
        },
    )
    return task


def complete_task(
    session: Session,
    task: AgentTask,
    *,
    status: AgentTaskStatus,
    result_type: str,
    result_payload: dict,
    tool_calls: list[dict] | None = None,
    evidence_ids: list[str] | None = None,
    confidence_score: Decimal | None = None,
    risk_level: str | None = None,
) -> AgentTask:
    task.status = status.value
    task.result_type = result_type
    task.result_payload = result_payload
    task.tool_calls = tool_calls or task.tool_calls or []
    task.evidence_ids = evidence_ids or task.evidence_ids or []
    task.confidence_score = confidence_score
    task.risk_level = risk_level
    task.started_at = task.started_at or now()
    task.completed_at = now()
    session.flush()
    write_audit(
        session,
        company_id=task.company_id,
        event_type="agent_task_completed",
        actor_type=ActorType.AGENT,
        actor_id=task.agent_role,
        object_type="agent_task",
        object_id=task.id,
        correlation_id=task.agent_run_id,
        payload={
            "status": status.value,
            "result_type": result_type,
            "tool_calls": [row.get("tool") for row in (tool_calls or [])],
            "confidence": str(confidence_score) if confidence_score is not None else None,
            "risk": risk_level,
        },
    )
    return task


def write_decision(
    session: Session,
    *,
    company_id: UUID,
    run_id: UUID,
    decision_type: str,
    action: str,
    rationale: str,
    structured_output: dict,
    confidence_score: Decimal,
    risk_level: str,
    policy_basis: str,
    authority_basis: str,
    requires_human_approval: bool,
    subject_type: str | None = None,
    subject_id: UUID | None = None,
    dollars_impact: Decimal | None = None,
    hours_saved_estimate: Decimal | None = None,
    status: DecisionStatus | None = None,
) -> Decision:
    decided = (
        status
        if status is not None
        else (DecisionStatus.AWAITING_HUMAN if requires_human_approval else DecisionStatus.EXECUTED)
    )
    row = Decision(
        id=uuid4(),
        company_id=company_id,
        decision_type=decision_type,
        status=decided.value,
        action=action,
        rationale=rationale,
        structured_output=structured_output,
        confidence_score=confidence_score,
        risk_level=risk_level,
        policy_basis=policy_basis,
        authority_basis=authority_basis,
        requires_human_approval=requires_human_approval,
        agent_run_id=run_id,
        subject_type=subject_type,
        subject_id=subject_id,
        dollars_impact=dollars_impact,
        hours_saved_estimate=hours_saved_estimate,
    )
    session.add(row)
    session.flush()
    if requires_human_approval:
        session.add(
            Approval(
                id=uuid4(),
                company_id=company_id,
                subject_type=subject_type or decision_type,
                subject_id=subject_id or row.id,
                status=ApprovalStatus.PENDING.value,
                decision_id=row.id,
                risk_level=risk_level,
                confidence_score=confidence_score,
            )
        )
        session.flush()
    write_audit(
        session,
        company_id=company_id,
        event_type="decision_written",
        object_type="decision",
        object_id=row.id,
        correlation_id=run_id,
        payload={
            "action": action,
            "requires_human_approval": requires_human_approval,
            "risk_level": risk_level,
            "confidence_score": str(confidence_score),
        },
    )
    return row


def write_savings(
    session: Session,
    *,
    company_id: UUID,
    category: SavingsCategory,
    amount_usd: Decimal,
    hours_saved: Decimal,
    workflow: str,
    period: str,
    run_id: UUID,
    related_object_type: str | None = None,
    related_object_id: UUID | None = None,
    note: str | None = None,
) -> SavingsEvent | None:
    existing = (
        session.query(SavingsEvent)
        .filter(
            SavingsEvent.company_id == company_id,
            SavingsEvent.workflow == workflow,
            SavingsEvent.related_object_id == related_object_id,
            SavingsEvent.source == SavingsSource.RUNTIME.value,
        )
        .first()
        if related_object_id is not None
        else None
    )
    if existing is not None:
        return existing
    row = SavingsEvent(
        id=uuid4(),
        company_id=company_id,
        category=category.value,
        amount_usd=amount_usd,
        hours_saved=hours_saved,
        workflow=workflow,
        period=period,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        note=note,
        source=SavingsSource.RUNTIME.value,
        agent_run_id=run_id,
    )
    session.add(row)
    session.flush()
    write_audit(
        session,
        company_id=company_id,
        event_type="savings_event_written",
        object_type="savings_event",
        object_id=row.id,
        correlation_id=run_id,
        payload={"category": category.value, "amount_usd": str(amount_usd), "hours_saved": str(hours_saved)},
    )
    return row


def trace_for_decision(session: Session, decision_id: UUID) -> list[dict]:
    decision = session.get(Decision, decision_id)
    if decision is None:
        return []
    events = (
        session.query(AuditEvent)
        .filter(AuditEvent.correlation_id == decision.agent_run_id)
        .order_by(AuditEvent.occurred_at.asc())
        .all()
    )
    tasks = (
        session.query(AgentTask)
        .filter(AgentTask.agent_run_id == decision.agent_run_id)
        .order_by(AgentTask.created_at.asc())
        .all()
    )
    return [
        {
            "decision_id": str(decision.id),
            "agent_run_id": str(decision.agent_run_id) if decision.agent_run_id else None,
            "tasks": [
                {
                    "task_id": str(t.id),
                    "originating_agent": t.originating_role,
                    "destination_agent": t.agent_role,
                    "objective": t.objective,
                    "related_object_ids": t.related_object_ids,
                    "evidence_ids": t.evidence_ids,
                    "tool_calls": t.tool_calls,
                    "structured_result": t.result_payload,
                    "confidence": str(t.confidence_score) if t.confidence_score is not None else None,
                    "risk": t.risk_level,
                    "status": t.status,
                    "started_at": t.started_at.isoformat() if t.started_at else None,
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                }
                for t in tasks
            ],
            "audit_events": [
                {
                    "event_type": e.event_type,
                    "actor_type": e.actor_type,
                    "object_type": e.object_type,
                    "object_id": str(e.object_id) if e.object_id else None,
                    "occurred_at": e.occurred_at.isoformat(),
                }
                for e in events
            ],
        }
    ]
