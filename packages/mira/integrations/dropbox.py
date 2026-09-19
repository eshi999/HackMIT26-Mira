"""Dropbox folder ingest. Demo mode: local data/demo/inbox."""

from __future__ import annotations

from pathlib import Path

from mira.integrations.base import AdapterStatus

INBOX = Path("data/demo/inbox")


class StorageAdapter:
    name = "storage"

    def __init__(self, dropbox_token: str | None = None) -> None:
        self.dropbox_token = dropbox_token

    def status(self) -> AdapterStatus:
        return AdapterStatus.LIVE if self.dropbox_token else AdapterStatus.DEMO

    def list_inbox(self) -> list[Path]:
        if not INBOX.exists():
            return []
        return sorted(p for p in INBOX.iterdir() if p.is_file())
