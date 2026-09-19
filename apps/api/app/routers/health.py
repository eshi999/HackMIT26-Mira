from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.deps import get_db
from mira import __version__
from mira.core.models import Company
from mira.core.schemas import HealthOut, ReadyOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", version=__version__)


@router.get("/health/ready", response_model=ReadyOut)
def ready(db: Session = Depends(get_db)) -> ReadyOut:
    db.execute(text("SELECT 1"))
    company = db.scalar(select(Company).where(Company.slug == "northstar-labs"))
    count = db.scalar(select(func.count()).select_from(Company)) or 0
    return ReadyOut(
        status="ok",
        version=__version__,
        database="up",
        company=company.name if company else None,
        seeded=count > 0,
    )
