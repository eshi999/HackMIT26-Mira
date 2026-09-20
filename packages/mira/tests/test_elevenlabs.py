from __future__ import annotations

import httpx
import pytest

from mira.integrations.base import AdapterStatus
from mira.integrations.elevenlabs import ElevenLabsAdapter, ElevenLabsIntegrationError


def test_status_is_demo_without_key() -> None:
    assert ElevenLabsAdapter().status() == AdapterStatus.DEMO


def test_speak_sends_mira_text_only(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        captured["url"] = url
        captured["json"] = kwargs["json"]
        request = httpx.Request("POST", url)
        return httpx.Response(200, request=request, content=b"ID3fakeaudio")

    monkeypatch.setattr(httpx, "post", fake_post)
    audio = ElevenLabsAdapter("el-test").speak("AWS spend rose by 1800.")
    assert audio == b"ID3fakeaudio"
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["text"] == "AWS spend rose by 1800."
    assert "prompt" not in payload
    assert payload["model_id"]


def test_speak_without_key_errors() -> None:
    with pytest.raises(ElevenLabsIntegrationError):
        ElevenLabsAdapter().speak("hello")
