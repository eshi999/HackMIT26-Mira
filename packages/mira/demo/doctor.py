"""Report demo readiness without exposing secrets."""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from mira.core.db import get_engine, reset_engine
from mira.core.models import Company
from mira.demo.status import (
    deepgram_row,
    dropbox_row,
    elastic_row,
    elevenlabs_row,
    grok_row,
)

OPTIONAL = ("dropbox", "elastic", "deepgram", "elevenlabs", "grok")


def _db_row() -> dict[str, Any]:
    url = os.environ.get("DATABASE_URL", "sqlite:///./data/mira.db")
    scheme = url.split(":", 1)[0]
    try:
        reset_engine()
        engine = get_engine(url)
        with Session(engine) as session:
            session.execute(text("SELECT 1"))
            company = session.scalar(select(Company).where(Company.slug == "northstar-labs"))
            count = session.scalar(select(func.count()).select_from(Company)) or 0
        if company and count:
            return {
                "name": "db",
                "configured": True,
                "status": "live",
                "note": f"{scheme} seeded ({company.name})",
            }
        return {
            "name": "db",
            "configured": True,
            "status": "unavailable",
            "note": f"{scheme} reachable but Northstar is not seeded",
        }
    except Exception:
        return {
            "name": "db",
            "configured": bool(url),
            "status": "unavailable",
            "note": f"{scheme} unreachable or not created",
        }
    finally:
        reset_engine()


def collect_report() -> dict[str, Any]:
    checks = [
        _db_row(),
        dropbox_row(),
        elastic_row(),
        deepgram_row(),
        elevenlabs_row(),
        grok_row(),
    ]
    by_name = {row["name"]: row for row in checks}
    live = [name for name in OPTIONAL if by_name[name]["status"] == "live"]
    core_ok = by_name["db"]["status"] == "live"
    return {
        "ready": core_ok,
        "core_ok": core_ok,
        "live_integrations": live,
        "checks": checks,
    }


def print_doctor() -> int:
    report = collect_report()
    print("Mira demo doctor")
    print("================")
    print(f"{'integration':<14} {'status':<12} {'configured':<12} note")
    for row in report["checks"]:
        configured = "yes" if row["configured"] else "no"
        print(f"{row['name']:<14} {row['status']:<12} {configured:<12} {row['note']}")
    print()
    live = ", ".join(report["live_integrations"]) or "none"
    print(f"Core demo ready: {'yes' if report['ready'] else 'no'}")
    print(f"Live integrations: {live}")
    print("Optional keys are reported as configured yes/no only. Values are never printed.")
    return 0 if report["ready"] else 1
