from uuid import UUID

import httpx
import pytest

from mira.evidence.index_docs import INDEX_EVIDENCE, make_index_document
from mira.integrations.base import AdapterStatus
from mira.integrations.elastic import (
    ElasticAdapter,
    ElasticIntegrationError,
)

SOURCE_ID = UUID("11111111-1111-1111-1111-111111111111")
COMPANY_ID = UUID("22222222-2222-2222-2222-222222222222")


def make_response(
    status_code: int,
    *,
    method: str,
    url: str,
    json_data: dict | None = None,
) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(
        status_code,
        request=request,
        json=json_data or {},
    )


def sample_document():
    return make_index_document(
        index=INDEX_EVIDENCE,
        source_id=SOURCE_ID,
        source_type="evidence",
        company_id=COMPANY_ID,
        title="HelixCloud invoice",
        body_text="Duplicate invoice investigation",
        extra={
            "evidence_type": "invoice",
            "source_system": "dropbox",
            "uri": "dropbox://invoice",
        },
    )


def test_health_check_is_demo_without_url() -> None:
    adapter = ElasticAdapter()

    assert adapter.health_check() == AdapterStatus.DEMO


def test_health_check_is_live_when_cluster_responds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        assert method == "GET"
        assert url.endswith("/_cluster/health")
        return make_response(
            200,
            method=method,
            url=url,
            json_data={"status": "green"},
        )

    monkeypatch.setattr(httpx, "request", fake_request)

    adapter = ElasticAdapter("http://elastic:9200")

    assert adapter.health_check() == AdapterStatus.LIVE


def test_health_check_reports_unavailable_on_network_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        request = httpx.Request(method, url)
        raise httpx.ConnectError("offline", request=request)

    monkeypatch.setattr(httpx, "request", fake_request)

    adapter = ElasticAdapter("http://elastic:9200")

    assert adapter.health_check() == AdapterStatus.UNAVAILABLE


def test_live_index_creates_mapping_and_indexes_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        calls.append((method, url, kwargs))

        if method == "GET" and url.endswith("/mira-evidence"):
            return make_response(404, method=method, url=url)

        if method == "PUT" and url.endswith("/mira-evidence"):
            return make_response(
                200,
                method=method,
                url=url,
                json_data={"acknowledged": True},
            )

        if method == "PUT" and "/mira-evidence/_doc/" in url:
            return make_response(
                201,
                method=method,
                url=url,
                json_data={"result": "created"},
            )

        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(httpx, "request", fake_request)

    adapter = ElasticAdapter("http://elastic:9200")
    document = sample_document()

    adapter.index(document)

    assert len(calls) == 3

    create_call = calls[1]
    assert create_call[0] == "PUT"
    assert create_call[2]["json"] is not None

    index_call = calls[2]
    assert index_call[0] == "PUT"
    assert index_call[2]["json"] == document.body


def test_live_get_reconstructs_index_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = sample_document()

    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        return make_response(
            200,
            method=method,
            url=url,
            json_data={
                "_index": INDEX_EVIDENCE,
                "_id": document.doc_id,
                "_source": document.body,
            },
        )

    monkeypatch.setattr(httpx, "request", fake_request)

    adapter = ElasticAdapter("http://elastic:9200")

    result = adapter.get(INDEX_EVIDENCE, SOURCE_ID)

    assert result is not None
    assert result.source_id == SOURCE_ID
    assert result.company_id == COMPANY_ID
    assert result.body["title"] == "HelixCloud invoice"


def test_live_get_returns_none_for_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        return make_response(404, method=method, url=url)

    monkeypatch.setattr(httpx, "request", fake_request)

    adapter = ElasticAdapter("http://elastic:9200")

    assert adapter.get(INDEX_EVIDENCE, SOURCE_ID) is None


def test_live_search_preserves_canonical_source_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = sample_document()

    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        assert method == "POST"
        assert url.endswith("/mira-evidence/_search")

        return make_response(
            200,
            method=method,
            url=url,
            json_data={
                "hits": {
                    "hits": [
                        {
                            "_index": INDEX_EVIDENCE,
                            "_id": document.doc_id,
                            "_source": document.body,
                        }
                    ]
                }
            },
        )

    monkeypatch.setattr(httpx, "request", fake_request)

    adapter = ElasticAdapter("http://elastic:9200")

    hits = adapter.search("HelixCloud", index=INDEX_EVIDENCE)

    assert len(hits) == 1
    assert hits[0].source_id == SOURCE_ID
    assert hits[0].body["title"] == "HelixCloud invoice"


def test_api_key_is_sent_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        headers = kwargs["headers"]

        assert isinstance(headers, dict)
        assert headers["Authorization"] == "ApiKey secret-test-key"

        return make_response(
            200,
            method=method,
            url=url,
            json_data={"status": "green"},
        )

    monkeypatch.setattr(httpx, "request", fake_request)

    adapter = ElasticAdapter(
        "https://elastic.example",
        api_key="secret-test-key",
    )

    assert adapter.health_check() == AdapterStatus.LIVE


def test_live_request_failure_becomes_integration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        return make_response(
            500,
            method=method,
            url=url,
            json_data={"error": "boom"},
        )

    monkeypatch.setattr(httpx, "request", fake_request)

    adapter = ElasticAdapter("http://elastic:9200")

    with pytest.raises(ElasticIntegrationError):
        adapter.search("HelixCloud")
