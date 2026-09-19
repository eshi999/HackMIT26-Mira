"""Elastic evidence index. Demo mode projects documents without a cluster."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from mira.evidence.index_docs import (
    ALL_INDICES,
    INDEX_CONTRACTS,
    INDEX_DECISIONS,
    INDEX_EVIDENCE,
    INDEX_FINDINGS,
    INDEX_INCIDENTS,
    INDEX_INVOICES,
    INDEX_MAPPINGS,
    INDEX_POLICIES,
    INDEX_TRANSACTIONS,
    IndexDocument,
    make_index_document,
)
from mira.finance.snapshot import FinanceSnapshot
from mira.integrations.base import AdapterStatus
from mira.risk.types import FinancialIncident, TypedFinding


class ElasticAdapter:
    name = "elastic"

    def __init__(self, url: str | None = None) -> None:
        self.url = url
        self._store: dict[str, dict[str, IndexDocument]] = {name: {} for name in ALL_INDICES}

    def status(self) -> AdapterStatus:
        return AdapterStatus.LIVE if self.url else AdapterStatus.DEMO

    def mappings(self) -> dict[str, Any]:
        return INDEX_MAPPINGS

    def index(self, document: IndexDocument) -> None:
        self._store.setdefault(document.index, {})[document.doc_id] = document

    def bulk_index(self, documents: Iterable[IndexDocument]) -> int:
        count = 0
        for document in documents:
            self.index(document)
            count += 1
        return count

    def get(self, index: str, source_id: UUID) -> IndexDocument | None:
        return self._store.get(index, {}).get(str(source_id))

    def search(self, query: str, *, index: str | None = None) -> tuple[IndexDocument, ...]:
        """SQL-shaped fallback: substring match over title/body while preserving source_id."""
        needle = query.lower()
        hits: list[IndexDocument] = []
        indices = [index] if index else list(self._store)
        for name in indices:
            for document in self._store.get(name, {}).values():
                blob = f"{document.body.get('title', '')} {document.body.get('body', '')} {document.source_id}"
                if needle in blob.lower():
                    hits.append(document)
        return tuple(hits)

    def project_snapshot(
        self,
        snapshot: FinanceSnapshot,
        *,
        findings: tuple[TypedFinding, ...] = (),
        incidents: tuple[FinancialIncident, ...] = (),
    ) -> tuple[IndexDocument, ...]:
        docs: list[IndexDocument] = []
        for txn in snapshot.transactions:
            docs.append(
                make_index_document(
                    index=INDEX_TRANSACTIONS,
                    source_id=txn.id,
                    source_type="transaction",
                    company_id=snapshot.company_id,
                    title=txn.description,
                    body_text=f"{txn.description} {txn.external_ref or ''} {txn.amount}",
                    extra={
                        "amount": txn.amount,
                        "currency": txn.currency,
                        "vendor_id": txn.vendor_id,
                        "external_ref": txn.external_ref,
                        "posted_at": txn.posted_at,
                    },
                    status=txn.source,
                )
            )
        for invoice in snapshot.invoices:
            docs.append(
                make_index_document(
                    index=INDEX_INVOICES,
                    source_id=invoice.id,
                    source_type="invoice",
                    company_id=snapshot.company_id,
                    title=invoice.invoice_number,
                    body_text=f"{invoice.invoice_number} {invoice.total} {invoice.status}",
                    extra={
                        "invoice_number": invoice.invoice_number,
                        "direction": invoice.direction,
                        "vendor_id": invoice.vendor_id,
                        "customer_id": invoice.customer_id,
                        "total": invoice.total,
                        "issue_date": invoice.issue_date,
                    },
                    status=invoice.status,
                )
            )
        for contract in snapshot.contracts:
            docs.append(
                make_index_document(
                    index=INDEX_CONTRACTS,
                    source_id=contract.id,
                    source_type="contract",
                    company_id=snapshot.company_id,
                    title=contract.title,
                    body_text=str(contract.extracted_terms),
                    extra={"vendor_id": contract.vendor_id, "extracted_terms": contract.extracted_terms},
                    status=contract.status,
                )
            )
        for policy in snapshot.policies:
            docs.append(
                make_index_document(
                    index=INDEX_POLICIES,
                    source_id=policy.id,
                    source_type="policy",
                    company_id=snapshot.company_id,
                    title=policy.name,
                    body_text=policy.body,
                    extra={"policy_type": policy.policy_type, "version": policy.version, "rules": policy.rules},
                    status=policy.status,
                )
            )
        for finding in findings:
            docs.append(
                make_index_document(
                    index=INDEX_FINDINGS,
                    source_id=finding.id,
                    source_type="finding",
                    company_id=snapshot.company_id,
                    title=finding.title,
                    body_text=finding.description,
                    extra={
                        "finding_type": finding.finding_type.value,
                        "severity": finding.severity.value,
                        "risk_contribution": finding.risk_contribution,
                        "confidence_score": finding.confidence.score,
                    },
                    status="open",
                )
            )
        for incident in incidents:
            docs.append(
                make_index_document(
                    index=INDEX_INCIDENTS,
                    source_id=incident.id,
                    source_type="incident",
                    company_id=snapshot.company_id,
                    title=incident.title,
                    body_text=incident.explanation,
                    extra={
                        "risk_score": incident.risk_score,
                        "confidence_score": incident.confidence.score,
                        "recommended_action": incident.recommended_action.value,
                        "finding_ids": [str(f.id) for f in incident.findings],
                    },
                    status="open",
                )
            )
        for decision in snapshot.decisions:
            docs.append(
                make_index_document(
                    index=INDEX_DECISIONS,
                    source_id=decision.id,
                    source_type="decision",
                    company_id=snapshot.company_id,
                    title=decision.action,
                    body_text=decision.action,
                    extra={
                        "decision_type": decision.decision_type,
                        "action": decision.action,
                        "confidence_score": decision.confidence_score,
                        "risk_level": decision.risk_level,
                        "requires_human_approval": decision.requires_human_approval,
                    },
                    status=decision.status,
                )
            )
        for evidence in snapshot.evidence:
            docs.append(
                make_index_document(
                    index=INDEX_EVIDENCE,
                    source_id=evidence.id,
                    source_type="evidence",
                    company_id=snapshot.company_id,
                    title=evidence.title,
                    body_text=evidence.snippet or evidence.title,
                    extra={
                        "evidence_type": evidence.evidence_type,
                        "source_system": evidence.source_system,
                        "uri": evidence.uri,
                    },
                )
            )
        self.bulk_index(docs)
        return tuple(docs)
