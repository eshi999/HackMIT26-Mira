"""Read-only paired context measurements against the current demo snapshot."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_actor, get_db
from app.routers.company import _require_northstar
from mira.agents.auth import CanonicalActor
from mira.context.evaluation import evaluate, evaluate_fresh_seed
from mira.finance.snapshot import load_snapshot
from mira.seed.northstar import AS_OF

router = APIRouter(prefix="/api/v1/context", tags=["context"])


@router.get("/efficiency")
def efficiency(db: Session = Depends(get_db), actor: CanonicalActor = Depends(get_actor)) -> dict:
    company = _require_northstar(db)
    snapshot = load_snapshot(db, company.id, AS_OF.date())
    try:
        report = evaluate(snapshot)
    except (ValueError, AssertionError) as exc:
        raise HTTPException(
            status_code=409, detail="Context equivalence evaluation could not be verified"
        ) from exc
    return {**report, "data_source": "current_demo_snapshot", "read_only": True}


@router.get("/measured")
def measured(db: Session = Depends(get_db), _actor: CanonicalActor = Depends(get_actor)) -> dict:
    _require_northstar(db)
    try:
        return evaluate_fresh_seed()
    except (ValueError, AssertionError) as exc:
        raise HTTPException(
            status_code=409, detail="Context equivalence evaluation could not be verified"
        ) from exc
