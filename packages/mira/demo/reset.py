"""Deterministic Northstar demo reset."""

from __future__ import annotations

import os
from pathlib import Path

from mira.agents.runtime import handle_month_end, overnight_review
from mira.agents.tools import tool_calculate_finance_metrics
from mira.core.db import create_schema, get_engine, reset_engine
from mira.core.models import Base
from mira.finance.snapshot import load_snapshot
from mira.seed.northstar import AS_OF, seed_from_url


def _sqlite_path(url: str) -> Path | None:
    if not url.startswith("sqlite:///"):
        return None
    raw = url.removeprefix("sqlite:///")
    if raw in {":memory:", ""}:
        return None
    return Path(raw)


def reset_demo(database_url: str | None = None) -> dict:
    url = database_url or os.environ.get("DATABASE_URL", "sqlite:///./data/mira.db")
    Path("data").mkdir(exist_ok=True)
    reset_engine()
    sqlite_path = _sqlite_path(url)
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        if sqlite_path.exists():
            sqlite_path.unlink()
        eval_db = Path("data/mira-eval.db")
        if eval_db.exists():
            eval_db.unlink()
    else:
        engine = get_engine(url)
        Base.metadata.drop_all(bind=engine)
        reset_engine()

    engine = get_engine(url)
    create_schema(engine)
    seed_from_url(url)

    from sqlalchemy.orm import Session

    from mira.core.models import Company

    with Session(engine) as session:
        company = session.query(Company).filter(Company.slug == "northstar-labs").one()
        snapshot = load_snapshot(session, company.id, AS_OF.date())
        overnight = overnight_review(session, snapshot, limit=20)
        close = handle_month_end(session, snapshot, period="2026-09")
        session.commit()
        live = load_snapshot(session, company.id, AS_OF.date())
        metrics = tool_calculate_finance_metrics(live, runtime_only=True)

    return {
        "database_url_scheme": url.split(":", 1)[0],
        "company": "Northstar Labs",
        "overnight_skipped": bool(overnight.get("skipped")),
        "close_pct": str(close.completion_pct),
        "dollars_protected": str(metrics.money_protected),
        "hours_saved": str(metrics.estimated_hours_saved),
        "status": "ready",
    }


def print_reset() -> int:
    report = reset_demo()
    print("Mira demo reset")
    print("===============")
    for key, value in report.items():
        print(f"{key:<22} {value}")
    return 0
