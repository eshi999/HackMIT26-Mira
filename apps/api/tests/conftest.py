from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mira.core.db import reset_engine


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "mira.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("MIRA_BOOTSTRAP", "true")
    monkeypatch.setenv("MIRA_SPACE_OFFLINE", "1")
    for key in (
        "OPENAI_API_KEY",
        "DEEPGRAM_API_KEY",
        "ELEVENLABS_API_KEY",
        "DROPBOX_ACCESS_TOKEN",
        "ELASTICSEARCH_URL",
        "ELASTICSEARCH_API_KEY",
        "XAI_API_KEY",
        "GROK_API_KEY",
    ):
        monkeypatch.setenv(key, "")
    reset_engine()
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    reset_engine()
