from __future__ import annotations

import pytest

from mira.core.db import create_schema, get_engine, get_sessionmaker, reset_engine
from mira.seed.northstar import AS_OF, seed_northstar


@pytest.fixture()
def seeded_session(tmp_path, monkeypatch):
    db = tmp_path / "phase2.db"
    url = f"sqlite:///{db}"
    monkeypatch.setenv("DATABASE_URL", url)
    reset_engine()
    engine = get_engine(url)
    create_schema(engine)
    Session = get_sessionmaker(url)
    session = Session()
    seed_northstar(session)
    session.commit()
    yield session
    session.close()
    reset_engine()


@pytest.fixture()
def as_of():
    return AS_OF.date()
