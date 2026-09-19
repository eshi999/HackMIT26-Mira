from __future__ import annotations


def test_health_ok(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "mira-api"


def test_ready_after_seed(client) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "up"
    assert body["seeded"] is True
    assert body["company"] == "Northstar Labs"


def test_company_is_northstar(client) -> None:
    response = client.get("/api/v1/company")
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "northstar-labs"
    assert body["name"] == "Northstar Labs"
    assert body["legal_name"] == "Northstar Labs, Inc."


def test_briefing_is_not_a_chatbot(client) -> None:
    response = client.get("/api/v1/briefing")
    assert response.status_code == 200
    body = response.json()
    assert "chat" not in body["headline"].lower()
    assert body["mira_status"] == "on_duty"
    assert body["company"]["name"] == "Northstar Labs"
    assert float(body["savings"]["dollars_protected"]) >= 18400
    assert float(body["savings"]["hours_saved"]) >= 8
    assert any(d["requires_human_approval"] for d in body["pending_decisions"])
    assert any(i["is_duplicate_suspect"] for i in body["invoices"])
    assert any(s["series_id"] == "DGS3MO" for s in body["signals"])
    assert "sandbox" in body["sandbox_notice"].lower()


def test_meta_declares_agents_not_implemented(client) -> None:
    response = client.get("/api/v1/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["agents_implemented"] is False
    mira = next(m for m in body["org"] if m["role"] == "mira_cfo")
    assert mira["speaks_to_user"] is True
    specialists = [m for m in body["org"] if m["role"] != "mira_cfo"]
    assert specialists
    assert all(m["speaks_to_user"] is False for m in specialists)
    assert body["adapters"]["visa"] == "demo"
