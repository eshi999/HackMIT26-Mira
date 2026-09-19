"""Public economic series. Demo mode uses seeded ExternalSignal rows."""

from __future__ import annotations

from mira.integrations.base import AdapterStatus


class PublicDataAdapter:
    name = "public_data"

    def status(self) -> AdapterStatus:
        return AdapterStatus.DEMO
