"""Optional live-key OpenAI smoke. OpenAI is never required."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mira.agents.openai_runtime import (
    HAS_OPENAI_AGENTS,
    openai_configured,
    run_aws_spend_investigation,
)
from mira.core.db import reset_engine
from mira.core.models import Base
from mira.demo.status import key_configured
from mira.finance.snapshot import load_snapshot
from mira.seed.northstar import AS_OF, seed_northstar


def openai_smoke() -> dict:
    if not key_configured("OPENAI_API_KEY"):
        return {
            "status": "skipped",
            "required": False,
            "configured": False,
            "note": "OPENAI_API_KEY is not set. Bounded runtime still uses the deterministic fallback.",
        }
    if not HAS_OPENAI_AGENTS:
        return {
            "status": "unavailable",
            "required": False,
            "configured": True,
            "note": "openai-agents package is not installed.",
        }
    reset_engine()
    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            company = seed_northstar(session)
            session.flush()
            snapshot = load_snapshot(session, company.id, AS_OF.date())
            result = run_aws_spend_investigation(
                snapshot,
                "Why did September AWS spend increase?",
                force_live=openai_configured(),
            )
        return {
            "status": result.get("execution"),
            "required": False,
            "configured": True,
            "model_invoked": bool(result.get("model_invoked")),
            "tools_invoked": result.get("tools_invoked"),
            "headline": result.get("headline"),
            "provider_error": result.get("provider_error"),
            "sdk_available": HAS_OPENAI_AGENTS,
        }
    finally:
        engine.dispose()
        reset_engine()


def print_openai_smoke() -> int:
    report = openai_smoke()
    print("Mira OpenAI smoke")
    print("=================")
    for key in (
        "status",
        "required",
        "configured",
        "model_invoked",
        "sdk_available",
        "headline",
        "provider_error",
        "note",
    ):
        if key in report and report[key] is not None:
            print(f"{key:<16} {report[key]}")
    tools = report.get("tools_invoked")
    if tools:
        print(f"{'tools_invoked':<16} {', '.join(str(t) for t in tools)}")
    return 0
