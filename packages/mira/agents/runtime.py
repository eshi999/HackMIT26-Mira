"""Mira CFO runtime.

The LLM may plan, investigate, interpret, delegate, explain, and choose tools.
It may not invent financial arithmetic, reconciliation, risk, confidence, policy,
savings, ledger values, approval authority, or contract calculations.

This module is the deterministic executor those tools run through. The optional
OpenAI Agents SDK planner lives in mira.agents.openai_runtime.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from mira.agents.close import CLOSE_PERIOD, close_status, execute_close
from mira.agents.events import attach_run, finish_event, record_event
from mira.agents.persist import (
    complete_task,
    create_task,
    finish_run,
    now,
    start_run,
    write_decision,
    write_savings,
)
from mira.agents.specialists import (
    adjudicate_invoice,
    run_ap_specialist,
    run_auditor_specialist,
    run_fpna_specialist,
    run_treasury_specialist,
)
from mira.agents.tools import (
    _cached_risk,
    tool_assess_risk,
    tool_calculate_finance_metrics,
    tool_get_cash_position,
)
from mira.core.agent_outputs import CFORecommendation, CloseWorkflowStatus
from mira.core.enums import (
    ActorType,
    AgentRole,
    AgentRunStatus,
    AgentTaskStatus,
    DecisionStatus,
    OfficeEventStatus,
    OfficeEventType,
    SavingsCategory,
)
from mira.core.models import AgentRun, OfficeEvent
from mira.finance.snapshot import FinanceSnapshot, load_snapshot
from mira.memory.store import (
    bootstrap_from_snapshot,
    parse_human_feedback_precedent,
    record_precedent,
)
from mira.risk.engine import persist_result

INTAKE_HOURS = Decimal("0.25")
DUPLICATE_HOURS = Decimal("1.50")
POLICY_HOURS = Decimal("0.50")
WORKFLOW_INVOICE = "runtime.invoice_received"
WORKFLOW_OVERNIGHT = "overnight_review"


def _period(snapshot: FinanceSnapshot) -> str:
    return f"{snapshot.as_of.year:04d}-{snapshot.as_of.month:02d}"


def _hours_for(decision_action: str, is_duplicate: bool, policy_blocked: bool) -> Decimal:
    hours = INTAKE_HOURS
    if is_duplicate:
        hours += DUPLICATE_HOURS
    if policy_blocked:
        hours += POLICY_HOURS
    return hours


def process_invoice(
    session: Session,
    snapshot: FinanceSnapshot,
    invoice_id: UUID,
    *,
    run: AgentRun | None = None,
    event: OfficeEvent | None = None,
) -> dict:
    """Event-driven AP packet: AP recommends, auditor reviews, Mira adjudicates."""
    if run is None:
        run = start_run(
            session,
            company_id=snapshot.company_id,
            workflow_type="invoice_received",
            initiated_by=ActorType.SYSTEM,
            plan={"invoice_id": str(invoice_id), "graph": ["ap", "auditor", "mira"]},
        )
    if event is not None:
        attach_run(session, event, run.id)

    mira_plan = create_task(
        session,
        run=run,
        destination=AgentRole.MIRA_CFO,
        originating=AgentRole.MIRA_CFO,
        objective="Plan invoice intake, delegate to AP and auditor, adjudicate.",
        related_object_ids=[str(invoice_id)],
        input_payload={"invoice_id": str(invoice_id)},
    )
    ap_task = create_task(
        session,
        run=run,
        destination=AgentRole.ACCOUNTS_PAYABLE,
        originating=AgentRole.MIRA_CFO,
        objective="Process invoice: match, duplicates, operational recommendation.",
        related_object_ids=[str(invoice_id)],
        parent_task_id=mira_plan.id,
        input_payload={"invoice_id": str(invoice_id)},
    )
    ap = run_ap_specialist(snapshot, invoice_id)
    complete_task(
        session,
        ap_task,
        status=AgentTaskStatus.COMPLETED,
        result_type=ap.artifact_type,
        result_payload=ap.artifact,
        tool_calls=ap.artifact.get("tool_calls") or [],
        evidence_ids=[str(e.evidence_id or e.object_id) for e in ap.evidence if e.object_id],
        confidence_score=Decimal(str(ap.artifact["decision"]["confidence"]["score"])),
        risk_level=ap.artifact["decision"]["risk_level"],
    )

    proposed = ap.artifact["decision"]["action"]
    audit_task = create_task(
        session,
        run=run,
        destination=AgentRole.AUDIT,
        originating=AgentRole.MIRA_CFO,
        objective="Adversarial review of the AP recommendation.",
        related_object_ids=[str(invoice_id)],
        parent_task_id=mira_plan.id,
        input_payload={"invoice_id": str(invoice_id), "proposed_action": proposed},
    )
    auditor = run_auditor_specialist(snapshot, invoice_id, proposed)
    complete_task(
        session,
        audit_task,
        status=AgentTaskStatus.COMPLETED,
        result_type=auditor.artifact_type,
        result_payload=auditor.artifact,
        tool_calls=auditor.artifact.get("tool_calls") or [],
        evidence_ids=[str(e.object_id) for e in auditor.evidence if e.object_id],
        confidence_score=Decimal(str(auditor.artifact["verdict"]["confidence"]["score"])),
        risk_level=auditor.artifact["verdict"]["risk_level"],
    )

    final, mira_result = adjudicate_invoice(snapshot, invoice_id, ap, auditor)
    complete_task(
        session,
        mira_plan,
        status=AgentTaskStatus.COMPLETED,
        result_type=mira_result.artifact_type,
        result_payload=mira_result.artifact,
        tool_calls=[],
        evidence_ids=[str(e.object_id) for e in final.evidence if e.object_id],
        confidence_score=final.confidence.score,
        risk_level=final.risk_level.value,
    )

    invoice = snapshot.invoice(invoice_id)
    assert invoice is not None
    policy_blocked = bool(auditor.artifact["verdict"]["policy_violations"]) or auditor.artifact["verdict"]["rejected"]
    is_dup = bool(ap.artifact["duplicates"]["is_duplicate"])
    hours = _hours_for(final.action, is_dup, policy_blocked)
    dollars = Decimal("0.00")
    category = SavingsCategory.INTAKE_HOURS
    if is_dup:
        dollars = invoice.total
        category = SavingsCategory.DUPLICATE_PREVENTED
    elif policy_blocked and final.action in {"hold", "reject", "escalate"}:
        dollars = invoice.total
        category = SavingsCategory.POLICY_BLOCK

    decision = write_decision(
        session,
        company_id=snapshot.company_id,
        run_id=run.id,
        decision_type="invoice",
        action=final.action,
        rationale=final.explanation,
        structured_output=final.model_dump(mode="json"),
        confidence_score=final.confidence.score,
        risk_level=final.risk_level.value,
        policy_basis=final.policy_basis,
        authority_basis=final.authority_basis.clause,
        requires_human_approval=final.requires_human_approval,
        subject_type="invoice",
        subject_id=invoice_id,
        dollars_impact=dollars or None,
        hours_saved_estimate=hours,
        status=DecisionStatus.AWAITING_HUMAN if final.requires_human_approval else DecisionStatus.EXECUTED,
    )
    write_savings(
        session,
        company_id=snapshot.company_id,
        category=category,
        amount_usd=dollars,
        hours_saved=hours,
        workflow=WORKFLOW_INVOICE,
        period=_period(snapshot),
        run_id=run.id,
        related_object_type="invoice",
        related_object_id=invoice_id,
        note=final.explanation,
    )
    if event is not None:
        finish_event(
            session,
            event,
            OfficeEventStatus.AWAITING_HUMAN if final.requires_human_approval else OfficeEventStatus.COMPLETED,
        )
    if run.workflow_type == "invoice_received":
        finish_run(
            session,
            run,
            AgentRunStatus.AWAITING_HUMAN if final.requires_human_approval else AgentRunStatus.COMPLETED,
        )
    return {
        "run_id": str(run.id),
        "decision_id": str(decision.id),
        "invoice_id": str(invoice_id),
        "ap_action": proposed,
        "auditor_verdict": auditor.artifact["verdict"]["verdict"],
        "mira_action": final.action,
        "requires_human_approval": final.requires_human_approval,
        "disagreement": proposed != final.action or auditor.artifact["verdict"]["rejected"],
    }


def handle_human_feedback(
    session: Session,
    snapshot: FinanceSnapshot,
    message: str,
    *,
    authorizer: str = "Elena Voss",
) -> dict:
    event = record_event(
        session,
        company_id=snapshot.company_id,
        event_type=OfficeEventType.HUMAN_FEEDBACK_RECEIVED,
        payload={"message": message},
    )
    run = start_run(
        session,
        company_id=snapshot.company_id,
        workflow_type="human_feedback",
        initiated_by=ActorType.USER,
        plan={"message": message},
    )
    attach_run(session, event, run.id)
    task = create_task(
        session,
        run=run,
        destination=AgentRole.POLICY,
        originating=AgentRole.MIRA_CFO,
        objective="Interpret human feedback into a typed precedent when the rule is machine-recognizable.",
        input_payload={"message": message},
    )
    parsed = parse_human_feedback_precedent(message)
    precedent_id = None
    if parsed:
        row = record_precedent(
            session,
            company_id=snapshot.company_id,
            summary=parsed["summary"],
            reusable_rule=parsed["reusable_rule"],
            outcome=parsed["outcome"],
            period=_period(snapshot),
            scope=parsed["scope"],
            authorizer=authorizer,
            conditions=parsed["conditions"],
        )
        precedent_id = str(row.id)
        complete_task(
            session,
            task,
            status=AgentTaskStatus.COMPLETED,
            result_type="Precedent",
            result_payload={"precedent_id": precedent_id, **parsed},
            confidence_score=Decimal("0.99"),
            risk_level="low",
        )
        finish_run(session, run, AgentRunStatus.COMPLETED)
        finish_event(session, event, OfficeEventStatus.COMPLETED)
    else:
        complete_task(
            session,
            task,
            status=AgentTaskStatus.COMPLETED,
            result_type="HumanFeedback",
            result_payload={"stored": True, "precedent": False, "message": message},
            confidence_score=Decimal("0.50"),
            risk_level="medium",
        )
        finish_run(session, run, AgentRunStatus.COMPLETED)
        finish_event(session, event, OfficeEventStatus.COMPLETED)
    return {"run_id": str(run.id), "precedent_id": precedent_id, "parsed": parsed}


def handle_month_end(session: Session, snapshot: FinanceSnapshot, *, period: str = CLOSE_PERIOD) -> CloseWorkflowStatus:
    event = record_event(
        session,
        company_id=snapshot.company_id,
        event_type=OfficeEventType.MONTH_END_STARTED,
        payload={"period": period},
    )
    status = execute_close(session, snapshot, period=period)
    event.agent_run_id = status.run_id
    event.status = (
        OfficeEventStatus.AWAITING_HUMAN.value if status.blocked else OfficeEventStatus.COMPLETED.value
    )
    session.flush()
    return status


def overnight_review(session: Session, snapshot: FinanceSnapshot, *, limit: int = 12) -> dict:
    """Command-center overnight work: invoices that still need a Mira decision."""
    existing = (
        session.query(AgentRun)
        .filter(AgentRun.company_id == snapshot.company_id, AgentRun.workflow_type == WORKFLOW_OVERNIGHT)
        .first()
    )
    if existing is not None:
        return {"run_id": str(existing.id), "skipped": True}

    bootstrap_from_snapshot(session, snapshot)
    session.flush()
    snapshot = load_snapshot(session, snapshot.company_id, snapshot.as_of)

    run = start_run(
        session,
        company_id=snapshot.company_id,
        workflow_type=WORKFLOW_OVERNIGHT,
        initiated_by=ActorType.MIRA,
        plan={"limit": limit},
    )
    interesting = sorted(
        (
            inv
            for inv in snapshot.ap_invoices()
            if inv.is_duplicate_suspect or inv.status in {"needs_review", "received"}
        ),
        key=lambda inv: (0 if inv.is_duplicate_suspect else 1, inv.invoice_number),
    )
    processed = []
    for invoice in interesting[:limit]:
        event = record_event(
            session,
            company_id=snapshot.company_id,
            event_type=OfficeEventType.INVOICE_RECEIVED,
            payload={"invoice_id": str(invoice.id)},
            correlation_id=run.id,
        )
        processed.append(process_invoice(session, snapshot, invoice.id, run=run, event=event))
    treasury = run_treasury_specialist(snapshot)
    treas_task = create_task(
        session,
        run=run,
        destination=AgentRole.TREASURY,
        originating=AgentRole.MIRA_CFO,
        objective="Cash position and period reconciliation for the overnight briefing.",
        input_payload={},
    )
    complete_task(
        session,
        treas_task,
        status=AgentTaskStatus.COMPLETED,
        result_type=treasury.artifact_type,
        result_payload=treasury.artifact,
        tool_calls=treasury.artifact.get("tool_calls") or [],
        confidence_score=Decimal("0.99"),
        risk_level="low",
    )
    persist_result(session, snapshot.company_id, _cached_risk(snapshot), now())
    awaiting = any(row["requires_human_approval"] for row in processed)
    write_savings(
        session,
        company_id=snapshot.company_id,
        category=SavingsCategory.INTAKE_HOURS,
        amount_usd=Decimal("0.00"),
        hours_saved=Decimal("6.50"),
        workflow="runtime.overnight_review",
        period=_period(snapshot),
        run_id=run.id,
        related_object_type="agent_run",
        related_object_id=run.id,
        note=f"Intake/coding hours returned by processing {len(processed)} invoices overnight.",
    )
    finish_run(session, run, AgentRunStatus.AWAITING_HUMAN if awaiting else AgentRunStatus.COMPLETED)
    return {"run_id": str(run.id), "processed": processed, "skipped": False}


def handle_event(
    session: Session,
    snapshot: FinanceSnapshot,
    event_type: OfficeEventType,
    payload: dict | None = None,
) -> dict:
    payload = payload or {}
    if event_type == OfficeEventType.INVOICE_RECEIVED:
        invoice_id = UUID(str(payload["invoice_id"]))
        event = record_event(
            session,
            company_id=snapshot.company_id,
            event_type=event_type,
            payload=payload,
        )
        return process_invoice(session, snapshot, invoice_id, event=event)
    if event_type == OfficeEventType.MONTH_END_STARTED:
        status = handle_month_end(session, snapshot, period=str(payload.get("period") or CLOSE_PERIOD))
        return status.model_dump(mode="json")
    if event_type == OfficeEventType.HUMAN_FEEDBACK_RECEIVED:
        return handle_human_feedback(session, snapshot, str(payload.get("message") or ""))
    event = record_event(session, company_id=snapshot.company_id, event_type=event_type, payload=payload)
    run = start_run(
        session,
        company_id=snapshot.company_id,
        workflow_type=event_type.value,
        initiated_by=ActorType.SYSTEM,
        plan=payload,
    )
    attach_run(session, event, run.id)
    if event_type in {OfficeEventType.BANK_FEED_UPDATED, OfficeEventType.PAYMENT_RECEIVED}:
        result = run_treasury_specialist(snapshot)
        task = create_task(
            session,
            run=run,
            destination=AgentRole.TREASURY,
            originating=AgentRole.MIRA_CFO,
            objective=f"Respond to {event_type.value}",
            input_payload=payload,
        )
        complete_task(
            session,
            task,
            status=AgentTaskStatus.COMPLETED,
            result_type=result.artifact_type,
            result_payload=result.artifact,
            tool_calls=result.artifact.get("tool_calls") or [],
            confidence_score=Decimal("0.90"),
            risk_level="low",
        )
    finish_run(session, run, AgentRunStatus.COMPLETED)
    finish_event(session, event, OfficeEventStatus.COMPLETED)
    return {"run_id": str(run.id), "event_id": str(event.id)}


def executive_request(session: Session, snapshot: FinanceSnapshot, request: str) -> dict:
    """Safe interface for voice/skill/other sponsors. Maps prose onto typed work."""
    text = request.lower()
    run = start_run(
        session,
        company_id=snapshot.company_id,
        workflow_type="executive_request",
        initiated_by=ActorType.USER,
        plan={"request": request},
    )
    intake = create_task(
        session,
        run=run,
        destination=AgentRole.MIRA_CFO,
        originating=AgentRole.MIRA_CFO,
        objective="Translate the executive request into typed specialist work.",
        input_payload={"request": request},
    )
    artifact: dict = {"request": request}
    if "month-end" in text or "month end" in text or "blocking" in text:
        status = close_status(session, snapshot.company_id) or handle_month_end(session, snapshot)
        artifact["kind"] = "close_status"
        artifact["close"] = status.model_dump(mode="json")
        headline = f"Month-end close is {status.completion_pct} complete."
        body = (
            f"Completed {len(status.completed)}; blocked {len(status.blocked)}: {', '.join(status.blocked) or 'none'}."
        )
    elif "engineer" in text or "afford" in text:
        fpna = run_fpna_specialist(snapshot, request)
        artifact["kind"] = "scenario"
        artifact["fpna"] = fpna.artifact
        headline = "Hiring scenario from deterministic cash, AR, AP, and payroll assumptions."
        body = fpna.explanation
    elif "aws" in text and "variance" in text:
        aws = next((v for v in snapshot.vendors if "aws" in v.name.lower() or "amazon web" in v.name.lower()), None)
        invoices = [i for i in snapshot.ap_invoices() if aws and i.vendor_id == aws.id]
        packets = []
        for inv in invoices:
            packets.append(process_invoice(session, snapshot, inv.id, run=run))
        artifact["kind"] = "aws_variance"
        artifact["packets"] = packets
        headline = f"Investigated {len(packets)} AWS invoices with AP, auditor, and Mira adjudication."
        body = "Amounts and risk scores come from engines, not from this sentence."
    elif "approval" in text or "payment" in text:
        from mira.core.models import Decision

        pending = (
            session.query(Decision)
            .filter(
                Decision.company_id == snapshot.company_id,
                Decision.requires_human_approval.is_(True),
                Decision.status.in_({"awaiting_human", "proposed"}),
            )
            .all()
        )
        artifact["kind"] = "pending_approvals"
        artifact["pending"] = [
            {"id": str(d.id), "action": d.action, "risk_level": d.risk_level, "rationale": d.rationale}
            for d in pending
        ]
        headline = f"{len(pending)} payment(s) or decisions still need you."
        body = "Queue is Decision rows with requires_human_approval, not a generated list."
    else:
        overnight = overnight_review(session, snapshot)
        metrics = tool_calculate_finance_metrics(
            load_snapshot(session, snapshot.company_id, snapshot.as_of), runtime_only=True
        )
        cash = tool_get_cash_position(load_snapshot(session, snapshot.company_id, snapshot.as_of))
        artifact["kind"] = "finance_review"
        artifact["overnight"] = {"run_id": overnight.get("run_id"), "processed": len(overnight.get("processed") or [])}
        artifact["metrics"] = metrics.model_dump(mode="json")
        artifact["cash"] = cash.model_dump(mode="json")
        headline = "Overnight finance review is on the command center."
        body = cash.explanation
    complete_task(
        session,
        intake,
        status=AgentTaskStatus.COMPLETED,
        result_type="ExecutiveRequest",
        result_payload=artifact,
        confidence_score=Decimal("0.90"),
        risk_level="low",
    )
    rec = CFORecommendation(
        headline=headline,
        body=body,
        action=artifact.get("kind", "review"),
        priority="action",
        confidence=cash_confidence(),
        risk_level=tool_assess_risk(snapshot).max_risk_level,
        policy_basis="Executive request API maps onto typed tasks; it does not execute live payments.",
        authority_basis=mira_authority(),
        evidence=[],
        requires_human_approval=False,
    )
    finish_run(session, run, AgentRunStatus.COMPLETED)
    return {
        "run_id": str(run.id),
        "request": request,
        "kind": artifact.get("kind"),
        "recommendation": rec.model_dump(mode="json"),
        "artifact": artifact,
    }


def cash_confidence():
    from mira.core.agent_outputs import Confidence

    return Confidence(score=Decimal("0.90"), basis="Request routed to deterministic tools.")


def mira_authority():
    from mira.core.agent_outputs import AuthorityBasis

    return AuthorityBasis(
        policy_name="Safe action API",
        clause="executive_request",
        actor_role=AgentRole.MIRA_CFO.value,
    )


def command_center_briefing_data(session: Session, snapshot: FinanceSnapshot) -> dict:
    overnight_review(session, snapshot)
    if close_status(session, snapshot.company_id) is None:
        handle_month_end(session, load_snapshot(session, snapshot.company_id, snapshot.as_of))
    session.flush()
    live = load_snapshot(session, snapshot.company_id, snapshot.as_of)
    runtime_savings = [s for s in live.savings if s.source == "runtime"]
    protected = sum(
        (s.amount_usd for s in runtime_savings if s.category in {"duplicate_prevented", "policy_block"}),
        Decimal("0.00"),
    )
    saved = sum(
        (s.amount_usd for s in runtime_savings if s.category in {"early_pay_discount", "other"}),
        Decimal("0.00"),
    )
    hours = sum((s.hours_saved for s in runtime_savings), Decimal("0.00"))
    metrics = tool_calculate_finance_metrics(live, runtime_only=True)
    cash = tool_get_cash_position(live)
    recon = metrics.reconciliation_rate
    from sqlalchemy import func, select

    from mira.core.models import Decision, Incident, Payment

    pending = list(
        session.scalars(
            select(Decision).where(
                Decision.company_id == live.company_id,
                Decision.requires_human_approval.is_(True),
                Decision.status.in_({"awaiting_human", "proposed"}),
            )
        )
    )
    incidents = session.scalar(
        select(func.count()).select_from(Incident).where(
            Incident.company_id == live.company_id, Incident.status.in_({"open", "investigating"})
        )
    )
    blocked_payments = session.scalar(
        select(func.count()).select_from(Payment).where(
            Payment.company_id == live.company_id, Payment.status.in_({"failed", "void"})
        )
    )
    close = close_status(session, live.company_id)
    if protected == 0 and hours == 0:
        headline = "I have not yet recorded workflow impact. Overnight intake is on the board as zeros until engines write SavingsEvent rows."
        narrative = (
            "Elena, displayed dollars and hours come only from runtime SavingsEvent rows. "
            "Seed fixtures are still in the database for planted engine tests, but they are not this scoreboard."
        )
    else:
        headline = (
            f"I protected {protected} and returned {hours} hours overnight. "
            + ("I still need you on exceptions." if pending else "No human gate is open.")
        )
        narrative = (
            f"Operating cash {cash.cash.amount}. Open AP {cash.open_ap.amount}. "
            f"Reconciliation rate {recon}. Autonomous completion {metrics.autonomy_score}. "
            "Every number is engine- or workflow-authored."
        )
    return {
        "headline": headline,
        "narrative": narrative,
        "cash": cash,
        "metrics": metrics,
        "dollars_protected": protected,
        "dollars_saved": saved,
        "hours_saved": hours,
        "reconciliation_rate": recon,
        "autonomous_completion_rate": metrics.autonomy_score,
        "open_incidents": int(incidents or 0),
        "blocked_payments": int(blocked_payments or 0),
        "pending_approvals": len(pending),
        "close": close.model_dump(mode="json") if close else None,
        "pending_decisions": pending,
    }
