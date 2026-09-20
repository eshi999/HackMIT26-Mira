"""Exact serialization and a bounded, instance-owned source encoding cache."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from threading import Lock
from typing import Any
from uuid import UUID

from pydantic import BaseModel


def _default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Decimal | UUID | date | datetime):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Unsupported context value: {type(value).__name__}")


def encode(value: Any) -> str:
    return json.dumps(
        value,
        default=_default,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def estimate_tokens(text: str) -> int:
    """Offline heuristic: ceil(UTF-8 bytes / 4), NOT a provider tokenizer or bill."""
    return (len(text.encode("utf-8")) + 3) // 4


class SourceEncodingCache:
    """Only serializes source records; never stores engine results or decision state.

    Revision AND content participate so even in-place nested changes invalidate.
    The string value cannot be mutated by a caller. No process-global instance.
    """

    def __init__(self, capacity: int = 128):
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._entries: OrderedDict[tuple[str, ...], str] = OrderedDict()
        self._lock = Lock()
        self.hits = 0
        self.misses = 0

    def serialize(
        self,
        *,
        company_id: UUID,
        task_id: str,
        profile: str,
        source_id: str,
        revision: str,
        value: Any,
    ) -> str:
        serialized = encode(value)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        key = (str(company_id), task_id, profile, source_id, revision, digest)
        with self._lock:
            if key in self._entries:
                self.hits += 1
                self._entries.move_to_end(key)
                return self._entries[key]
            self.misses += 1
            self._entries[key] = serialized
            if len(self._entries) > self.capacity:
                self._entries.popitem(last=False)
            return serialized
