from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from mira.core.db import create_schema, get_engine, get_sessionmaker, reset_engine
from mira.core.models import (
    AuditEvent,
    Company,
    Decision,
    Finding,
    Invoice,
    SavingsEvent,
)
from mira.seed.ids import COMPANY, INV_HELIX_B
from mira.seed.northstar import seed_northstar


def test_seed_is_idempotent(tmp_path, monkeypatch) -> None:
    db = tmp_path / "seed.db"
    url = f"sqlite:///{db}"
    monkeypatch.setenv("DATABASE_URL", url)
    reset_engine()
    engine = get_engine(url)
    create_schema(engine)
    Session = get_sessionmaker(url)
    session = Session()
    try:
        first = seed_northstar(session)
        session.commit()
        second = seed_northstar(session)
        session.commit()
        assert first.id == second.id == COMPANY
        count = session.scalar(select(func.count()).select_from(Company))
        assert count == 1
        dup = session.get(Invoice, INV_HELIX_B)
        assert dup is not None
        assert dup.is_duplicate_suspect is True
        finding = session.scalar(
            select(Finding).where(Finding.finding_type == "duplicate_invoice")
        )
        assert finding is not None
        gpu = session.scalar(
            select(Decision).where(Decision.decision_type == "procurement")
        )
        assert gpu is not None
        assert gpu.requires_human_approval is True
        dollars = session.scalar(select(func.sum(SavingsEvent.amount_usd)))
        assert Decimal(str(dollars)) >= Decimal("18400")
        events = session.scalars(select(AuditEvent)).all()
        assert events
    finally:
        session.close()
        reset_engine()
