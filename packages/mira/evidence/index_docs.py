"""Index documents for Elastic. Search must preserve source IDs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

INDEX_TRANSACTIONS = "mira-transactions"
INDEX_INVOICES = "mira-invoices"
INDEX_CONTRACTS = "mira-contracts"
INDEX_POLICIES = "mira-policies"
INDEX_FINDINGS = "mira-findings"
INDEX_INCIDENTS = "mira-incidents"
INDEX_DECISIONS = "mira-decisions"
INDEX_EVIDENCE = "mira-evidence"

ALL_INDICES = (
    INDEX_TRANSACTIONS,
    INDEX_INVOICES,
    INDEX_CONTRACTS,
    INDEX_POLICIES,
    INDEX_FINDINGS,
    INDEX_INCIDENTS,
    INDEX_DECISIONS,
    INDEX_EVIDENCE,
)

KEYWORD = {"type": "keyword"}
TEXT = {"type": "text", "fields": {"raw": {"type": "keyword"}}}
DATE = {"type": "date"}
DOUBLE = {"type": "double"}


def _common_properties() -> dict[str, Any]:
    return {
        "source_id": KEYWORD,
        "source_type": KEYWORD,
        "company_id": KEYWORD,
        "title": TEXT,
        "body": TEXT,
        "status": KEYWORD,
        "as_of": DATE,
    }


INDEX_MAPPINGS: dict[str, dict[str, Any]] = {
    name: {"mappings": {"properties": {**_common_properties(), **extra}}}
    for name, extra in {
        INDEX_TRANSACTIONS: {
            "amount": DOUBLE,
            "currency": KEYWORD,
            "vendor_id": KEYWORD,
            "external_ref": KEYWORD,
            "posted_at": DATE,
        },
        INDEX_INVOICES: {
            "invoice_number": KEYWORD,
            "direction": KEYWORD,
            "vendor_id": KEYWORD,
            "customer_id": KEYWORD,
            "total": DOUBLE,
            "issue_date": DATE,
        },
        INDEX_CONTRACTS: {"vendor_id": KEYWORD, "extracted_terms": {"type": "object", "enabled": True}},
        INDEX_POLICIES: {"policy_type": KEYWORD, "version": KEYWORD, "rules": {"type": "object", "enabled": True}},
        INDEX_FINDINGS: {
            "finding_type": KEYWORD,
            "severity": KEYWORD,
            "risk_contribution": DOUBLE,
            "confidence_score": DOUBLE,
        },
        INDEX_INCIDENTS: {
            "risk_score": DOUBLE,
            "confidence_score": DOUBLE,
            "recommended_action": KEYWORD,
            "finding_ids": KEYWORD,
        },
        INDEX_DECISIONS: {
            "decision_type": KEYWORD,
            "action": KEYWORD,
            "confidence_score": DOUBLE,
            "risk_level": KEYWORD,
            "requires_human_approval": {"type": "boolean"},
        },
        INDEX_EVIDENCE: {"evidence_type": KEYWORD, "source_system": KEYWORD, "uri": KEYWORD},
    }.items()
}


class IndexDocument(BaseModel):
    """Projection of a canonical object. `_id` / source_id is the canonical UUID."""

    model_config = ConfigDict(frozen=True)

    index: str
    doc_id: str
    source_id: UUID
    source_type: str
    company_id: UUID
    body: dict[str, Any] = Field(default_factory=dict)


def _jsonish(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonish(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonish(v) for v in value]
    return value


def make_index_document(
    *,
    index: str,
    source_id: UUID,
    source_type: str,
    company_id: UUID,
    title: str,
    body_text: str,
    extra: dict[str, Any],
    status: str | None = None,
) -> IndexDocument:
    payload = {
        "source_id": str(source_id),
        "source_type": source_type,
        "company_id": str(company_id),
        "title": title,
        "body": body_text,
        "status": status,
        **{k: _jsonish(v) for k, v in extra.items()},
    }
    return IndexDocument(
        index=index,
        doc_id=str(source_id),
        source_id=source_id,
        source_type=source_type,
        company_id=company_id,
        body=payload,
    )
