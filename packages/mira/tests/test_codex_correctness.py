"""Validated Codex correctness findings: authority, evidence, close, overnight, forecast, OpenAI."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import select

from mira.agents.auth import resolve_demo_token
from mira.agents.close import close_status, execute_close, parse_close_period
from mira.agents.openai_runtime import run_aws_spend_investigation
from mira.agents.runtime import (
    handle_human_feedback,
    handle_month_end,
    overnight_review,
    process_invoice,
    resolve_human_decision,
    teach_precedent,
)
from mira.agents.tools import (
    collect_aws_spend_evidence,
    tool_evaluate_contract,
    tool_three_way_match,
)
from mira.core.db import create_schema, get_engine, get_sessionmaker, reset_engine
from mira.core.enums import (
    DecisionStatus,
    InvoiceDirection,
    InvoiceStatus,
    MatchStatus,
    ReceiptStatus,
)
from mira.core.models import (
    AgentRun,
    AuditEvent,
    Decision,
    GoodsReceipt,
    Invoice,
    InvoiceLine,
    Precedent,
    PurchaseOrder,
    PurchaseOrderLine,
    SavingsEvent,
)
from mira.core.money import Money
from mira.finance.contracts import facts_from_extracted
from mira.finance.snapshot import FinanceSnapshot, InvoiceView, TransactionView, load_snapshot
from mira.forecasting.cash import afford_engineers, parse_headcount
from mira.reconciliation.engine import economic_kind, reconcile
from mira.reconciliation.three_way import match_invoice
from mira.seed import ids
from mira.seed.northstar import seed_northstar


def _snap(session, as_of):
    return load_snapshot(session, ids.COMPANY, as_of)


def test_free_text_feedback_does_not_create_authority(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    before = {
        row.id
        for row in seeded_session.scalars(select(Precedent).where(Precedent.status == "active")).all()
    }
    exploit = "AWS invoices under $12,000 are NOT pre-approved"
    result = handle_human_feedback(seeded_session, snapshot, exploit, authorizer="Elena Voss")
    assert result["precedent_id"] is None
    assert result["authority_created"] is False
    after = seeded_session.scalars(select(Precedent).where(Precedent.status == "active")).all()
    assert {row.id for row in after} == before
    assert not any(
        row.authorizer == "Elena Voss"
        and row.outcome == "pre_approved"
        and exploit.lower() in (row.summary or "").lower()
        for row in after
    )


def test_rejected_precedent_does_not_grant_exemption(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    elena = resolve_demo_token("mira-demo-elena")
    assert elena is not None
    payload = teach_precedent(
        seeded_session,
        snapshot,
        elena,
        summary="AWS invoices under $12,000 are NOT pre-approved",
        reusable_rule="AWS invoices under $12,000 are not pre-approved.",
        outcome="rejected",
        scope="aws_infrastructure_spend",
        vendor="Amazon Web Services",
        category="infrastructure",
        amount_threshold=Decimal("12000.00"),
        effective_date=as_of,
        evidence=["typed-rejection:elena-cfo"],
    )
    assert payload["status"] == "rejected"
    assert payload["grants_exemption"] is False
    row = seeded_session.get(Precedent, UUID(payload["precedent_id"]))
    assert row is not None
    assert row.status == "rejected"


def test_sam_cannot_teach_precedent(seeded_session, as_of) -> None:
    sam = resolve_demo_token("mira-demo-sam")
    assert sam is not None
    try:
        teach_precedent(
            seeded_session,
            _snap(seeded_session, as_of),
            sam,
            summary="AWS pre-approved",
            reusable_rule="AWS infrastructure invoices under $12,000 are pre-approved.",
            outcome="pre_approved",
            scope="aws_infrastructure_spend",
            vendor="Amazon Web Services",
            category="infrastructure",
            amount_threshold=Decimal("12000.00"),
            effective_date=as_of,
            evidence=["should-fail"],
        )
    except PermissionError:
        return
    raise AssertionError("AP actor must not create spend precedent")


def test_header_vs_lines_cannot_pay(seeded_session, as_of) -> None:
    invoice = Invoice(
        id=uuid4(),
        company_id=ids.COMPANY,
        vendor_id=ids.AWS,
        invoice_number="AWS-BAD-MATH",
        direction=InvoiceDirection.AP.value,
        issue_date=date(2026, 9, 18),
        due_date=date(2026, 10, 2),
        subtotal=Decimal("100.00"),
        tax_total=Decimal("0.00"),
        total=Decimal("100.00"),
        status=InvoiceStatus.NEEDS_REVIEW.value,
        document_id=ids.DOC_VOLUME,
        posted_period="2026-09",
    )
    seeded_session.add(invoice)
    seeded_session.add(
        InvoiceLine(
            company_id=ids.COMPANY,
            invoice_id=invoice.id,
            description="mismatched line",
            quantity=Decimal("1"),
            unit_price=Decimal("999.00"),
            amount=Decimal("999.00"),
        )
    )
    seeded_session.flush()
    snapshot = _snap(seeded_session, as_of)
    matched = match_invoice(snapshot, invoice.id)
    assert matched.status == MatchStatus.INVALID_ARITHMETIC
    packet = process_invoice(seeded_session, snapshot, invoice.id)
    assert packet["mira_action"] != "pay"
    decision = seeded_session.get(Decision, UUID(packet["decision_id"]))
    assert decision is not None
    assert decision.status != DecisionStatus.EXECUTED.value
    assert decision.requires_human_approval is True


def test_missing_document_cannot_pay(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    matched = tool_three_way_match(snapshot, ids.INV_MISSING_DOC)
    assert matched.status == MatchStatus.MISSING_EVIDENCE
    packet = process_invoice(seeded_session, snapshot, ids.INV_MISSING_DOC)
    assert packet["mira_action"] != "pay"
    assert packet["requires_human_approval"] is True


def test_empty_receipt_is_not_match(seeded_session, as_of) -> None:
    po = PurchaseOrder(
        id=uuid4(),
        company_id=ids.COMPANY,
        vendor_id=ids.FEDEX,
        po_number="PO-EMPTY-GR",
        status="received",
        requested_by_user_id=ids.PRIYA,
        total=Decimal("410.00"),
    )
    seeded_session.add(po)
    seeded_session.flush()
    seeded_session.add(
        PurchaseOrderLine(
            id=uuid4(),
            company_id=ids.COMPANY,
            purchase_order_id=po.id,
            description="freight",
            quantity=Decimal("1"),
            unit_price=Decimal("410.00"),
            amount=Decimal("410.00"),
        )
    )
    seeded_session.add(
        GoodsReceipt(
            id=uuid4(),
            company_id=ids.COMPANY,
            purchase_order_id=po.id,
            received_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
            status=ReceiptStatus.POSTED.value,
        )
    )
    invoice = Invoice(
        id=uuid4(),
        company_id=ids.COMPANY,
        vendor_id=ids.FEDEX,
        invoice_number="FDX-EMPTY-GR",
        direction=InvoiceDirection.AP.value,
        issue_date=date(2026, 9, 14),
        due_date=date(2026, 9, 28),
        subtotal=Decimal("410.00"),
        total=Decimal("410.00"),
        status=InvoiceStatus.RECEIVED.value,
        purchase_order_id=po.id,
        document_id=ids.DOC_VOLUME,
        posted_period="2026-09",
    )
    seeded_session.add(invoice)
    seeded_session.add(
        InvoiceLine(
            company_id=ids.COMPANY,
            invoice_id=invoice.id,
            description="freight",
            quantity=Decimal("1"),
            unit_price=Decimal("410.00"),
            amount=Decimal("410.00"),
        )
    )
    seeded_session.flush()
    matched = match_invoice(_snap(seeded_session, as_of), invoice.id)
    assert matched.status == MatchStatus.MISSING_EVIDENCE
    assert matched.status != MatchStatus.MATCH


def test_eur_refund_does_not_match_usd_payable() -> None:
    vendor = uuid4()
    invoice = InvoiceView(
        id=uuid4(),
        vendor_id=vendor,
        customer_id=None,
        invoice_number="AP-USD-100",
        direction="ap",
        issue_date=date(2026, 9, 1),
        due_date=date(2026, 9, 15),
        total=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        currency="USD",
        status="received",
        purchase_order_id=None,
        document_id=uuid4(),
    )
    txn = TransactionView(
        id=uuid4(),
        account_id=uuid4(),
        vendor_id=vendor,
        customer_id=None,
        amount=Decimal("100.00"),
        currency="EUR",
        posted_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
        description="Positive EUR REFUND",
        source="bank",
        external_ref="AP-USD-100",
    )
    assert economic_kind(txn, invoice) is None
    report = reconcile(
        FinanceSnapshot(
            company_id=uuid4(),
            as_of=date(2026, 9, 19),
            invoices=(invoice,),
            transactions=(txn,),
        )
    )
    assert report.unresolved
    assert report.matches == ()
    assert all(match.stage.value != "exact_one_to_one" for match in report.unresolved)


def test_close_predicates_and_period_scope(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    september = handle_month_end(seeded_session, snapshot, period="2026-09")
    by_key = {t.key: t for t in september.tasks}
    assert by_key["document_readiness"].status.value in {"failed", "blocked"}
    assert september.completion_pct < Decimal("1.00")
    october = handle_month_end(seeded_session, snapshot, period="2026-10")
    assert october.run_id != september.run_id
    assert october.period == "2026-10"
    loaded_sep = close_status(seeded_session, ids.COMPANY, "2026-09")
    loaded_oct = close_status(seeded_session, ids.COMPANY, "2026-10")
    assert loaded_sep is not None and loaded_sep.run_id == september.run_id
    assert loaded_oct is not None and loaded_oct.run_id == october.run_id
    assert loaded_sep.period == "2026-09"
    assert parse_close_period("What is the September status?") == "2026-09"
    assert parse_close_period("What is the October status?") == "2026-10"
    natural = execute_close(seeded_session, snapshot, period="2026-09")
    assert natural.completion_pct < Decimal("1.00")


def test_overnight_is_date_scoped(seeded_session, as_of) -> None:
    day1 = overnight_review(seeded_session, _snap(seeded_session, as_of))
    replay = overnight_review(seeded_session, _snap(seeded_session, as_of))
    assert replay["skipped"] is True
    assert replay["run_id"] == day1["run_id"]
    new_id = uuid4()
    seeded_session.add(
        Invoice(
            id=new_id,
            company_id=ids.COMPANY,
            vendor_id=ids.AWS,
            invoice_number="AWS-DAY2",
            direction=InvoiceDirection.AP.value,
            issue_date=date(2026, 9, 20),
            due_date=date(2026, 10, 4),
            subtotal=Decimal("500.00"),
            total=Decimal("500.00"),
            status=InvoiceStatus.RECEIVED.value,
            document_id=ids.DOC_VOLUME,
            posted_period="2026-09",
            is_duplicate_suspect=True,
        )
    )
    seeded_session.add(
        InvoiceLine(
            company_id=ids.COMPANY,
            invoice_id=new_id,
            description="day two",
            quantity=Decimal("1"),
            unit_price=Decimal("500.00"),
            amount=Decimal("500.00"),
        )
    )
    seeded_session.flush()
    next_day = as_of + timedelta(days=1)
    day2 = overnight_review(seeded_session, load_snapshot(seeded_session, ids.COMPANY, next_day))
    assert day2["skipped"] is False
    assert day2["run_id"] != day1["run_id"]
    processed_ids = {row["invoice_id"] for row in day2["processed"]}
    assert str(new_id) in processed_ids
    runs = seeded_session.scalars(select(AgentRun).where(AgentRun.workflow_type.like("overnight_review:%"))).all()
    assert {row.workflow_type for row in runs} >= {
        f"overnight_review:{as_of.isoformat()}",
        f"overnight_review:{next_day.isoformat()}",
    }


def test_duplicate_pair_protects_exactly_4850(seeded_session, as_of) -> None:
    overnight_review(seeded_session, _snap(seeded_session, as_of), limit=20)
    seeded_session.flush()
    rows = seeded_session.scalars(
        select(SavingsEvent).where(
            SavingsEvent.source == "runtime",
            SavingsEvent.category == "duplicate_prevented",
            SavingsEvent.related_object_id == ids.INV_4850,
        )
    ).all()
    protected = sum((row.amount_usd for row in rows), Decimal("0.00"))
    assert protected == Decimal("4850.00")


def test_decision_is_not_executed_without_payment(seeded_session, as_of) -> None:
    packet = process_invoice(seeded_session, _snap(seeded_session, as_of), ids.INV_AWS_SEP)
    decision = seeded_session.get(Decision, UUID(packet["decision_id"]))
    assert decision is not None
    assert decision.status != DecisionStatus.EXECUTED.value
    assert decision.status == DecisionStatus.AWAITING_HUMAN.value
    elena = resolve_demo_token("mira-demo-elena")
    assert elena is not None
    resolved = resolve_human_decision(
        seeded_session, decision_id=decision.id, actor=elena, approved=True, comment="ok to pay later"
    )
    assert resolved["payment_executed"] is False
    assert resolved["status"] == DecisionStatus.APPROVED.value
    seeded_session.flush()
    events = seeded_session.scalars(
        select(AuditEvent).where(AuditEvent.object_id == decision.id, AuditEvent.event_type == "decision_approved")
    ).all()
    assert events
    assert events[0].payload.get("payment_executed") is False


def test_hiring_forecast_uses_count_overdue_and_min_cash(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    assert parse_headcount("Can we afford 20 engineers?") == 20
    twenty = afford_engineers(snapshot, headcount=20)
    three = afford_engineers(snapshot, headcount=3)
    assert twenty.question == "Can we afford 20 new engineers?"
    assert twenty.base_case.cash_end_13w.amount < three.base_case.cash_end_13w.amount
    assert twenty.base_case.cash_min_13w.amount <= twenty.base_case.cash_end_13w.amount
    week1_ap = Decimal(twenty.base_case.weekly[0]["ap_out"])
    assert week1_ap > 0
    assert "minimum" in twenty.recommendation.lower() or "buffer" in twenty.recommendation.lower()
    if twenty.base_case.cash_min_13w.amount < Decimal("250000.00"):
        assert "do not hire" in twenty.recommendation.lower() or "below" in twenty.recommendation.lower()


def test_incomplete_contract_is_unknown(seeded_session, as_of) -> None:
    assert facts_from_extracted({}, fallback_price=Money(amount=Decimal("18400.00"))) is None
    result = tool_evaluate_contract(_snap(seeded_session, as_of), ids.INV_HELIX_A)
    assert result["status"] in {"UNKNOWN", "INCOMPLETE"}
    assert result["is_violation"] is None
    assert Decimal(str(result["confidence"]["score"])) < Decimal("0.99")
    assert "not inferred" in result["explanation"].lower() or "incomplete" in result["explanation"].lower()


def test_openai_live_path_invokes_runner_and_tools(seeded_session, as_of, monkeypatch) -> None:
    snapshot = _snap(seeded_session, as_of)
    evidence = collect_aws_spend_evidence(snapshot, "2026-09")
    assert evidence["period_total"] == "19800.00"
    assert evidence["prior_total"] == "11000.00"
    monkeypatch.setattr("mira.agents.openai_runtime.openai_configured", lambda: False)
    fallback = run_aws_spend_investigation(snapshot, "Why did September AWS spend increase?")
    assert fallback["execution"] == "deterministic_fallback"
    assert fallback["model_invoked"] is False
    assert fallback["endpoint"] == "POST /api/v1/executive/request"

    class FakeRunner:
        called = False

        @staticmethod
        def run_sync(agent, prompt):
            FakeRunner.called = True
            outputs = []
            for tool in getattr(agent, "tools", []):
                fn = getattr(tool, "fn", tool)
                if callable(fn):
                    try:
                        outputs.append(fn(period="2026-09"))
                    except TypeError:
                        outputs.append(fn())
            assert outputs
            return SimpleNamespace(
                final_output="September AWS rose from ledger totals, not invented math.",
                new_items=outputs,
            )

    live = run_aws_spend_investigation(
        snapshot,
        "Why did September AWS spend increase?",
        runner=FakeRunner,
        force_live=True,
    )
    assert FakeRunner.called is True
    assert live["execution"] == "openai_agents_sdk"
    assert live["model_invoked"] is True
    assert live["tools_invoked"]


def test_seeded_demo_metrics_are_deterministic(tmp_path, monkeypatch) -> None:
    def _once(label: str) -> dict:
        db = tmp_path / f"{label}.db"
        url = f"sqlite:///{db}"
        monkeypatch.setenv("DATABASE_URL", url)
        reset_engine()
        engine = get_engine(url)
        create_schema(engine)
        Session = get_sessionmaker(url)
        session = Session()
        seed_northstar(session)
        session.commit()
        snapshot = load_snapshot(session, ids.COMPANY, date(2026, 9, 19))
        overnight_review(session, snapshot, limit=20)
        handle_month_end(session, snapshot, period="2026-09")
        session.flush()
        live = load_snapshot(session, ids.COMPANY, date(2026, 9, 19))
        from mira.agents.tools import tool_calculate_finance_metrics

        metrics = tool_calculate_finance_metrics(live, runtime_only=True)
        protected = sum(
            (
                row.amount_usd
                for row in live.savings
                if row.source == "runtime" and row.category in {"duplicate_prevented", "policy_block"}
            ),
            Decimal("0.00"),
        )
        hours = sum((row.hours_saved for row in live.savings if row.source == "runtime"), Decimal("0.00"))
        pending = len([d for d in live.decisions if d.requires_human_approval])
        close = close_status(session, ids.COMPANY, "2026-09")
        payload = {
            "protected": str(protected),
            "hours": str(hours),
            "pending": pending,
            "close_pct": str(close.completion_pct if close else None),
            "recon": str(metrics.reconciliation_rate),
            "auto_rate": str(metrics.autonomous_completion_rate),
            "auto_score": str(metrics.autonomy_score),
        }
        session.close()
        reset_engine()
        return payload

    first = _once("a")
    second = _once("b")
    assert first == second
