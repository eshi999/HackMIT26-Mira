from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_db
from mira.core.models import (
    Company,
    Decision,
    Document,
    ExternalSignal,
    Finding,
    Invoice,
    Metric,
    SavingsEvent,
    Vendor,
)
from mira.core.schemas import (
    BriefingOut,
    CashPosition,
    CompanyOut,
    DecisionBrief,
    DocumentBrief,
    FindingBrief,
    InvoiceBrief,
    SavingsTotals,
    SignalOut,
)

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

    cash_row = db.scalar(
        select(Metric).where(Metric.company_id == cid, Metric.name == "cash")
    )
    ap_row = db.scalar(
        select(Metric).where(Metric.company_id == cid, Metric.name == "open_ap")
    )
    dollars = db.scalar(
        select(func.coalesce(func.sum(SavingsEvent.amount_usd), 0)).where(
            SavingsEvent.company_id == cid
        )
    )
    hours = db.scalar(
        select(func.coalesce(func.sum(SavingsEvent.hours_saved), 0)).where(
            SavingsEvent.company_id == cid
        )
    )

    decisions = db.scalars(
        select(Decision)
        .where(Decision.company_id == cid)
        .order_by(Decision.created_at.desc())
    ).all()
    findings = db.scalars(
        select(Finding).where(Finding.company_id == cid).order_by(Finding.severity.desc())
    ).all()
    invoices = db.scalars(select(Invoice).where(Invoice.company_id == cid)).all()
    vendors = {v.id: v.name for v in db.scalars(select(Vendor).where(Vendor.company_id == cid))}
    signals = db.scalars(select(ExternalSignal).where(ExternalSignal.company_id == cid)).all()
    documents = db.scalars(select(Document).where(Document.company_id == cid)).all()

    pending = [d for d in decisions if d.requires_human_approval]
    headline = (
        "I blocked a duplicate HelixCloud bill and I need you on a GPU purchase."
        if pending
        else "Northstar is quiet. I will keep watching AP and cash."
    )
    narrative = (
        "Elena, I closed the Dropbox-shaped inbox overnight. "
        "Eleven documents are classified. HelixCloud 10441-A is a duplicate of 10441 — "
        "I blocked $18,400 under spend policy v3 clause 6. Apex Scientific is 38 days overdue. "
        "The $67,000 eval-cluster GPU request clears budget but not authority; dual approval "
        "is waiting. Any Visa path from here is SANDBOX / simulated, not a live transfer."
    )

    return BriefingOut(
        company=CompanyOut.model_validate(company),
        headline=headline,
        narrative=narrative,
        cash=CashPosition(
            amount=Decimal(cash_row.value) if cash_row else Decimal("0"),
            account_name="Operating cash",
        ),
        open_ap=Decimal(ap_row.value) if ap_row else Decimal("0"),
        savings=SavingsTotals(
            dollars_protected=Decimal(dollars or 0),
            hours_saved=Decimal(hours or 0),
            period="2026-09",
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
    )
