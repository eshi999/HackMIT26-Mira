from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class AdapterStatus(StrEnum):
    LIVE = "live"
    DEMO = "demo"
    UNAVAILABLE = "unavailable"


class Adapter(Protocol):
    name: str

    def status(self) -> AdapterStatus: ...
