from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from mira.core.models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def sqlite_connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def get_engine(database_url: str) -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            database_url,
            future=True,
            connect_args=sqlite_connect_args(database_url),
        )
        if database_url.startswith("sqlite"):

            @event.listens_for(_engine, "connect")
            def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    return _engine


def get_sessionmaker(database_url: str) -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(database_url),
            autoflush=False,
            autocommit=False,
            future=True,
        )
    return _SessionLocal


def reset_engine() -> None:
    """Test helper."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)


def session_scope(database_url: str) -> Generator[Session, None, None]:
    SessionLocal = get_sessionmaker(database_url)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
