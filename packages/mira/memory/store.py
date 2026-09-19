"""Factual memory, historical memory, and decision precedent.

Three separate concepts. Precedent may change future policy outcomes
but must not bypass unrelated controls.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from mira.core.enums import MemoryStatus, PrecedentStatus
from mira.core.models import FactualMemory, HistoricalMemory, Precedent, Vendor
from mira.finance.snapshot import FinanceSnapshot


def situation_hash(*parts: str) -> str:
    blob = "|".join(parts).encode("utf-8")
    return sha256(blob).hexdigest()


def record_factual(
    session: Session,
    *,
    company_id: UUID,
    statement: str,
    fact_key: str,
    subject_type: str,
    subject_id: UUID | None = None,
    fact_value: dict | None = None,
    source: str = "runtime",
    as_of: date | None = None,
) -> FactualMemory:
    row = FactualMemory(
        id=uuid4(),
        company_id=company_id,
        subject_type=subject_type,
        subject_id=subject_id,
        fact_key=fact_key,
        fact_value=fact_value or {},
        statement=statement,
        source=source,
        as_of=as_of,
        status=MemoryStatus.ACTIVE.value,
    )
    session.add(row)
    session.flush()
    return row


def record_historical(
    session: Session,
    *,
    company_id: UUID,
    statement: str,
    metric_name: str,
    subject_type: str,
    period_start: str,
    period_end: str,
    subject_id: UUID | None = None,
    low: Decimal | None = None,
    high: Decimal | None = None,
    typical: Decimal | None = None,
    unit: str = "usd",
    sample_size: int | None = None,
) -> HistoricalMemory:
    row = HistoricalMemory(
        id=uuid4(),
        company_id=company_id,
        subject_type=subject_type,
        subject_id=subject_id,
        metric_name=metric_name,
        period_start=period_start,
        period_end=period_end,
        low=low,
        high=high,
        typical=typical,
        unit=unit,
        sample_size=sample_size,
        statement=statement,
        status=MemoryStatus.ACTIVE.value,
    )
    session.add(row)
    session.flush()
    return row


def record_precedent(
    session: Session,
    *,
    company_id: UUID,
    summary: str,
    reusable_rule: str,
    outcome: str,
    period: str,
    scope: str,
    authorizer: str,
    conditions: dict | None = None,
    decision_id: UUID | None = None,
    evidence_ids: list[str] | None = None,
    authorized_at: datetime | None = None,
) -> Precedent:
    row = Precedent(
        id=uuid4(),
        company_id=company_id,
        situation_hash=situation_hash(scope, reusable_rule, period),
        decision_id=decision_id,
        summary=summary,
        outcome=outcome,
        period=period,
        reusable_rule=reusable_rule,
        scope=scope,
        conditions=conditions or {},
        authorizer=authorizer,
        authorized_at=authorized_at or datetime.now(UTC),
        evidence_ids=evidence_ids or [],
        status=PrecedentStatus.ACTIVE.value,
    )
    session.add(row)
    session.flush()
    return row


def revoke_precedent(session: Session, precedent_id: UUID) -> Precedent | None:
    row = session.get(Precedent, precedent_id)
    if row is None:
        return None
    row.status = PrecedentStatus.REVOKED.value
    session.flush()
    return row


def bootstrap_from_snapshot(session: Session, snapshot: FinanceSnapshot) -> None:
    """Materialize factual + historical memory from canonical rows. Does not mint precedent."""
    existing_facts = {(row.fact_key, str(row.subject_id)) for row in snapshot.factual_memories}
    existing_hist = {(row.metric_name, str(row.subject_id)) for row in snapshot.historical_memories}

    for vendor in snapshot.vendors:
        key = "vendor.approved_infrastructure" if "aws" in vendor.name.lower() else "vendor.status"
        statement = (
            f"{vendor.name} is an approved infrastructure vendor."
            if vendor.is_preferred and "aws" in vendor.name.lower()
            else f"{vendor.name} is a {vendor.status} vendor (risk_tier={vendor.risk_tier})."
        )
        marker = (key if "aws" in vendor.name.lower() else f"vendor.status.{vendor.id}", str(vendor.id))
        if marker in existing_facts:
            continue
        if "aws" in vendor.name.lower() and vendor.is_preferred:
            record_factual(
                session,
                company_id=snapshot.company_id,
                statement=statement,
                fact_key=key,
                subject_type="vendor",
                subject_id=vendor.id,
                fact_value={"approved": True, "name": vendor.name},
                source="bootstrap",
                as_of=snapshot.as_of,
            )

    by_vendor: dict[UUID, list] = {}
    for invoice in snapshot.ap_invoices():
        if invoice.vendor_id is None:
            continue
        by_vendor.setdefault(invoice.vendor_id, []).append(invoice)
    for vendor_id, invoices in by_vendor.items():
        amounts = [inv.total for inv in invoices]
        if len(amounts) < 2:
            continue
        vendor = snapshot.vendor(vendor_id)
        if vendor is None:
            continue
        marker = ("typical_monthly_spend", str(vendor_id))
        if marker in existing_hist:
            continue
        low = min(amounts)
        high = max(amounts)
        typical = sum(amounts, Decimal("0.00")) / Decimal(len(amounts))
        periods = sorted({f"{inv.issue_date.year:04d}-{inv.issue_date.month:02d}" for inv in invoices})
        record_historical(
            session,
            company_id=snapshot.company_id,
            statement=f"{vendor.name} normally costs {low}–{high}/period across {len(amounts)} invoices.",
            metric_name="typical_monthly_spend",
            subject_type="vendor",
            subject_id=vendor_id,
            period_start=periods[0],
            period_end=periods[-1],
            low=low,
            high=high,
            typical=typical,
            sample_size=len(amounts),
        )


def parse_human_feedback_precedent(message: str) -> dict | None:
    """Deterministic extraction of the AWS $12k pre-approval rule. Not an LLM."""
    text = message.lower()
    if "aws" not in text:
        return None
    if not any(token in text for token in ("pre-approved", "preapproved", "pre approved", "authorized", "without secondary")):
        return None
    if not any(token in text for token in ("12,000", "12000", "12k", "$12")):
        return None
    return {
        "scope": "aws_infrastructure_spend",
        "conditions": {"vendor": "Amazon Web Services", "max_amount": "12000.00", "category": "infrastructure"},
        "reusable_rule": "AWS infrastructure invoices under $12,000 are pre-approved without secondary review.",
        "summary": message.strip(),
        "outcome": "pre_approved",
        "authorizer": "human",
    }


def vendor_is_aws(vendor: Vendor | None, name: str | None = None) -> bool:
    label = (name or (vendor.name if vendor is not None else "") or "").lower()
    return "amazon web services" in label or label.strip() in {"aws", "amazon web services (aws)"}
