"""Deepgram STT. Voice maps onto the same skill API as Zenni — no open chat."""

from __future__ import annotations

from mira.integrations.base import AdapterStatus


class DeepgramAdapter:
    name = "deepgram"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def status(self) -> AdapterStatus:
        return AdapterStatus.LIVE if self.api_key else AdapterStatus.DEMO
