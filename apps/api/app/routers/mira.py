"""Executive request API — safe typed work, not an open chat."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db
from mira.agents.close import close_status
from mira.agents.persist import trace_for_decision
from mira.agents.runtime import executive_request, handle_event, overnight_review
from mira.core.enums import OfficeEventType
from mira.core.models import Company, Decision
from mira.finance.snapshot import load_snapshot
from mira.seed.northstar import AS_OF

router = APIRouter(prefix="/api/v1", tags=["mira"])


class ExecutiveRequestIn(BaseModel):
    request: str = Field(min_length=3, max_length=2000)


class EventIn(BaseModel):
    event_type: OfficeEventType
    payload: dict = Field(default_factory=dict)


def _company_snapshot(db: Session):
    company = db.query(Company).filter(Company.slug == "northstar-labs").one()
    return company, load_snapshot(db, company.id, AS_OF.date())


@router.post("/executive/request")
def post_executive_request(body: ExecutiveRequestIn, db: Session = Depends(get_db)) -> dict:
    _company, snapshot = _company_snapshot(db)
    result = executive_request(db, snapshot, body.request)
    db.commit()
    return result


@router.post("/events")
def post_event(body: EventIn, db: Session = Depends(get_db)) -> dict:
    _company, snapshot = _company_snapshot(db)
    result = handle_event(db, snapshot, body.event_type, body.payload)
    db.commit()
    return result


@router.post("/overnight")
def post_overnight(db: Session = Depends(get_db)) -> dict:
    _company, snapshot = _company_snapshot(db)
    result = overnight_review(db, snapshot)
    db.commit()
    return result


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
