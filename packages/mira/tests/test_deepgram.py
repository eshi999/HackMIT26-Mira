from __future__ import annotations

import httpx
import pytest

from mira.integrations.base import AdapterStatus
from mira.integrations.deepgram import DeepgramAdapter, DeepgramIntegrationError, Transcript


def make_response(status_code: int, *, url: str, json_data: dict | None = None) -> httpx.Response:
    request = httpx.Request("POST", url)
    return httpx.Response(status_code, request=request, json=json_data or {})


def test_status_is_demo_without_key() -> None:
    assert DeepgramAdapter().status() == AdapterStatus.DEMO


def test_status_is_live_with_key() -> None:
    assert DeepgramAdapter("dg-test").status() == AdapterStatus.LIVE


def test_transcribe_extracts_transcript(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        assert "listen" in url
        headers = kwargs["headers"]
        assert isinstance(headers, dict)
        assert headers["Authorization"] == "Token dg-test"
        return make_response(
            200,
            url=url,
            json_data={
                "results": {
                    "channels": [
                        {"alternatives": [{"transcript": "Run today's finance review.", "confidence": 0.98}]}
                    ]
                }
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = DeepgramAdapter("dg-test").transcribe(b"fake-audio", "audio/webm")
    assert isinstance(result, Transcript)
    assert result.text == "Run today's finance review."
    assert result.confidence == 0.98


def test_transcribe_without_key_errors() -> None:
    with pytest.raises(DeepgramIntegrationError):
        DeepgramAdapter().transcribe(b"audio")


def test_empty_transcript_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kwargs: make_response(200, url=url, json_data={"results": {"channels": []}}),
    )
    with pytest.raises(DeepgramIntegrationError):
        DeepgramAdapter("dg-test").transcribe(b"audio")
