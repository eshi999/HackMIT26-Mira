from pathlib import Path

import httpx
import pytest

from mira.integrations import dropbox
from mira.integrations.base import AdapterStatus
from mira.integrations.dropbox import (
    DropboxIntegrationError,
    StorageAdapter,
)


def make_response(
    status_code: int,
    *,
    url: str,
    json_data: dict | None = None,
    content: bytes | None = None,
) -> httpx.Response:
    request = httpx.Request("POST", url)

    if json_data is not None:
        return httpx.Response(
            status_code,
            request=request,
            json=json_data,
        )

    return httpx.Response(
        status_code,
        request=request,
        content=content or b"",
    )


def test_status_is_demo_without_token() -> None:
    adapter = StorageAdapter()

    assert adapter.status() == AdapterStatus.DEMO


def test_status_is_live_with_token() -> None:
    adapter = StorageAdapter("test-token")

    assert adapter.status() == AdapterStatus.LIVE


def test_list_inbox_preserves_demo_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "a.txt"
    second = tmp_path / "b.pdf"

    first.write_text("one")
    second.write_text("two")
    (tmp_path / "nested").mkdir()

    monkeypatch.setattr(dropbox, "INBOX", tmp_path)

    adapter = StorageAdapter()

    assert adapter.list_inbox() == [first, second]


def test_list_dropbox_files_normalizes_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        assert url.endswith("/files/list_folder")

        return make_response(
            200,
            url=url,
            json_data={
                "entries": [
                    {
                        ".tag": "file",
                        "id": "id:test",
                        "name": "invoice.pdf",
                        "path_display": "/invoice.pdf",
                        "rev": "123",
                        "size": 42,
                        "server_modified": "2026-09-19T19:45:56Z",
                        "content_hash": "abc123",
                        "is_downloadable": True,
                    }
                ],
                "cursor": "cursor-1",
                "has_more": False,
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    adapter = StorageAdapter("test-token")
    files = adapter.list_dropbox_files()

    assert len(files) == 1

    file = files[0]

    assert file.id == "id:test"
    assert file.name == "invoice.pdf"
    assert file.path_display == "/invoice.pdf"
    assert file.rev == "123"
    assert file.size == 42
    assert file.content_hash == "abc123"


def test_list_dropbox_files_handles_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        calls.append(url)

        if url.endswith("/files/list_folder"):
            return make_response(
                200,
                url=url,
                json_data={
                    "entries": [
                        {
                            ".tag": "file",
                            "id": "id:first",
                            "name": "first.txt",
                            "path_display": "/first.txt",
                            "rev": "1",
                            "size": 10,
                        }
                    ],
                    "cursor": "cursor-next",
                    "has_more": True,
                },
            )

        return make_response(
            200,
            url=url,
            json_data={
                "entries": [
                    {
                        ".tag": "file",
                        "id": "id:second",
                        "name": "second.txt",
                        "path_display": "/second.txt",
                        "rev": "2",
                        "size": 20,
                    }
                ],
                "cursor": "cursor-done",
                "has_more": False,
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    adapter = StorageAdapter("test-token")
    files = adapter.list_dropbox_files()

    assert [file.name for file in files] == [
        "first.txt",
        "second.txt",
    ]

    assert len(calls) == 2
    assert calls[1].endswith("/files/list_folder/continue")


def test_download_file_returns_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        assert url.endswith("/files/download")

        headers = kwargs["headers"]
        assert isinstance(headers, dict)
        assert "Dropbox-API-Arg" in headers

        return make_response(
            200,
            url=url,
            content=b"Mira Dropbox integration test\n",
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    adapter = StorageAdapter("test-token")

    content = adapter.download_file("/mira-dropbox-test.txt")

    assert content == b"Mira Dropbox integration test\n"


def test_dropbox_failure_becomes_integration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        return make_response(
            401,
            url=url,
            json_data={
                "error": {
                    ".tag": "invalid_access_token",
                }
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    adapter = StorageAdapter("bad-token")

    with pytest.raises(DropboxIntegrationError):
        adapter.list_dropbox_files()


def test_health_check_reports_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        return make_response(
            503,
            url=url,
            json_data={"error": "unavailable"},
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    adapter = StorageAdapter("test-token")

    assert adapter.health_check() == AdapterStatus.UNAVAILABLE
