"""Secret-safe readiness probes for demo-doctor."""

from __future__ import annotations

import os
from typing import Any

from mira.integrations.base import AdapterStatus
from mira.integrations.deepgram import DeepgramAdapter, DeepgramIntegrationError
from mira.integrations.dropbox import StorageAdapter
from mira.integrations.elastic import ElasticAdapter
from mira.integrations.elevenlabs import ElevenLabsAdapter, ElevenLabsIntegrationError
from mira.integrations.spacexai import GrokVoiceAdapter, SpaceXAIIntegrationError


def key_configured(*names: str) -> bool:
    return any(bool(os.environ.get(name, "").strip()) for name in names)


def _probe(check) -> str:
    try:
        status = check()
    except Exception:
        return AdapterStatus.UNAVAILABLE.value
    if isinstance(status, AdapterStatus):
        return status.value
    return AdapterStatus.UNAVAILABLE.value


def integration_row(name: str, configured: bool, status: str, note: str) -> dict[str, Any]:
    return {
        "name": name,
        "configured": configured,
        "status": status,
        "note": note,
    }


def dropbox_row() -> dict[str, Any]:
    token = os.environ.get("DROPBOX_ACCESS_TOKEN")
    adapter = StorageAdapter(token)
    configured = key_configured("DROPBOX_ACCESS_TOKEN")
    status = _probe(adapter.health_check)
    note = "token not configured" if not configured else "health checked"
    return integration_row("dropbox", configured, status, note)


def elastic_row() -> dict[str, Any]:
    adapter = ElasticAdapter(
        os.environ.get("ELASTICSEARCH_URL") or None,
        api_key=os.environ.get("ELASTICSEARCH_API_KEY") or None,
    )
    configured = key_configured("ELASTICSEARCH_URL")
    status = _probe(adapter.health_check)
    note = "url not configured" if not configured else "cluster health checked"
    return integration_row("elastic", configured, status, note)


def deepgram_row() -> dict[str, Any]:
    adapter = DeepgramAdapter(os.environ.get("DEEPGRAM_API_KEY"))
    configured = key_configured("DEEPGRAM_API_KEY")
    if not configured:
        return integration_row("deepgram", False, AdapterStatus.DEMO.value, "key not configured")
    try:
        status = adapter.health_check().value
        note = "health checked"
    except DeepgramIntegrationError:
        status = AdapterStatus.UNAVAILABLE.value
        note = "configured but unreachable"
    return integration_row("deepgram", True, status, note)


def elevenlabs_row() -> dict[str, Any]:
    adapter = ElevenLabsAdapter(os.environ.get("ELEVENLABS_API_KEY"))
    configured = key_configured("ELEVENLABS_API_KEY")
    if not configured:
        return integration_row("elevenlabs", False, AdapterStatus.DEMO.value, "key not configured")
    try:
        status = adapter.health_check().value
        note = "health checked"
    except ElevenLabsIntegrationError:
        status = AdapterStatus.UNAVAILABLE.value
        note = "configured but unreachable"
    return integration_row("elevenlabs", True, status, note)


def grok_row() -> dict[str, Any]:
    adapter = GrokVoiceAdapter(os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY"))
    configured = key_configured("XAI_API_KEY", "GROK_API_KEY")
    if not configured:
        return integration_row("grok", False, AdapterStatus.DEMO.value, "key not configured")
    try:
        status = adapter.health_check().value
        note = "health checked"
    except SpaceXAIIntegrationError:
        status = AdapterStatus.UNAVAILABLE.value
        note = "configured but unreachable"
    return integration_row("grok", True, status, note)
