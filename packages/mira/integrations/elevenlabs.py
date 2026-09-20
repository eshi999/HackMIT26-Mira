"""ElevenLabs TTS. Speaks Mira's already-computed text. Never generates finance."""

from __future__ import annotations

import httpx

from mira.integrations.base import AdapterStatus

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
ELEVENLABS_TTS = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
ELEVENLABS_USER = "https://api.elevenlabs.io/v1/user"
MAX_SPEAK_CHARS = 4000


class ElevenLabsIntegrationError(RuntimeError):
    """Raised when ElevenLabs cannot speak supplied Mira text."""


class ElevenLabsAdapter:
    name = "elevenlabs"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        voice_id: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.api_key = api_key.strip() if api_key else None
        self.voice_id = (voice_id or DEFAULT_VOICE_ID).strip() or DEFAULT_VOICE_ID
        self.timeout = timeout

    def status(self) -> AdapterStatus:
        return AdapterStatus.LIVE if self.api_key else AdapterStatus.DEMO

    def health_check(self) -> AdapterStatus:
        if not self.api_key:
            return AdapterStatus.DEMO
        try:
            response = httpx.get(
                ELEVENLABS_USER,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ElevenLabsIntegrationError("ElevenLabs health check failed.") from exc
        return AdapterStatus.LIVE

    def speak(self, text: str) -> bytes:
        """Synthesize speech for text Mira already produced.

        The model is not asked to reason, calculate, or invent finance.
        """
        if not self.api_key:
            raise ElevenLabsIntegrationError("ElevenLabs credentials are not configured.")
        spoken = text.strip()
        if not spoken:
            raise ElevenLabsIntegrationError("No Mira text was provided to speak.")
        if len(spoken) > MAX_SPEAK_CHARS:
            spoken = spoken[:MAX_SPEAK_CHARS]
        payload = {
            "text": spoken,
            "model_id": "eleven_turbo_v2_5",
        }
        try:
            response = httpx.post(
                ELEVENLABS_TTS.format(voice_id=self.voice_id),
                headers={**self._headers(), "Accept": "audio/mpeg", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ElevenLabsIntegrationError("ElevenLabs speech synthesis failed.") from exc
        if not response.content:
            raise ElevenLabsIntegrationError("ElevenLabs returned empty audio.")
        return response.content

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ElevenLabsIntegrationError("ElevenLabs credentials are not configured.")
        return {"xi-api-key": self.api_key}
