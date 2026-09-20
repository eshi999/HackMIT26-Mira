"""Mira CFO runtime.

The LLM may plan, investigate, interpret, delegate, explain, and choose tools.
It may not invent financial arithmetic, reconciliation, risk, confidence, policy,
savings, ledger values, approval authority, or contract calculations.

This module is the deterministic executor for Mira's finance workflows.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from mira.agents.auth import CanonicalActor
from mira.agents.close import CLOSE_PERIOD, close_status, execute_close, parse_close_period
from mira.agents.events import attach_run, finish_event, record_event
from mira.agents.persist import (
    complete_task,
    create_task,
    decision_status_for_action,
    existing_runtime_invoice_decision,
    finish_run,
    now,
    resolve_decision,
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
    collect_aws_spend_evidence,
    tool_assess_risk,
    tool_calculate_finance_metrics,
    tool_get_cash_position,
)
from mira.core.agent_outputs import CFORecommendation, CloseWorkflowStatus, Confidence
from mira.core.enums import (
    ActorType,
    AgentRole,
    AgentRunStatus,
    AgentTaskStatus,
    OfficeEventStatus,
    OfficeEventType,
    SavingsCategory,
)
from mira.core.models import AgentRun, AgentTask, Decision, OfficeEvent
from mira.finance.snapshot import FinanceSnapshot, load_snapshot
from mira.memory.store import (
    authorize_precedent,
    bootstrap_from_snapshot,
    parse_human_feedback_precedent,
    record_factual,
)
from mira.risk.engine import persist_result

INTAKE_HOURS = Decimal("0.25")
DUPLICATE_HOURS = Decimal("1.50")
POLICY_HOURS = Decimal("0.50")
WORKFLOW_INVOICE = "runtime.invoice_received"


def overnight_workflow_type(as_of) -> str:
    return f"overnight_review:{as_of.isoformat()}"


def duplicate_canonical_id(invoice_id: UUID, duplicate_ids: list | tuple) -> UUID:
    members = [invoice_id, *[UUID(str(item)) for item in duplicate_ids]]
    return min(members)


def _period(snapshot: FinanceSnapshot) -> str:
    return f"{snapshot.as_of.year:04d}-{snapshot.as_of.month:02d}"


def _hours_for(decision_action: str, is_duplicate: bool, policy_blocked: bool) -> Decimal:
    hours = INTAKE_HOURS
    if is_duplicate:
        hours += DUPLICATE_HOURS
    if policy_blocked:
        hours += POLICY_HOURS
    return hours


def _packet_from_decision(session: Session, decision, invoice_id: UUID) -> dict:
    tasks: list[AgentTask] = []
    if decision.agent_run_id is not None:
        tasks = session.query(AgentTask).filter(AgentTask.agent_run_id == decision.agent_run_id).all()
    invoice_key = str(invoice_id)

    def _for_role(role: str) -> AgentTask | None:
        return next(
            (
                task
                for task in tasks
                if task.agent_role == role and invoice_key in (task.related_object_ids or [])
            ),
            None,
        )

    ap = _for_role(AgentRole.ACCOUNTS_PAYABLE.value)
    auditor = _for_role(AgentRole.AUDIT.value)
    ap_action = None
    auditor_verdict = None
    if ap and isinstance(ap.result_payload, dict):
        ap_action = (ap.result_payload.get("decision") or {}).get("action")
    if auditor and isinstance(auditor.result_payload, dict):
        auditor_verdict = (auditor.result_payload.get("verdict") or {}).get("verdict")
    proposed = ap_action or decision.action
    return {
        "run_id": str(decision.agent_run_id) if decision.agent_run_id else None,
        "decision_id": str(decision.id),
        "invoice_id": str(invoice_id),
        "ap_action": proposed,
        "auditor_verdict": auditor_verdict or ("reject" if decision.requires_human_approval else "accept"),
        "mira_action": decision.action,
        "requires_human_approval": decision.requires_human_approval,
        "disagreement": proposed != decision.action or auditor_verdict == "reject",
        "replayed": True,
    }


def process_invoice(
    session: Session,
    snapshot: FinanceSnapshot,
    invoice_id: UUID,
    *,
    run: AgentRun | None = None,
    event: OfficeEvent | None = None,
) -> dict:
    """Event-driven AP packet: AP recommends, auditor reviews, Mira adjudicates."""
    existing = existing_runtime_invoice_decision(session, snapshot.company_id, invoice_id)
    if existing is not None:
        packet = _packet_from_decision(session, existing, invoice_id)
        if event is not None and existing.agent_run_id is not None:
            attach_run(session, event, existing.agent_run_id)
            finish_event(
                session,
                event,
                OfficeEventStatus.AWAITING_HUMAN
                if existing.requires_human_approval
                else OfficeEventStatus.COMPLETED,
            )
        return packet
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
    dollar_category = SavingsCategory.INTAKE_HOURS
    savings_subject_id = invoice_id
    if is_dup:
        dup_ids = (ap.artifact.get("duplicates") or {}).get("duplicate_invoice_ids") or []
        savings_subject_id = duplicate_canonical_id(invoice_id, dup_ids)
        dollars = invoice.total
        dollar_category = SavingsCategory.DUPLICATE_PREVENTED
    elif policy_blocked and final.action in {"hold", "reject", "escalate"}:
        dollars = invoice.total
        dollar_category = SavingsCategory.POLICY_BLOCK

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
        status=decision_status_for_action(final.action, requires_human_approval=final.requires_human_approval),
    )
    write_savings(
        session,
        company_id=snapshot.company_id,
        category=SavingsCategory.INTAKE_HOURS,
        amount_usd=Decimal("0.00"),
        hours_saved=hours,
        workflow=WORKFLOW_INVOICE,
        period=_period(snapshot),
        run_id=run.id,
        related_object_type="invoice",
        related_object_id=invoice_id,
        note=final.explanation,
    )
    if dollars:
        write_savings(
            session,
            company_id=snapshot.company_id,
            category=dollar_category,
            amount_usd=dollars,
            hours_saved=Decimal("0.00"),
            workflow=WORKFLOW_INVOICE,
            period=_period(snapshot),
            run_id=run.id,
            related_object_type="duplicate_group" if is_dup else "invoice",
            related_object_id=savings_subject_id,
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
    authorizer: str = "unauthenticated",
) -> dict:
    """Record a comment. Never creates approval authority or pre-approval precedent."""
    event = record_event(
        session,
        company_id=snapshot.company_id,
        event_type=OfficeEventType.HUMAN_FEEDBACK_RECEIVED,
        payload={"message": message, "authorizer": authorizer},
    )
    run = start_run(
        session,
        company_id=snapshot.company_id,
        workflow_type="human_feedback",
        initiated_by=ActorType.USER,
        plan={"message": message, "authority_created": False},
    )
    attach_run(session, event, run.id)
    task = create_task(
        session,
        run=run,
        destination=AgentRole.POLICY,
        originating=AgentRole.MIRA_CFO,
        objective="Store human feedback as a comment. Do not mint spend authority from free text.",
        input_payload={"message": message},
    )
    parsed = parse_human_feedback_precedent(message)
    record_factual(
        session,
        company_id=snapshot.company_id,
        statement=message.strip(),
        fact_key="human_feedback.comment",
        subject_type="feedback",
        fact_value={"message": message, "authorizer": authorizer, "parsed_but_not_authorized": bool(parsed)},
        source="human_feedback",
        as_of=snapshot.as_of,
    )
    parser_confidence = Confidence(
        score=Decimal("0.99"),
        basis="Free-text feedback is stored as a comment and cannot create precedent or spending authority.",
    )
    complete_task(
        session,
        task,
        status=AgentTaskStatus.COMPLETED,
        result_type="HumanFeedback",
        result_payload={
            "stored": True,
            "precedent": False,
            "authority_created": False,
            "message": message,
            "recognized_rule_shape": bool(parsed),
            "confidence": parser_confidence.model_dump(mode="json"),
        },
        confidence_score=parser_confidence.score,
        risk_level="low",
    )
    finish_run(session, run, AgentRunStatus.COMPLETED)
    finish_event(session, event, OfficeEventStatus.COMPLETED)
    return {
        "run_id": str(run.id),
        "precedent_id": None,
        "parsed": parsed,
        "authority_created": False,
    }


def teach_precedent(
    session: Session,
    snapshot: FinanceSnapshot,
    actor: CanonicalActor,
    *,
    summary: str,
    reusable_rule: str,
    outcome: str,
    scope: str,
    vendor: str | None,
    category: str | None,
    amount_threshold: Decimal | str,
    effective_date,
    evidence: list[str],
) -> dict:
    row = authorize_precedent(
        session,
        company_id=snapshot.company_id,
        actor=actor,
        summary=summary,
        reusable_rule=reusable_rule,
        outcome=outcome,
        period=_period(snapshot),
        scope=scope,
        vendor=vendor,
        category=category,
        amount_threshold=amount_threshold,
        effective_date=effective_date,
        evidence=evidence,
    )
    return {
        "precedent_id": str(row.id),
        "status": row.status,
        "outcome": row.outcome,
        "authorizer": row.authorizer,
        "grants_exemption": row.status == "active" and row.outcome in {"pre_approved", "approved", "pre-approved", "preapproved"},
    }


def resolve_human_decision(
    session: Session,
    *,
    decision_id: UUID,
    actor: CanonicalActor,
    approved: bool,
    comment: str | None = None,
) -> dict:
    if not actor.can_resolve_approvals:
        raise PermissionError(f"{actor.name} is not authorized to resolve approvals.")
    decision = resolve_decision(
        session,
        decision_id=decision_id,
        actor_user_id=actor.user_id,
        actor_name=actor.name,
        approved=approved,
        comment=comment,
    )
    return {
        "decision_id": str(decision.id),
        "status": decision.status,
        "action": decision.action,
        "payment_executed": False,
        "actor": actor.name,
    }


def handle_month_end(session: Session, snapshot: FinanceSnapshot, *, period: str = CLOSE_PERIOD) -> CloseWorkflowStatus:
    existing = close_status(session, snapshot.company_id, period)
    if existing is not None:
        return existing
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
    workflow_key = overnight_workflow_type(snapshot.as_of)
    existing = (
        session.query(AgentRun)
        .filter(AgentRun.company_id == snapshot.company_id, AgentRun.workflow_type == workflow_key)
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
        workflow_type=workflow_key,
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
    unhandled = [
        inv
        for inv in interesting
        if existing_runtime_invoice_decision(session, snapshot.company_id, inv.id) is None
    ]
    queued = unhandled + [inv for inv in interesting if inv not in unhandled]
    processed = []
    for invoice in queued[:limit]:
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
        confidence_score=Decimal(str(treasury.artifact["cash"]["confidence"]["score"])),
        risk_level=tool_assess_risk(snapshot).max_risk_level.value,
    )
    persist_result(session, snapshot.company_id, _cached_risk(snapshot), now())
    awaiting = any(row["requires_human_approval"] for row in processed)
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
            confidence_score=Decimal(str(result.artifact["cash"]["confidence"]["score"])),
            risk_level=tool_assess_risk(snapshot).max_risk_level.value,
        )
    finish_run(session, run, AgentRunStatus.COMPLETED)
    finish_event(session, event, OfficeEventStatus.COMPLETED)
    return {"run_id": str(run.id), "event_id": str(event.id)}


def executive_request(session: Session, snapshot: FinanceSnapshot, request: str) -> dict:
    """Learned language routing over deterministic Mira finance tools."""

    from mira.agents.intent_router import predict_intent

    routing = predict_intent(request)

    def _money(value) -> str:
        amount = Decimal(value)
        magnitude = abs(amount)

        if magnitude >= Decimal("1000000"):
            return f"${amount / Decimal('1000000'):.2f}M"

        if magnitude >= Decimal("1000"):
            rendered = f"{amount / Decimal('1000'):.1f}"
            if rendered.endswith(".0"):
                rendered = rendered[:-2]
            return f"${rendered}K"

        return f"${amount:,.0f}"

    run = start_run(
        session,
        company_id=snapshot.company_id,
        workflow_type="executive_request",
        initiated_by=ActorType.USER,
        plan={
            "request": request,
            "intent": routing.intent,
            "intent_confidence": routing.confidence,
            "intent_model": routing.model_version,
        },
    )

    intake = create_task(
        session,
        run=run,
        destination=AgentRole.MIRA_CFO,
        originating=AgentRole.MIRA_CFO,
        objective="Route an executive request to deterministic finance work.",
        input_payload={
            "request": request,
            "intent": routing.intent,
            "intent_confidence": routing.confidence,
        },
    )

    live = load_snapshot(
        session,
        snapshot.company_id,
        snapshot.as_of,
    )

    cash = tool_get_cash_position(live)

    artifact: dict = {
        "request": request,
        "routing": {
            "intent": routing.intent,
            "confidence": round(routing.confidence, 4),
            "model_version": routing.model_version,
            "low_confidence": routing.low_confidence,
        },
    }

    intent = routing.intent

    if intent == "cash_position":
        artifact["kind"] = "cash_position"
        artifact["cash"] = cash.model_dump(mode="json")

        headline = f"Operating cash is {_money(cash.cash.amount)}."

        body = (
            f"Open AP is {_money(cash.open_ap.amount)} and "
            f"open AR is {_money(cash.open_ar.amount)} "
            f"as of {live.as_of}."
        )

    elif intent == "ap_ar":
        artifact["kind"] = "ap_ar"
        artifact["cash"] = cash.model_dump(mode="json")

        headline = (
            f"Open AP is {_money(cash.open_ap.amount)} and "
            f"open AR is {_money(cash.open_ar.amount)}."
        )

        net = Decimal(cash.open_ar.amount) - Decimal(cash.open_ap.amount)

        if net >= 0:
            body = (
                f"Receivables exceed payables by {_money(net)} "
                "in the current snapshot."
            )
        else:
            body = (
                f"Payables exceed receivables by {_money(abs(net))} "
                "in the current snapshot."
            )

    elif intent == "pending_approvals":
        pending = (
            session.query(Decision)
            .filter(
                Decision.company_id == live.company_id,
                Decision.requires_human_approval.is_(True),
                Decision.status.in_({"awaiting_human", "proposed"}),
            )
            .all()
        )

        artifact["kind"] = "pending_approvals"
        artifact["pending"] = [
            {
                "id": str(d.id),
                "action": d.action,
                "risk_level": d.risk_level,
                "rationale": d.rationale,
            }
            for d in pending
        ]

        headline = (
            f"{len(pending)} item"
            f"{'s' if len(pending) != 1 else ''} need your review."
        )

        body = (
            "These items remain behind explicit human approval gates. "
            "Mira will not execute a gated payment automatically."
        )

    elif intent == "close_status":
        period = parse_close_period(request)

        status = close_status(
            session,
            live.company_id,
            period,
        )

        artifact["kind"] = "close_status"
        artifact["period"] = period
        artifact["close"] = (
            status.model_dump(mode="json")
            if status is not None
            else None
        )

        if status is None:
            headline = f"{period} close has not been run yet."

            body = (
                "The executive request is read-only. "
                "Run the explicit close workflow to create close state."
            )
        else:
            percent = float(status.completion_pct) * 100

            headline = f"{period} close is {percent:.0f}% complete."

            body = (
                f"{len(status.completed)} complete and "
                f"{len(status.blocked)} blocked."
            )

            if status.blocked:
                blockers = ", ".join(
                    item.replace("_", " ")
                    for item in status.blocked[:3]
                )

                body += f" Top blockers: {blockers}."

    elif intent == "scenario":
        fpna = run_fpna_specialist(
            live,
            request,
        )

        artifact["kind"] = "scenario"
        artifact["fpna"] = fpna.artifact

        headline = (
            "I ran that scenario against the current finance snapshot."
        )

        body = fpna.explanation

    elif intent == "vendor_spend":
        if any(
            word in request.lower()
            for word in ("aws", "amazon", "cloud")
        ):
            period = _period(live)
            investigation = collect_aws_spend_evidence(
                live,
                period,
            )

            artifact["kind"] = "vendor_spend"
            artifact["investigation"] = {
                "execution": "deterministic",
                "model_invoked": False,
                "tools_invoked": ["collect_aws_spend_evidence"],
                "evidence": investigation,
            }

            headline = (
                f"AWS spend changed by "
                f"{_money(investigation['delta'])} in {period}."
            )

            body = (
                f"AWS spend is "
                f"{_money(investigation['period_total'])} in "
                f"{investigation['period']} versus "
                f"{_money(investigation['prior_total'])} in "
                f"{investigation['prior_period']}. "
                "These values come directly from canonical ledger "
                "invoice totals."
            )

        else:
            artifact["kind"] = "vendor_spend"

            headline = (
                "Tell me which vendor or spend category you want investigated."
            )

            body = (
                "I can inspect a named vendor, AWS or cloud spend, "
                "or a specific variance without changing finance state."
            )

    elif intent in {
        "invoice_investigation",
        "evidence_query",
    }:
        from mira.agents.tools import tool_retrieve_evidence

        evidence = tool_retrieve_evidence(
            live,
            request,
        )

        if hasattr(evidence, "model_dump"):
            evidence_payload = evidence.model_dump(mode="json")
        elif isinstance(evidence, dict):
            evidence_payload = evidence
        else:
            evidence_payload = {
                "result": str(evidence),
            }

        artifact["kind"] = intent
        artifact["evidence"] = evidence_payload

        headline = (
            "I retrieved the records related to that request."
        )

        body = (
            "The underlying result is grounded in Mira's persisted "
            "evidence and retrieval layer. Open Evidence for the "
            "full source lineage."
        )

    elif intent == "risk_controls":
        from mira.core.models import Incident

        risk = tool_assess_risk(live)

        incidents = (
            session.query(Incident)
            .filter(
                Incident.company_id == live.company_id,
                Incident.status.in_({
                    "open",
                    "investigating",
                }),
            )
            .all()
        )

        artifact["kind"] = "risk_controls"
        artifact["risk"] = risk.model_dump(mode="json")
        artifact["open_incidents"] = len(incidents)

        headline = (
            f"{len(incidents)} open incident"
            f"{'s' if len(incidents) != 1 else ''}."
        )

        body = (
            f"The deterministic risk engine's highest current "
            f"risk level is {risk.max_risk_level.value}."
        )

    elif intent == "finance_review":
        metrics = tool_calculate_finance_metrics(
            live,
            runtime_only=True,
        )

        runtime_savings = [
            row
            for row in live.savings
            if row.source == "runtime"
        ]

        protected = sum(
            (
                row.amount_usd
                for row in runtime_savings
                if row.category
                in {
                    "duplicate_prevented",
                    "policy_block",
                }
            ),
            Decimal("0.00"),
        )

        hours_returned = sum(
            (
                row.hours_saved
                for row in runtime_savings
            ),
            Decimal("0.00"),
        )

        pending_count = (
            session.query(Decision)
            .filter(
                Decision.company_id == live.company_id,
                Decision.requires_human_approval.is_(True),
                Decision.status.in_({
                    "awaiting_human",
                    "proposed",
                }),
            )
            .count()
        )

        artifact["kind"] = "finance_review"
        artifact["metrics"] = metrics.model_dump(
            mode="json",
        )
        artifact["cash"] = cash.model_dump(
            mode="json",
        )
        artifact["dollars_protected"] = str(protected)
        artifact["hours_returned"] = str(hours_returned)
        artifact["pending_approvals"] = pending_count
        artifact["read_only"] = True

        headline = "Overnight finance review is complete."

        impact = ""

        if protected > 0 or hours_returned > 0:
            impact = (
                f"Mira protected {_money(protected)} "
                f"and returned {hours_returned:.1f} hours. "
            )

        body = (
            f"{impact}"
            f"Operating cash is {_money(cash.cash.amount)}, "
            f"with {_money(cash.open_ap.amount)} in open AP "
            f"and {_money(cash.open_ar.amount)} in open AR. "
            f"{pending_count} items still need your review."
        )

    elif intent == "help":
        artifact["kind"] = "help"

        headline = "Ask me about the finance operation."

        body = (
            "I can answer questions about cash, AP and AR, "
            "approvals, month-end close, invoices, vendor spend, "
            "risk controls, evidence, and hiring scenarios."
        )

    else:
        artifact["kind"] = "unknown"

        headline = (
            "I need a little more specificity to ground that request."
        )

        body = (
            "Try asking about cash, AP or AR, approvals, "
            "close, an invoice, vendor spend, risk controls, "
            "evidence, or a hiring scenario."
        )

    risk = tool_assess_risk(live)

    complete_task(
        session,
        intake,
        status=AgentTaskStatus.COMPLETED,
        result_type="ExecutiveRequest",
        result_payload=artifact,
        confidence_score=cash.confidence.score,
        risk_level=risk.max_risk_level.value,
    )

    recommendation = CFORecommendation(
        headline=headline,
        body=body,
        action=artifact.get(
            "kind",
            "review",
        ),
        priority="action",
        confidence=cash.confidence,
        risk_level=risk.max_risk_level,
        policy_basis=(
            "A trained intent model selects a bounded finance "
            "workflow. Financial facts remain deterministic."
        ),
        authority_basis=mira_authority(),
        evidence=[],
        requires_human_approval=False,
    )

    finish_run(
        session,
        run,
        AgentRunStatus.COMPLETED,
    )

    return {
        "run_id": str(run.id),
        "request": request,
        "kind": artifact.get("kind"),
        "routing": artifact["routing"],
        "recommendation": recommendation.model_dump(
            mode="json",
        ),
        "artifact": artifact,
    }

def mira_authority():
    from mira.core.agent_outputs import AuthorityBasis

    return AuthorityBasis(
        policy_name="Safe action API",
        clause="executive_request",
        actor_role=AgentRole.MIRA_CFO.value,
    )


def command_center_briefing_data(session: Session, snapshot: FinanceSnapshot) -> dict:
    """Read-only command-center projection.

    Workflow execution happens separately. Refreshing the UI must never
    create decisions, memories, savings events, close runs, or external calls.
    """
    live = snapshot
    period = _period(live)

    runtime_savings = [s for s in live.savings if s.source == "runtime"]
    protected = sum(
        (
            s.amount_usd
            for s in runtime_savings
            if s.category in {"duplicate_prevented", "policy_block"}
        ),
        Decimal("0.00"),
    )
    saved = sum(
        (
            s.amount_usd
            for s in runtime_savings
            if s.category in {"early_pay_discount", "other"}
        ),
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
        select(func.count())
        .select_from(Incident)
        .where(
            Incident.company_id == live.company_id,
            Incident.status.in_({"open", "investigating"}),
        )
    )

    blocked_payments = session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.company_id == live.company_id,
            Payment.status.in_({"failed", "void"}),
        )
    )

    close = close_status(session, live.company_id, period)

    if protected == 0 and hours == 0:
        headline = "Good morning, Elena. Overnight review has no recorded impact yet."
    else:
        headline = (
            f"Good morning, Elena. Mira protected ${protected:,.0f} overnight "
            f"and returned {hours:.1f} hours."
        )

    attention = (
        f"{len(pending)} items need your review."
        if pending
        else "No human approvals are waiting."
    )

    narrative = (
        f"{attention} "
        f"Operating cash ${cash.cash.amount:,.0f} · "
        f"Open AP ${cash.open_ap.amount:,.0f} · "
        f"Reconciliation {float(recon) * 100:.0f}%."
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
        "autonomous_completion_rate": metrics.autonomous_completion_rate,
        "open_incidents": int(incidents or 0),
        "blocked_payments": int(blocked_payments or 0),
        "pending_approvals": len(pending),
        "close": close.model_dump(mode="json") if close else None,
        "pending_decisions": pending,
    }
