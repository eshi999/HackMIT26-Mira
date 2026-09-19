"""Dropbox evidence storage adapter.

Without Dropbox credentials, Mira falls back to the local demo inbox.
With credentials, the adapter can discover and download real Dropbox files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from mira.integrations.base import AdapterStatus

INBOX = Path("data/demo/inbox")

DROPBOX_API_BASE = "https://api.dropboxapi.com/2"
DROPBOX_CONTENT_BASE = "https://content.dropboxapi.com/2"


class DropboxIntegrationError(RuntimeError):
    """Raised when Dropbox cannot satisfy an integration request."""


@dataclass(frozen=True, slots=True)
class DropboxFile:
    """Normalized metadata for a file discovered in Dropbox."""

    id: str
    name: str
    path_display: str
    rev: str
    size: int
    server_modified: str | None = None
    content_hash: str | None = None
    is_downloadable: bool = True

    @classmethod
    def from_api_entry(cls, entry: dict[str, Any]) -> DropboxFile:
        return cls(
            id=entry["id"],
            name=entry["name"],
            path_display=entry.get("path_display") or entry["name"],
            rev=entry["rev"],
            size=entry.get("size", 0),
            server_modified=entry.get("server_modified"),
            content_hash=entry.get("content_hash"),
            is_downloadable=entry.get("is_downloadable", True),
        )


class StorageAdapter:
    """Storage adapter backed by Dropbox or Mira's local demo inbox."""

    name = "storage"

    def __init__(
        self,
        dropbox_token: str | None = None,
        *,
        timeout: float = 10.0,
    ) -> None:
        self.dropbox_token = dropbox_token
        self.timeout = timeout

    def status(self) -> AdapterStatus:
        return AdapterStatus.LIVE if self.dropbox_token else AdapterStatus.DEMO

    def list_inbox(self) -> list[Path]:
        """Return files from the local demo inbox.

        This preserves Mira's original offline/demo behavior.
        """

        if not INBOX.exists():
            return []

        return sorted(path for path in INBOX.iterdir() if path.is_file())

    def list_dropbox_files(
        self,
        path: str = "",
        *,
        recursive: bool = True,
    ) -> list[DropboxFile]:
        """Return files visible to the configured Dropbox app."""

        self._require_token()

        payload = {
            "path": path,
            "recursive": recursive,
            "include_deleted": False,
        }

        result = self._post_json(
            f"{DROPBOX_API_BASE}/files/list_folder",
            payload,
        )

        files: list[DropboxFile] = []

        while True:
            files.extend(self._extract_files(result))

            if not result.get("has_more", False):
                break

            cursor = result.get("cursor")
            if not cursor:
                raise DropboxIntegrationError(
                    "Dropbox returned has_more=true without a cursor."
                )

            result = self._post_json(
                f"{DROPBOX_API_BASE}/files/list_folder/continue",
                {"cursor": cursor},
            )

        return files

    def download_file(self, path: str) -> bytes:
        """Download a Dropbox file and return its raw bytes."""

        self._require_token()

        headers = {
            **self._authorization_headers(),
            "Dropbox-API-Arg": json.dumps({"path": path}),
        }

        try:
            response = httpx.post(
                f"{DROPBOX_CONTENT_BASE}/files/download",
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DropboxIntegrationError(
                f"Dropbox download failed for {path!r}."
            ) from exc

        return response.content

    def health_check(self) -> AdapterStatus:
        """Verify that configured Dropbox credentials can reach Dropbox."""

        if not self.dropbox_token:
            return AdapterStatus.DEMO

        try:
            self.list_dropbox_files(recursive=False)
        except DropboxIntegrationError:
            return AdapterStatus.UNAVAILABLE

        return AdapterStatus.LIVE

    def _authorization_headers(self) -> dict[str, str]:
        self._require_token()

        return {
            "Authorization": f"Bearer {self.dropbox_token}",
        }

    def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        headers = {
            **self._authorization_headers(),
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DropboxIntegrationError(
                "Dropbox metadata request failed."
            ) from exc

        if not isinstance(result, dict):
            raise DropboxIntegrationError(
                "Dropbox returned an unexpected response."
            )

        return result

    @staticmethod
    def _extract_files(result: dict[str, Any]) -> list[DropboxFile]:
        files: list[DropboxFile] = []

        for entry in result.get("entries", []):
            if entry.get(".tag") != "file":
                continue

            if not entry.get("is_downloadable", True):
                continue

            files.append(DropboxFile.from_api_entry(entry))

        return files

    def _require_token(self) -> None:
        if not self.dropbox_token:
            raise DropboxIntegrationError(
                "Dropbox credentials are not configured."
            )
