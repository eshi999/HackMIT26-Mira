from __future__ import annotations

from mira.core.models import CANONICAL_MODELS, Base

REQUIRED = {
    "Company",
    "User",
    "Employee",
    "Vendor",
    "Customer",
    "Account",
    "Invoice",
    "InvoiceLine",
    "PurchaseOrder",
    "GoodsReceipt",
    "Transaction",
    "LedgerEntry",
    "Contract",
    "Policy",
    "Approval",
    "Evidence",
    "Finding",
    "Incident",
    "RiskAssessment",
    "Decision",
    "AgentTask",
    "AgentRun",
    "Precedent",
    "Forecast",
    "Metric",
}


def test_canonical_models_are_mapped() -> None:
    names = {model.__name__ for model in CANONICAL_MODELS}
    missing = REQUIRED - names
    assert not missing, f"missing canonical models: {missing}"
    for model in CANONICAL_MODELS:
        assert model.__table__.name in Base.metadata.tables


def test_audit_event_is_append_only_hooked() -> None:
    assert "audit_events" in Base.metadata.tables
    table = Base.metadata.tables["audit_events"]
    assert "payload" in table.c
    assert "occurred_at" in table.c
