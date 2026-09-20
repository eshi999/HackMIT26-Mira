from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from mira.agents.runtime import command_center_briefing_data
from mira.core.models import (
    Company,
    Decision,
    Document,
    ExternalSignal,
    Finding,
    Invoice,
    Vendor,
)
from mira.core.schemas import (
    BriefingOut,
    CashPosition,
    CloseBrief,
    CompanyOut,
    DecisionBrief,
    DocumentBrief,
    FindingBrief,
    InvoiceBrief,
    SavingsTotals,
    SignalOut,
)
from mira.finance.snapshot import load_snapshot
from mira.seed.northstar import AS_OF

router = APIRouter(prefix="/api/v1", tags=["company"])


def _require_northstar(db: Session) -> Company:
    company = db.scalar(select(Company).where(Company.slug == "northstar-labs"))
    if not company:
        raise HTTPException(status_code=404, detail="Northstar Labs is not seeded")
    return company


@router.get("/company", response_model=CompanyOut)
def get_company(db: Session = Depends(get_db)) -> Company:
    return _require_northstar(db)


@router.get("/briefing", response_model=BriefingOut)
def get_briefing(db: Session = Depends(get_db)) -> BriefingOut:
    company = _require_northstar(db)
    cid = company.id
    snapshot = load_snapshot(db, cid, AS_OF.date())
    runtime = command_center_briefing_data(db, snapshot)
    db.commit()

    decisions = db.scalars(
        select(Decision).where(Decision.company_id == cid).order_by(Decision.created_at.desc())
    ).all()
    findings = db.scalars(
        select(Finding).where(Finding.company_id == cid).order_by(Finding.severity.desc())
    ).all()
    invoices = db.scalars(select(Invoice).where(Invoice.company_id == cid)).all()
    vendors = {v.id: v.name for v in db.scalars(select(Vendor).where(Vendor.company_id == cid))}
    signals = db.scalars(select(ExternalSignal).where(ExternalSignal.company_id == cid)).all()
    documents = db.scalars(select(Document).where(Document.company_id == cid)).all()

    close = runtime.get("close")
    cash = runtime["cash"]
    return BriefingOut(
        company=CompanyOut.model_validate(company),
        headline=runtime["headline"],
        narrative=runtime["narrative"],
        cash=CashPosition(
            amount=cash.cash.amount,
            account_name="Operating cash",
        ),
        open_ap=cash.open_ap.amount,
        savings=SavingsTotals(
            dollars_protected=Decimal(runtime["dollars_protected"]),
            dollars_saved=Decimal(runtime["dollars_saved"]),
            hours_saved=Decimal(runtime["hours_saved"]),
            period="2026-09",
            source="runtime",
        ),
        pending_decisions=[
            DecisionBrief(
                id=d.id,
                decision_type=d.decision_type,
                status=d.status,
                action=d.action,
                rationale=d.rationale,
                confidence_score=d.confidence_score,
                risk_level=d.risk_level,
                policy_basis=d.policy_basis,
                authority_basis=d.authority_basis,
                requires_human_approval=d.requires_human_approval,
                dollars_impact=d.dollars_impact,
                hours_saved_estimate=d.hours_saved_estimate,
                subject_type=d.subject_type,
            )
            for d in decisions
        ],
        findings=[
            FindingBrief(
                id=f.id,
                finding_type=f.finding_type,
                severity=f.severity,
                title=f.title,
                description=f.description,
                status=f.status,
            )
            for f in findings
        ],
        invoices=[
            InvoiceBrief(
                id=i.id,
                invoice_number=i.invoice_number,
                vendor_name=vendors.get(i.vendor_id) if i.vendor_id else None,
                total=i.total,
                currency=i.currency,
                status=i.status,
                due_date=i.due_date,
                is_duplicate_suspect=i.is_duplicate_suspect,
            )
            for i in invoices
        ],
        signals=[
            SignalOut(
                series_id=s.series_id,
                title=s.title,
                value=s.value,
                unit=s.unit,
                as_of=s.as_of,
                source=s.source,
                note=s.note,
            )
            for s in signals
        ],
        documents_ingested=len(documents),
        inbox=[
            DocumentBrief(
                id=d.id,
                filename=d.filename,
                document_class=d.document_class,
                storage_backend=d.storage_backend,
                storage_uri=d.storage_uri,
            )
            for d in documents
        ],
        autonomous_completion_rate=Decimal(runtime["autonomous_completion_rate"]),
        reconciliation_rate=Decimal(runtime["reconciliation_rate"]),
        open_incidents=int(runtime["open_incidents"]),
        blocked_payments=int(runtime["blocked_payments"]),
        pending_approvals=int(runtime["pending_approvals"]),
        close=CloseBrief.model_validate(close) if close else None,
    )
