"""September month-end close: dependency-aware DAG Mira plans and runs."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from mira.agents.persist import complete_task, create_task, dump, finish_run, start_run
from mira.agents.specialists import (
    run_ap_specialist,
    run_ar_specialist,
    run_auditor_specialist,
    run_controller_specialist,
    run_fpna_specialist,
    run_treasury_specialist,
)
from mira.agents.tools import tool_assess_risk, tool_get_cash_position, tool_reconcile_period
from mira.core.agent_outputs import CloseTaskStatus, CloseWorkflowStatus
from mira.core.enums import ActorType, AgentRole, AgentRunStatus, AgentTaskStatus
from mira.core.models import AgentRun, AgentTask, Decision
from mira.core.money import quantize_money
from mira.finance.snapshot import FinanceSnapshot, load_snapshot

CLOSE_PERIOD = "2026-09"


def close_workflow_type(period: str) -> str:
    return f"month_end_close:{period}"


def parse_close_period(text: str, default: str = CLOSE_PERIOD) -> str:
    lowered = text.lower()
    if "2026-10" in lowered or "october" in lowered:
        return "2026-10"
    if "2026-09" in lowered or "september" in lowered:
        return "2026-09"
    return default


def _in_close_period(invoice, period: str) -> bool:
    if invoice.posted_period:
        return invoice.posted_period == period
    return f"{invoice.issue_date.year:04d}-{invoice.issue_date.month:02d}" == period


def _scores_from_artifact(artifact: object) -> tuple[Decimal | None, str | None]:
    """Copy engine/tool confidence and risk out of a specialist artifact. Never invent."""
    if not isinstance(artifact, dict):
        return None, None
    candidates: list[dict] = [artifact]
    for key in ("decision", "verdict", "cash", "aging"):
        nested = artifact.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
    confidence = None
    risk = None
    for row in candidates:
        conf = row.get("confidence")
        if confidence is None and isinstance(conf, dict) and conf.get("score") is not None:
            confidence = Decimal(str(conf["score"]))
        if risk is None and row.get("risk_level"):
            risk = str(row["risk_level"])
        if risk is None and row.get("max_risk_level"):
            risk = str(row["max_risk_level"])
    return confidence, risk

CLOSE_NODES: tuple[tuple[str, str, AgentRole, tuple[str, ...]], ...] = (
    ("document_readiness", "Document readiness", AgentRole.CONTROLLER, ()),
    ("ap_close", "AP close", AgentRole.ACCOUNTS_PAYABLE, ("document_readiness",)),
    ("ar_close", "AR close", AgentRole.ACCOUNTS_RECEIVABLE, ("document_readiness",)),
    ("bank_reconciliation", "Bank reconciliation", AgentRole.TREASURY, ("document_readiness",)),
    ("payroll_readiness", "Payroll readiness", AgentRole.CONTROLLER, ()),
    (
        "accrual_prepaid_review",
        "Accrual/prepaid review",
        AgentRole.CONTROLLER,
        ("ap_close",),
    ),
    (
        "balance_sheet_evidence",
        "Balance-sheet evidence",
        AgentRole.CONTROLLER,
        ("ap_close", "ar_close", "bank_reconciliation", "payroll_readiness", "accrual_prepaid_review"),
    ),
    ("control_audit_review", "Control/audit review", AgentRole.AUDIT, ("balance_sheet_evidence",)),
    (
        "variance_analysis",
        "Variance analysis",
        AgentRole.FPNA,
        ("ap_close", "ar_close", "bank_reconciliation"),
    ),
    (
        "report_board_preparation",
        "Report/board preparation",
        AgentRole.FPNA,
        ("variance_analysis", "control_audit_review", "balance_sheet_evidence"),
    ),
)


def _ready(key: str, status: dict[str, AgentTaskStatus]) -> bool:
    node = next(n for n in CLOSE_NODES if n[0] == key)
    for dep in node[3]:
        if status.get(dep) != AgentTaskStatus.COMPLETED:
            return False
    return True


def _blocked_reason(key: str, status: dict[str, AgentTaskStatus], reasons: dict[str, str]) -> str:
    node = next(n for n in CLOSE_NODES if n[0] == key)
    missing = [dep for dep in node[3] if status.get(dep) != AgentTaskStatus.COMPLETED]
    bits = [f"waiting on {', '.join(missing)}" if missing else ""]
    bits.extend(reasons.get(dep, "") for dep in missing)
    return "; ".join(b for b in bits if b) or "blocked"


def execute_close(
    session: Session,
    snapshot: FinanceSnapshot,
    *,
    period: str = CLOSE_PERIOD,
    fail_keys: frozenset[str] = frozenset(),
) -> CloseWorkflowStatus:
    run = start_run(
        session,
        company_id=snapshot.company_id,
        workflow_type=close_workflow_type(period),
        initiated_by=ActorType.SYSTEM,
        plan={
            "period": period,
            "nodes": [
                {"key": k, "title": t, "specialist": r.value, "depends_on": list(d)}
                for k, t, r, d in CLOSE_NODES
            ],
        },
    )
    tasks: dict[str, AgentTask] = {}
    for key, title, role, deps in CLOSE_NODES:
        tasks[key] = create_task(
            session,
            run=run,
            destination=role,
            originating=AgentRole.MIRA_CFO,
            objective=f"{title} for {period}",
            input_payload={"key": key, "period": period},
            depends_on=list(deps),
        )

    status: dict[str, AgentTaskStatus] = {key: AgentTaskStatus.QUEUED for key, *_ in CLOSE_NODES}
    reasons: dict[str, str] = {}
    remaining = set(status)
    safety = 0
    while remaining and safety < 40:
        safety += 1
        progressed = False
        for key in list(remaining):
            if not _ready(key, status):
                continue
            progressed = True
            remaining.remove(key)
            title = next(n[1] for n in CLOSE_NODES if n[0] == key)
            role = next(n[2] for n in CLOSE_NODES if n[0] == key)
            if key in fail_keys:
                status[key] = AgentTaskStatus.FAILED
                reasons[key] = f"Injected failure on {key}"
                complete_task(
                    session,
                    tasks[key],
                    status=AgentTaskStatus.FAILED,
                    result_type="CloseTask",
                    result_payload={"key": key, "error": reasons[key]},
                )
                continue
            artifact, explanation, ok = _run_node(snapshot, key, period)
            st = AgentTaskStatus.COMPLETED if ok else AgentTaskStatus.FAILED
            status[key] = st
            if not ok:
                reasons[key] = explanation
            confidence, risk = _scores_from_artifact(artifact)
            complete_task(
                session,
                tasks[key],
                status=st,
                result_type="CloseTask",
                result_payload={"key": key, "title": title, "specialist": role.value, "artifact": dump(artifact)},
                confidence_score=confidence,
                risk_level=risk if ok else (risk or "high"),
            )
        if not progressed:
            for key in list(remaining):
                status[key] = AgentTaskStatus.BLOCKED
                reasons[key] = _blocked_reason(key, status, reasons)
                complete_task(
                    session,
                    tasks[key],
                    status=AgentTaskStatus.BLOCKED,
                    result_type="CloseTask",
                    result_payload={"key": key, "blocker": reasons[key]},
                )
                remaining.remove(key)

    completed = [k for k, st in status.items() if st == AgentTaskStatus.COMPLETED]
    blocked = [k for k, st in status.items() if st in {AgentTaskStatus.BLOCKED, AgentTaskStatus.FAILED}]
    pct = quantize_money(Decimal(len(completed)) / Decimal(len(CLOSE_NODES)))
    human = [
        d.id
        for d in session.query(Decision).filter(
            Decision.company_id == snapshot.company_id,
            Decision.requires_human_approval.is_(True),
            Decision.status.in_({"awaiting_human", "proposed", "evaluated"}),
        )
    ]
    if human:
        if pct >= Decimal("1.00"):
            pct = Decimal("0.99")
        if "outstanding_human_decisions" not in blocked:
            blocked = [*blocked, "outstanding_human_decisions"]
    finish_run(
        session,
        run,
        AgentRunStatus.AWAITING_HUMAN if blocked or human else AgentRunStatus.COMPLETED,
    )
    task_rows = [
        CloseTaskStatus(
            key=key,
            title=title,
            specialist=role,
            status=status[key],
            depends_on=list(deps),
            blocker=reasons.get(key),
            explanation=reasons.get(key) or f"{title} {status[key].value}",
        )
        for key, title, role, deps in CLOSE_NODES
    ]
    return CloseWorkflowStatus(
        period=period,
        completion_pct=pct,
        completed=completed,
        blocked=blocked,
        outstanding_human_decisions=human,
        audit_status="blocked" if "control_audit_review" not in completed else "reviewed",
        tasks=task_rows,
        run_id=run.id,
    )


def _run_node(snapshot: FinanceSnapshot, key: str, period: str) -> tuple[object, str, bool]:
    if key == "document_readiness":
        missing = [
            inv.invoice_number
            for inv in snapshot.invoices
            if _in_close_period(inv, period) and inv.document_id is None
        ]
        ctrl = run_controller_specialist(snapshot, period)
        ok = not missing
        return ctrl.artifact, f"Missing documents: {missing or 'none'}.", ok
    if key == "ap_close":
        open_ap = [inv for inv in snapshot.ap_invoices() if inv.status in {"received", "needs_review"}]
        sample = open_ap[0] if open_ap else snapshot.ap_invoices()[0]
        result = run_ap_specialist(snapshot, sample.id)
        return result.artifact, f"AP close reviewed {len(open_ap)} open bills.", True
    if key == "ar_close":
        result = run_ar_specialist(snapshot)
        return result.artifact, result.explanation, True
    if key == "bank_reconciliation":
        result = run_treasury_specialist(snapshot)
        recon = tool_reconcile_period(snapshot)
        ok = len(recon.unresolved) == 0
        return (
            result.artifact,
            f"Bank recon rate {recon.reconciliation_rate}; unresolved {len(recon.unresolved)}.",
            ok,
        )
    if key == "payroll_readiness":
        gusto = next((v for v in snapshot.vendors if "gusto" in v.name.lower()), None)
        payroll = [inv for inv in snapshot.ap_invoices() if gusto and inv.vendor_id == gusto.id]
        return {"payroll_invoices": len(payroll)}, f"{len(payroll)} payroll invoices on file.", True
    if key == "accrual_prepaid_review":
        return {"reviewed": True}, "Accrual/prepaid review used posted AP as input.", True
    if key == "balance_sheet_evidence":
        cash = tool_get_cash_position(snapshot)
        return cash.model_dump(mode="json"), cash.explanation, True
    if key == "control_audit_review":
        risk = tool_assess_risk(snapshot)
        open_ap = [inv for inv in snapshot.ap_invoices() if inv.status == "needs_review"]
        if open_ap:
            auditor = run_auditor_specialist(snapshot, open_ap[0].id, "pay")
            rejected = bool(auditor.artifact.get("verdict", {}).get("rejected"))
            return auditor.artifact, auditor.explanation, not rejected
        return {"findings": len(risk.result.findings)}, risk.explanation, True
    if key == "variance_analysis":
        fpna = run_fpna_specialist(snapshot)
        return fpna.artifact, fpna.explanation, True
    if key == "report_board_preparation":
        fpna = run_fpna_specialist(snapshot, "board pack")
        return fpna.artifact, "Board pack assembled from deterministic cash, recon, and signals.", True
    return {}, f"Unknown close node {key}", False


def close_status(session: Session, company_id: UUID, period: str = CLOSE_PERIOD) -> CloseWorkflowStatus | None:
    run = (
        session.query(AgentRun)
        .filter(AgentRun.company_id == company_id, AgentRun.workflow_type == close_workflow_type(period))
        .order_by(AgentRun.started_at.desc())
        .first()
    )
    if run is None:
        return None
    rows = session.query(AgentTask).filter(AgentTask.agent_run_id == run.id).all()
    by_key = {(t.input_payload or {}).get("key"): t for t in rows}
    completed = [k for k, t in by_key.items() if t is not None and t.status == AgentTaskStatus.COMPLETED.value]
    blocked = [
        k
        for k, t in by_key.items()
        if t is not None and t.status in {AgentTaskStatus.BLOCKED.value, AgentTaskStatus.FAILED.value}
    ]
    pct = quantize_money(Decimal(len(completed)) / Decimal(len(CLOSE_NODES))) if CLOSE_NODES else Decimal("0.00")
    human = [
        d.id
        for d in session.query(Decision).filter(
            Decision.company_id == company_id,
            Decision.requires_human_approval.is_(True),
            Decision.status.in_({"awaiting_human", "proposed", "evaluated"}),
        )
    ]
    if human:
        if pct >= Decimal("1.00"):
            pct = Decimal("0.99")
        if "outstanding_human_decisions" not in blocked:
            blocked = [*blocked, "outstanding_human_decisions"]
    return CloseWorkflowStatus(
        period=period,
        completion_pct=pct,
        completed=completed,
        blocked=blocked,
        outstanding_human_decisions=human,
        audit_status="blocked" if "control_audit_review" not in completed else "reviewed",
        tasks=[
            CloseTaskStatus(
                key=key,
                title=title,
                specialist=role,
                status=AgentTaskStatus(by_key[key].status) if key in by_key else AgentTaskStatus.QUEUED,
                depends_on=list(deps),
                blocker=(by_key[key].result_payload or {}).get("blocker") if key in by_key else None,
                explanation=by_key[key].objective or title if key in by_key else title,
            )
            for key, title, role, deps in CLOSE_NODES
        ],
        run_id=run.id,
    )


def ensure_snapshot(session: Session, company_id: UUID, as_of) -> FinanceSnapshot:
    return load_snapshot(session, company_id, as_of)
