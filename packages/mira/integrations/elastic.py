"""Elastic evidence index. Demo mode: not connected."""

from __future__ import annotations

from mira.integrations.base import AdapterStatus


class ElasticAdapter:
    name = "elastic"

    def __init__(self, url: str | None = None) -> None:
        self.url = url

    def status(self) -> AdapterStatus:
        return AdapterStatus.LIVE if self.url else AdapterStatus.DEMO
