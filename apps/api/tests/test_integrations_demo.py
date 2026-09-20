from __future__ import annotations

AUTH = {"Authorization": "Bearer mira-demo-elena"}


def test_evidence_search_reports_retrieval_source(client) -> None:
    response = client.get("/api/v1/evidence/search", params={"q": "HelixCloud"})
    assert response.status_code == 200
    body = response.json()
    assert body["retrieval_source"] in {"elastic", "elastic-demo"}
    assert body["hit_count"] >= 1
    assert body["hits"]
    assert "explanation" in body


def test_briefing_inbox_includes_lineage(client) -> None:
    response = client.get("/api/v1/briefing")
    assert response.status_code == 200
    inbox = response.json()["inbox"]
    assert inbox
    assert any(row.get("lineage") and "inbox" in row["lineage"].lower() for row in inbox)


def test_precedents_list_and_measured_context(client) -> None:
    rows = client.get("/api/v1/precedents")
    assert rows.status_code == 200
    assert "precedents" in rows.json()
    measured = client.get("/api/v1/context/measured", headers=AUTH)
    assert measured.status_code == 200
    body = measured.json()
    assert body["scenario_count"] == 6
    assert body["correctness_retained"] is True
    assert body["correctness_retained_label"] == "6/6"
    assert body["tokens_avoided"] > 0
    assert body["source"] == "make token-eval"


def test_space_signals_are_isolated(client) -> None:
    response = client.get("/api/v1/external-signals/space")
    assert response.status_code == 200
    body = response.json()
    assert body["isolated"] is True
    assert body["affects_finance_truth"] is False
    assert "narration" in body


def test_meta_includes_voice_adapters(client) -> None:
    body = client.get("/api/v1/meta").json()
    assert body["adapters"]["deepgram"] == "demo"
    assert body["adapters"]["elevenlabs"] == "demo"
    assert body["adapters"]["grok"] == "demo"
    assert body["openai_configured"] is False
