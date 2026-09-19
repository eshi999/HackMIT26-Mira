from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.config import get_settings
from mira.core.db import get_sessionmaker


def get_db() -> Generator[Session, None, None]:
    settings = get_settings()
    SessionLocal = get_sessionmaker(settings.database_url)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
