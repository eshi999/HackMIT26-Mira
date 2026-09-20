from __future__ import annotations

from collections.abc import Generator

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from mira.agents.auth import CanonicalActor, parse_bearer, resolve_demo_token
from mira.core.db import get_sessionmaker


def get_db() -> Generator[Session, None, None]:
    settings = get_settings()
    SessionLocal = get_sessionmaker(settings.database_url)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_actor(authorization: str | None = Header(default=None)) -> CanonicalActor:
    token = parse_bearer(authorization)
    actor = resolve_demo_token(token)
    if actor is None:
        raise HTTPException(
            status_code=401,
            detail="Demo bearer token required. Use Authorization: Bearer mira-demo-elena",
        )
    return actor
