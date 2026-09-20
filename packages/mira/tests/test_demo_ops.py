from __future__ import annotations

from mira.demo.doctor import collect_report
from mira.demo.openai_smoke import openai_smoke
from mira.demo.status import integration_row, key_configured
from mira.integrations.base import AdapterStatus


def test_key_configured_does_not_return_values(monkeypatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "super-secret")
    assert key_configured("DEEPGRAM_API_KEY") is True
    monkeypatch.setenv("DEEPGRAM_API_KEY", "")
    assert key_configured("DEEPGRAM_API_KEY") is False
    row = integration_row("deepgram", False, "demo", "key not configured")
    assert "super-secret" not in str(row)


def test_openai_smoke_skips_without_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    report = openai_smoke()
    assert report["status"] == "skipped"
    assert report["required"] is False
    assert report["configured"] is False


def test_doctor_report_has_no_secret_values(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/missing.db")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "secret-dg-value")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DROPBOX_ACCESS_TOKEN", "")
    monkeypatch.setenv("ELASTICSEARCH_URL", "")
    monkeypatch.setenv("XAI_API_KEY", "")
    monkeypatch.setattr(
        "mira.demo.status.DeepgramAdapter.health_check",
        lambda self: AdapterStatus.UNAVAILABLE,
    )
    report = collect_report()
    blob = str(report)
    assert "secret-dg-value" not in blob
    names = [row["name"] for row in report["checks"]]
    assert names == ["db", "dropbox", "elastic", "deepgram", "elevenlabs", "openai", "grok"]
