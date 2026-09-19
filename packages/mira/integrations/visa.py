"""Visa sandbox payments. Always labeled is_sandbox=true in this hackathon."""

from __future__ import annotations

from mira.integrations.base import AdapterStatus


class VisaAdapter:
    name = "visa"

    def status(self) -> AdapterStatus:
        return AdapterStatus.DEMO
