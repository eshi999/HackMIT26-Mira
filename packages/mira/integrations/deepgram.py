"""Deepgram STT. Voice maps onto the same executive request API as typed input."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from mira.integrations.base import AdapterStatus

DEEPGRAM_LISTEN = "https://api.deepgram.com/v1/listen"
DEEPGRAM_PROJECTS = "https://api.deepgram.com/v1/projects"


class DeepgramIntegrationError(RuntimeError):
    """Raised when Deepgram cannot transcribe audio."""


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    confidence: float | None
    provider: str = "deepgram"


class DeepgramAdapter:
    name = "deepgram"

    def __init__(self, api_key: str | None = None, *, timeout: float = 8.0) -> None:
        self.api_key = api_key.strip() if api_key else None
        self.timeout = timeout

    def status(self) -> AdapterStatus:
        return AdapterStatus.LIVE if self.api_key else AdapterStatus.DEMO

    def health_check(self) -> AdapterStatus:
        if not self.api_key:
            return AdapterStatus.DEMO
        try:
            response = httpx.get(
                DEEPGRAM_PROJECTS,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DeepgramIntegrationError("Deepgram health check failed.") from exc
        return AdapterStatus.LIVE

    def transcribe(self, audio: bytes, content_type: str | None = None) -> Transcript:
        if not self.api_key:
            raise DeepgramIntegrationError("Deepgram credentials are not configured.")
        if not audio:
            raise DeepgramIntegrationError("No audio was provided.")
        headers = {
            **self._headers(),
            "Content-Type": content_type or "application/octet-stream",
        }
        try:
            response = httpx.post(
                DEEPGRAM_LISTEN,
                headers=headers,
                params={"model": "nova-2", "smart_format": "true", "punctuate": "true"},
                content=audio,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DeepgramIntegrationError("Deepgram transcription failed.") from exc
        text, confidence = _extract_transcript(payload)
        if not text:
            raise DeepgramIntegrationError("Deepgram returned an empty transcript.")
        return Transcript(text=text, confidence=confidence)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise DeepgramIntegrationError("Deepgram credentials are not configured.")
        return {"Authorization": f"Token {self.api_key}"}


def _extract_transcript(payload: object) -> tuple[str, float | None]:
    if not isinstance(payload, dict):
        return "", None
    results = payload.get("results") or {}
    channels = results.get("channels") or []
    if not channels:
        return "", None
    alternatives = channels[0].get("alternatives") or []
    if not alternatives:
        return "", None
    alt = alternatives[0]
    text = str(alt.get("transcript") or "").strip()
    raw_confidence = alt.get("confidence")
    confidence = float(raw_confidence) if isinstance(raw_confidence, int | float) else None
    return text, confidence
