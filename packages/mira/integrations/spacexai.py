"""Isolated SpaceXAI external signals: public space data + optional Grok Voice.

This module must not read or write finance snapshots, decisions, or savings.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

from mira.integrations.base import AdapterStatus

SPACEX_NEXT_LAUNCH = "https://api.spacexdata.com/v5/launches/next"
ISS_NOW = "https://api.wheretheiss.at/v1/satellites/25544"
XAI_MODELS = "https://api.x.ai/v1/models"
XAI_CHAT = "https://api.x.ai/v1/chat/completions"
XAI_SPEECH = "https://api.x.ai/v1/audio/speech"
DEFAULT_GROK_MODEL = "grok-3"
DEFAULT_GROK_VOICE_MODEL = "grok-voice"


class SpaceXAIIntegrationError(RuntimeError):
    """Raised when public space data or Grok Voice cannot be reached."""


class GrokVoiceAdapter:
    name = "grok"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = DEFAULT_GROK_MODEL,
        timeout: float = 20.0,
    ) -> None:
        self.api_key = api_key.strip() if api_key else None
        self.model = model
        self.timeout = timeout

    def status(self) -> AdapterStatus:
        return AdapterStatus.LIVE if self.api_key else AdapterStatus.DEMO

    def health_check(self) -> AdapterStatus:
        if not self.api_key:
            return AdapterStatus.DEMO
        try:
            response = httpx.get(
                XAI_MODELS,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SpaceXAIIntegrationError("Grok health check failed.") from exc
        return AdapterStatus.LIVE

    def narrate(self, observations: dict[str, Any]) -> str:
        """Spoken-style briefing of public space observations. Not finance."""
        fallback = _script_from_observations(observations)
        if not self.api_key:
            return fallback
        prompt = (
            "Narrate these public space observations in two short spoken sentences. "
            "Do not mention finance, invoices, companies, ledgers, or Mira."
        )
        try:
            response = httpx.post(
                XAI_CHAT,
                headers={**self._headers(), "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": _script_from_observations(observations)},
                    ],
                    "temperature": 0.2,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            text = (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content")
            )
            if isinstance(text, str) and text.strip():
                return text.strip()
        except (httpx.HTTPError, ValueError, LookupError, TypeError):
            return fallback
        return fallback

    def speak(self, text: str) -> bytes | None:
        """Optional Grok Voice audio for already-written space narration."""
        if not self.api_key or not text.strip():
            return None
        try:
            response = httpx.post(
                XAI_SPEECH,
                headers={**self._headers(), "Content-Type": "application/json"},
                json={
                    "model": DEFAULT_GROK_VOICE_MODEL,
                    "input": text.strip(),
                    "voice": "ara",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        return response.content or None

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise SpaceXAIIntegrationError("Grok credentials are not configured.")
        return {"Authorization": f"Bearer {self.api_key}"}


def fetch_space_signals(*, timeout: float = 8.0) -> dict[str, Any]:
    """Live public space observations with a labeled demo fallback."""
    if os.environ.get("MIRA_SPACE_OFFLINE") == "1":
        return {
            "isolated": True,
            "affects_finance_truth": False,
            "live": False,
            "as_of": datetime.now(UTC).isoformat(),
            "launch": _normalize_launch(None),
            "iss": _normalize_iss(None),
            "sources": [SPACEX_NEXT_LAUNCH, ISS_NOW],
        }
    launch = _get_json(SPACEX_NEXT_LAUNCH, timeout=timeout)
    iss = _get_json(ISS_NOW, timeout=timeout)
    live = bool(launch or iss)
    return {
        "isolated": True,
        "affects_finance_truth": False,
        "live": live,
        "as_of": datetime.now(UTC).isoformat(),
        "launch": _normalize_launch(launch),
        "iss": _normalize_iss(iss),
        "sources": [
            SPACEX_NEXT_LAUNCH,
            ISS_NOW,
        ],
    }


def _get_json(url: str, *, timeout: float) -> dict[str, Any] | None:
    try:
        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_launch(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {
            "name": "Next launch unavailable",
            "date_utc": None,
            "details": None,
            "provider": "demo_snapshot",
        }
    return {
        "name": payload.get("name"),
        "date_utc": payload.get("date_utc"),
        "details": payload.get("details"),
        "provider": "spacexdata",
    }


def _normalize_iss(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {
            "latitude": None,
            "longitude": None,
            "provider": "demo_snapshot",
        }
    return {
        "latitude": payload.get("latitude"),
        "longitude": payload.get("longitude"),
        "altitude": payload.get("altitude"),
        "provider": "wheretheiss.at",
    }


def _script_from_observations(observations: dict[str, Any]) -> str:
    launch = observations.get("launch") or {}
    iss = observations.get("iss") or {}
    launch_name = launch.get("name") or "the next launch"
    when = launch.get("date_utc") or "an unconfirmed time"
    lat = iss.get("latitude")
    lon = iss.get("longitude")
    iss_clause = (
        f"The ISS is near {lat}, {lon}."
        if lat is not None and lon is not None
        else "ISS position is currently unavailable."
    )
    return f"Next public launch is {launch_name} at {when}. {iss_clause}"
