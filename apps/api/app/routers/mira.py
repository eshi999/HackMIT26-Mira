"""Executive request API — safe typed work, not an open chat."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_actor, get_db
from mira.agents.auth import CanonicalActor
from mira.agents.close import close_status
from mira.agents.persist import trace_for_decision
from mira.agents.runtime import (
    executive_request,
    handle_event,
    overnight_review,
    resolve_human_decision,
    teach_precedent,
)
from mira.core.enums import OfficeEventType
from mira.core.models import Company, Decision, Precedent
from mira.finance.snapshot import load_snapshot
from mira.seed.northstar import AS_OF

router = APIRouter(prefix="/api/v1", tags=["mira"])


class ExecutiveRequestIn(BaseModel):
    request: str = Field(min_length=3, max_length=2000)


class EventIn(BaseModel):
    event_type: OfficeEventType
    payload: dict = Field(default_factory=dict)


class PrecedentIn(BaseModel):
    summary: str
    reusable_rule: str
    outcome: str
    scope: str
    vendor: str | None = None
    category: str | None = None
    amount_threshold: Decimal
    effective_date: date
    evidence: list[str] = Field(min_length=1)


class ResolveIn(BaseModel):
    resolution: str = Field(pattern="^(approve|reject)$")
    comment: str | None = None


def _company_snapshot(db: Session):
    company = db.query(Company).filter(Company.slug == "northstar-labs").one()
    return company, load_snapshot(db, company.id, AS_OF.date())


@router.post("/executive/request")
def post_executive_request(
    body: ExecutiveRequestIn,
    db: Session = Depends(get_db),
    _actor: CanonicalActor = Depends(get_actor),
) -> dict:
    _company, snapshot = _company_snapshot(db)
    result = executive_request(db, snapshot, body.request)
    db.commit()
    return result


@router.post("/executive/investigate")
def post_executive_investigate(
    body: ExecutiveRequestIn,
    db: Session = Depends(get_db),
    _actor: CanonicalActor = Depends(get_actor),
) -> dict:
    """Compatibility alias for Mira's deterministic executive runtime."""
    _company, snapshot = _company_snapshot(db)
    result = executive_request(db, snapshot, body.request)
    db.commit()
    return result


@router.post("/events")
def post_event(
    body: EventIn,
    db: Session = Depends(get_db),
    _actor: CanonicalActor = Depends(get_actor),
) -> dict:
    _company, snapshot = _company_snapshot(db)
    result = handle_event(db, snapshot, body.event_type, body.payload)
    db.commit()
    return result


@router.post("/overnight")
def post_overnight(
    db: Session = Depends(get_db),
    _actor: CanonicalActor = Depends(get_actor),
) -> dict:
    _company, snapshot = _company_snapshot(db)
    result = overnight_review(db, snapshot)
    db.commit()
    return result


@router.post("/precedents/authorize")
def post_authorize_precedent(
    body: PrecedentIn,
    db: Session = Depends(get_db),
    actor: CanonicalActor = Depends(get_actor),
) -> dict:
    _company, snapshot = _company_snapshot(db)
    try:
        result = teach_precedent(
            db,
            snapshot,
            actor,
            summary=body.summary,
            reusable_rule=body.reusable_rule,
            outcome=body.outcome,
            scope=body.scope,
            vendor=body.vendor,
            category=body.category,
            amount_threshold=body.amount_threshold,
            effective_date=body.effective_date,
            evidence=body.evidence,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return result


@router.post("/decisions/{decision_id}/resolve")
def post_resolve_decision(
    decision_id: str,
    body: ResolveIn,
    db: Session = Depends(get_db),
    actor: CanonicalActor = Depends(get_actor),
) -> dict:
    from uuid import UUID

    try:
        result = resolve_human_decision(
            db,
            decision_id=UUID(decision_id),
            actor=actor,
            approved=body.resolution == "approve",
            comment=body.comment,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("/precedents")
def list_precedents(db: Session = Depends(get_db)) -> dict:
    company, _snapshot = _company_snapshot(db)
    rows = (
        db.query(Precedent)
        .filter(Precedent.company_id == company.id)
        .order_by(Precedent.created_at.desc())
        .all()
    )
    return {
        "precedents": [
            {
                "id": str(row.id),
                "summary": row.summary,
                "outcome": row.outcome,
                "scope": row.scope,
                "status": row.status,
                "authorizer": row.authorizer,
                "reusable_rule": row.reusable_rule,
                "conditions": row.conditions,
                "period": row.period,
            }
            for row in rows
        ]
    }


@router.get("/office/runs")
def office_runs(db: Session = Depends(get_db)) -> dict:
    company, snapshot = _company_snapshot(db)
    close = close_status(db, company.id)
    return {
        "company_id": str(company.id),
        "as_of": snapshot.as_of.isoformat(),
        "close": close.model_dump(mode="json") if close else None,
        "org_note": "Specialists are roles. Only Mira speaks to the user.",
    }


@router.get("/decisions/{decision_id}/trace")
def decision_trace(decision_id: str, db: Session = Depends(get_db)) -> dict:
    from uuid import UUID

    rows = trace_for_decision(db, UUID(decision_id))
    decision = db.get(Decision, UUID(decision_id))
    return {"decision": str(decision.id) if decision else None, "trace": rows}
