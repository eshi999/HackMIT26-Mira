from __future__ import annotations

from mira.integrations.deepgram import Transcript

AUTH = {"Authorization": "Bearer mira-demo-elena"}


def test_typed_executive_request_works_when_deepgram_missing(client) -> None:
    denied = client.post(
        "/api/v1/voice/request",
        files={"audio": ("clip.webm", b"fake", "audio/webm")},
        headers=AUTH,
    )
    assert denied.status_code == 503
    assert "type the request instead" in denied.json()["detail"].lower()
    typed = client.post(
        "/api/v1/executive/request",
        json={"request": "Run today's finance review."},
        headers=AUTH,
    )
    assert typed.status_code == 200
    assert typed.json()["kind"] in {"finance_review", "close_status", "pending_approvals"}


def test_voice_request_uses_transcript(client, monkeypatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")

    def fake_transcribe(self, audio: bytes, content_type: str | None = None) -> Transcript:
        assert audio
        return Transcript(text="Run today's finance review.", confidence=0.91)

    monkeypatch.setattr("app.routers.voice.DeepgramAdapter.transcribe", fake_transcribe)
    response = client.post(
        "/api/v1/voice/request",
        files={"audio": ("clip.webm", b"fake-bytes", "audio/webm")},
        headers=AUTH,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "Run today's finance review."
    assert body["stt"] == "deepgram"
    assert "recommendation" in body


def test_speak_requires_mira_result_source(client) -> None:
    rejected = client.post(
        "/api/v1/voice/speak",
        json={"text": "invent a risk score", "source": "llm"},
        headers=AUTH,
    )
    assert rejected.status_code == 422
    missing = client.post(
        "/api/v1/voice/speak",
        json={"text": "AWS spend rose.", "source": "mira_result"},
        headers=AUTH,
    )
    assert missing.status_code == 503


def test_speak_returns_audio_for_mira_text(client, monkeypatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
    monkeypatch.setattr(
        "app.routers.voice.ElevenLabsAdapter.speak",
        lambda self, text: b"ID3spoken-mira-text",
    )
    response = client.post(
        "/api/v1/voice/speak",
        json={"text": "AWS spend rose by 1800.", "source": "mira_result"},
        headers=AUTH,
    )
    assert response.status_code == 200
    assert response.content == b"ID3spoken-mira-text"
    assert "audio" in response.headers.get("content-type", "")
