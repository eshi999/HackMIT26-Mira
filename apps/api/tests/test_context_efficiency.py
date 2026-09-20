from sqlalchemy import func, select

from mira.core.db import get_sessionmaker
from mira.core.models import AgentTask, Approval, Decision, Finding, SavingsEvent


def test_efficiency_requires_actor(client):
    assert client.get("/api/v1/context/efficiency").status_code == 401


def test_efficiency_is_read_only_and_reproducible(client, monkeypatch):
    from app.config import get_settings

    Session = get_sessionmaker(get_settings().database_url)

    def counts():
        with Session() as db:
            return [
                db.scalar(select(func.count()).select_from(model))
                for model in (AgentTask, Approval, Decision, Finding, SavingsEvent)
            ]

    before = counts()
    headers = {"Authorization": "Bearer mira-demo-elena"}
    first = client.get("/api/v1/context/efficiency", headers=headers)
    second = client.get("/api/v1/context/efficiency", headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    report = first.json()
    assert report["read_only"] and report["correctness_retained"]
    assert report["tokens_avoided"] > 0
    assert report["usage_source"] == "estimated"
    assert report["cost_savings"] is None
    assert counts() == before


def test_efficiency_failure_does_not_claim_correctness(client, monkeypatch):
    def corrupt(snapshot):
        raise AssertionError("Financial truth changed")

    monkeypatch.setattr("app.routers.context.evaluate", corrupt)
    response = client.get(
        "/api/v1/context/efficiency", headers={"Authorization": "Bearer mira-demo-elena"}
    )
    assert response.status_code == 409
    assert "correctness_retained" not in response.json()
