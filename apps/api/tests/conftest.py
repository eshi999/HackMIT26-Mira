from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mira.core.db import reset_engine


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "mira.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("MIRA_BOOTSTRAP", "true")
    reset_engine()
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    reset_engine()
