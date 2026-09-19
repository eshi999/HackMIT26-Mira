from __future__ import annotations


def test_executive_request_finance_review(client) -> None:
    response = client.post("/api/v1/executive/request", json={"request": "Run today's finance review."})
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] in {"finance_review", "close_status", "pending_approvals"}
    assert "recommendation" in body
    assert "chat" not in body["recommendation"]["headline"].lower()


def test_executive_request_month_end(client) -> None:
    response = client.post("/api/v1/executive/request", json={"request": "What's blocking month-end close?"})
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "close_status"
    assert "close" in body["artifact"]


def test_briefing_uses_runtime_savings(client) -> None:
    response = client.get("/api/v1/briefing")
    assert response.status_code == 200
    body = response.json()
    assert body["savings"]["source"] == "runtime"
    assert float(body["savings"]["dollars_protected"]) >= 18400
    assert float(body["savings"]["hours_saved"]) >= 8
    assert "chat" not in body["headline"].lower()
    assert body["pending_approvals"] >= 1
