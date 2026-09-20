"""Repeatable Maximor evaluation: baseline vs learned-state metrics."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from mira.agents.auth import resolve_demo_token
from mira.agents.persist import trace_for_decision
from mira.agents.runtime import process_invoice, teach_precedent
from mira.agents.tools import tool_calculate_finance_metrics
from mira.core.enums import InvoiceDirection, InvoiceStatus, POStatus, ReceiptStatus
from mira.core.models import (
    AgentTask,
    GoodsReceipt,
    GoodsReceiptLine,
    Invoice,
    InvoiceLine,
    Precedent,
    PurchaseOrder,
    PurchaseOrderLine,
)
from mira.evaluation.metrics import FinanceMetrics
from mira.finance.snapshot import load_snapshot
from mira.seed import ids


def _metrics(session: Session, as_of: date) -> FinanceMetrics:
    snapshot = load_snapshot(session, ids.COMPANY, as_of)
    return tool_calculate_finance_metrics(snapshot)


def _add_aws_invoice(session: Session, *, number: str, total: Decimal, issue: date) -> Invoice:
    po = PurchaseOrder(
        id=uuid4(),
        company_id=ids.COMPANY,
        vendor_id=ids.AWS,
        po_number=f"PO-{number}",
        status=POStatus.RECEIVED.value,
        requested_by_user_id=ids.PRIYA,
        total=total,
    )
    session.add(po)
    session.flush()
    line = PurchaseOrderLine(
        id=uuid4(),
        company_id=ids.COMPANY,
        purchase_order_id=po.id,
        description="AWS infrastructure",
        quantity=Decimal("1"),
        unit_price=total,
        amount=total,
        account_id=ids.EXPENSE_CLOUD,
    )
    session.add(line)
    session.flush()
    gr = GoodsReceipt(
        id=uuid4(),
        company_id=ids.COMPANY,
        purchase_order_id=po.id,
        received_at=datetime(issue.year, issue.month, issue.day, 12, 0, tzinfo=UTC),
        status=ReceiptStatus.POSTED.value,
    )
    session.add(gr)
    session.flush()
    session.add(
        GoodsReceiptLine(
            id=uuid4(),
            company_id=ids.COMPANY,
            goods_receipt_id=gr.id,
            purchase_order_line_id=line.id,
            quantity=Decimal("1"),
            description="AWS period",
        )
    )
    inv = Invoice(
        id=uuid4(),
        company_id=ids.COMPANY,
        vendor_id=ids.AWS,
        invoice_number=number,
        direction=InvoiceDirection.AP.value,
        issue_date=issue,
        due_date=issue,
        subtotal=total,
        total=total,
        status=InvoiceStatus.NEEDS_REVIEW.value,
        purchase_order_id=po.id,
        document_id=ids.DOC_VOLUME,
        posted_period=f"{issue.year:04d}-{issue.month:02d}",
    )
    session.add(inv)
    session.add(
        InvoiceLine(
            company_id=ids.COMPANY,
            invoice_id=inv.id,
            description="AWS infrastructure",
            quantity=Decimal("1"),
            unit_price=total,
            amount=total,
            account_id=ids.EXPENSE_CLOUD,
        )
    )
    session.flush()
    return inv


def run_precedent_evaluation(session: Session, as_of: date) -> dict:
    """Baseline (no AWS precedent) vs learned state after human feedback."""
    seeded = session.get(Precedent, ids.PRECEDENT_AWS)
    if seeded is not None:
        session.delete(seeded)
        session.flush()

    baseline_inv = _add_aws_invoice(
        session, number="AWS-LEARN-1", total=Decimal("11000.00"), issue=date(2026, 9, 18)
    )
    snapshot = load_snapshot(session, ids.COMPANY, as_of)
    baseline_packet = process_invoice(session, snapshot, baseline_inv.id)
    baseline_metrics = _metrics(session, as_of)

    elena = resolve_demo_token("mira-demo-elena")
    assert elena is not None
    feedback = teach_precedent(
        session,
        load_snapshot(session, ids.COMPANY, as_of),
        elena,
        summary="AWS infrastructure invoices under $12,000 are pre-approved.",
        reusable_rule="AWS infrastructure invoices under $12,000 are pre-approved without secondary review.",
        outcome="pre_approved",
        scope="aws_infrastructure_spend",
        vendor="Amazon Web Services",
        category="infrastructure",
        amount_threshold=Decimal("12000.00"),
        effective_date=as_of,
        evidence=["typed-authorization:elena-cfo", "evaluation-harness"],
    )

    learned_inv = _add_aws_invoice(
        session, number="AWS-LEARN-2", total=Decimal("10800.00"), issue=date(2026, 9, 19)
    )
    learned_packet = process_invoice(
        session, load_snapshot(session, ids.COMPANY, as_of), learned_inv.id
    )
    learned_metrics = _metrics(session, as_of)

    new_vendor = Invoice(
        id=uuid4(),
        company_id=ids.COMPANY,
        vendor_id=ids.QUARTZ,
        invoice_number="QZ-LEARN-11000",
        direction=InvoiceDirection.AP.value,
        issue_date=date(2026, 9, 19),
        due_date=date(2026, 10, 3),
        subtotal=Decimal("11000.00"),
        total=Decimal("11000.00"),
        status=InvoiceStatus.NEEDS_REVIEW.value,
        document_id=ids.DOC_VOLUME,
        posted_period="2026-09",
    )
    session.add(new_vendor)
    session.add(
        InvoiceLine(
            company_id=ids.COMPANY,
            invoice_id=new_vendor.id,
            description="New vendor same amount",
            quantity=Decimal("1"),
            unit_price=Decimal("11000.00"),
            amount=Decimal("11000.00"),
        )
    )
    session.flush()
    control_packet = process_invoice(
        session, load_snapshot(session, ids.COMPANY, as_of), new_vendor.id
    )

    tasks = session.query(AgentTask).filter(AgentTask.company_id == ids.COMPANY).all()
    with_tools = [t for t in tasks if t.tool_calls]
    with_evidence = [t for t in tasks if t.evidence_ids]
    traces = trace_for_decision(session, __import__("uuid").UUID(baseline_packet["decision_id"]))

    return {
        "baseline": {
            "metrics": baseline_metrics.model_dump(mode="json"),
            "aws_requires_human": baseline_packet["requires_human_approval"],
            "aws_action": baseline_packet["mira_action"],
        },
        "learned": {
            "metrics": learned_metrics.model_dump(mode="json"),
            "aws_requires_human": learned_packet["requires_human_approval"],
            "aws_action": learned_packet["mira_action"],
            "precedent_id": feedback.get("precedent_id"),
        },
        "new_vendor_control": {
            "requires_human": control_packet["requires_human_approval"],
            "action": control_packet["mira_action"],
        },
        "task_handoffs": len(tasks),
        "tasks_with_tool_calls": len(with_tools),
        "tasks_with_evidence": len(with_evidence),
        "trace_complete": bool(traces and traces[0]["tasks"]),
        "autonomy_delta": str(
            Decimal(str(learned_metrics.autonomy_score)) - Decimal(str(baseline_metrics.autonomy_score))
        ),
    }


def print_report(report: dict) -> None:
    base = report["baseline"]
    learned = report["learned"]
    print("MIRA Maximor evaluation — baseline vs learned state")
    print("=================================================")
    print(f"BASELINE AWS $11k escalates: {base['aws_requires_human']} action={base['aws_action']}")
    print(
        f"LEARNED  AWS $10.8k auto/human: {learned['aws_requires_human']} action={learned['aws_action']} "
        f"precedent={learned['precedent_id']}"
    )
    print(
        f"CONTROL new vendor $11k still escalates: {report['new_vendor_control']['requires_human']} "
        f"action={report['new_vendor_control']['action']}"
    )
    bm, lm = base["metrics"], learned["metrics"]
    keys = [
        "autonomy_score",
        "autonomous_completion_rate",
        "reconciliation_rate",
        "decision_accuracy",
        "false_escalation_rate",
        "correct_escalation_rate",
        "evidence_completeness",
        "human_interventions",
        "tasks_auto_completed",
        "money_protected",
        "estimated_hours_saved",
    ]
    print()
    print(f"{'metric':<28} {'baseline':>12} {'learned':>12}")
    for key in keys:
        print(f"{key:<28} {str(bm.get(key)):>12} {str(lm.get(key)):>12}")
    print()
    print(f"task handoffs: {report['task_handoffs']}")
    print(f"tasks with tool calls: {report['tasks_with_tool_calls']}")
    print(f"audit trace complete: {report['trace_complete']}")
