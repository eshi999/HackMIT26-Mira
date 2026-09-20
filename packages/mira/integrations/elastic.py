"""Elastic evidence index. Demo mode projects documents without a cluster."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

import httpx

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


class ElasticIntegrationError(RuntimeError):
    """Raised when live Elasticsearch cannot satisfy a request."""


class ElasticAdapter:
    name = "elastic"

    def __init__(
        self,
        url: str | None = None,
        *,
        api_key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.url = url.rstrip("/") if url else None
        self.api_key = api_key
        self.timeout = timeout

        # Demo fallback. SQL remains canonical truth and this in-memory
        # representation keeps Mira usable without Elasticsearch.
        self._store: dict[str, dict[str, IndexDocument]] = {
            name: {} for name in ALL_INDICES
        }

        # Avoid checking index existence before every document write.
        self._ensured_indices: set[str] = set()

    def status(self) -> AdapterStatus:
        return AdapterStatus.LIVE if self.url else AdapterStatus.DEMO

    def health_check(self) -> AdapterStatus:
        """Check whether configured Elasticsearch is actually reachable."""

        if not self.url:
            return AdapterStatus.DEMO

        try:
            self._request("GET", "/_cluster/health")
        except ElasticIntegrationError:
            return AdapterStatus.UNAVAILABLE

        return AdapterStatus.LIVE

    def mappings(self) -> dict[str, Any]:
        return INDEX_MAPPINGS

    def ensure_indices(self) -> None:
        """Create Mira indices with their canonical mappings when needed."""

        if not self.url:
            return

        for name in ALL_INDICES:
            self._ensure_index(name)

    def index(self, document: IndexDocument) -> None:
        """Index one document into live Elastic or the demo memory store."""

        if not self.url:
            self._store.setdefault(document.index, {})[document.doc_id] = document
            return

        self._ensure_index(document.index)

        self._request(
            "PUT",
            f"/{document.index}/_doc/{document.doc_id}",
            json_body=document.body,
            params={"refresh": "true"},
        )

    def bulk_index(self, documents: Iterable[IndexDocument]) -> int:
        """Index documents with one Elasticsearch bulk request."""

        docs = list(documents)
        if not docs:
            return 0

        # Preserve deterministic in-memory demo behavior.
        if not self.url:
            for document in docs:
                self._store.setdefault(document.index, {})[document.doc_id] = document
            return len(docs)

        # Ensure each index once instead of once per document.
        for index_name in sorted({document.index for document in docs}):
            self._ensure_index(index_name)

        import json

        lines: list[str] = []
        for document in docs:
            lines.append(
                json.dumps(
                    {
                        "index": {
                            "_index": document.index,
                            "_id": document.doc_id,
                        }
                    }
                )
            )
            lines.append(json.dumps(document.body, default=str))

        payload = "\n".join(lines) + "\n"

        headers = self._headers()
        headers["Content-Type"] = "application/x-ndjson"

        try:
            response = httpx.post(
                f"{self.url}/_bulk",
                headers=headers,
                content=payload,
                params={"refresh": "wait_for"},
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ElasticIntegrationError(
                "Elasticsearch bulk index request failed."
            ) from exc

        if result.get("errors"):
            failures = [
                item
                for item in result.get("items", [])
                if next(iter(item.values())).get("error")
            ]
            raise ElasticIntegrationError(
                f"Elasticsearch bulk index had {len(failures)} failed item(s)."
            )

        return len(docs)

    def get(self, index: str, source_id: UUID) -> IndexDocument | None:
        """Retrieve a canonical search document by source UUID."""

        if not self.url:
            return self._store.get(index, {}).get(str(source_id))

        result = self._request(
            "GET",
            f"/{index}/_doc/{source_id}",
            allow_404=True,
        )

        if result is None:
            return None

        return self._document_from_hit(
            {
                "_index": result["_index"],
                "_id": result["_id"],
                "_source": result["_source"],
            }
        )

    def search(
        self,
        query: str,
        *,
        index: str | None = None,
    ) -> tuple[IndexDocument, ...]:
        """Search canonical Mira documents while preserving source IDs."""

        if not self.url:
            needle = query.lower()
            hits: list[IndexDocument] = []
            indices = [index] if index else list(self._store)

            for name in indices:
                for document in self._store.get(name, {}).values():
                    blob = (
                        f"{document.body.get('title', '')} "
                        f"{document.body.get('body', '')} "
                        f"{document.source_id}"
                    )

                    if needle in blob.lower():
                        hits.append(document)

            return tuple(hits)

        if index:
            search_path = f"/{index}/_search"
        else:
            search_path = f"/{','.join(ALL_INDICES)}/_search"

        result = self._request(
            "POST",
            search_path,
            json_body={
                "size": 50,
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "title^2",
                            "body",
                            "source_id",
                            "source_type",
                        ],
                    }
                },
            },
            params={"ignore_unavailable": "true"},
        )

        if result is None:
            return ()

        raw_hits = result.get("hits", {}).get("hits", [])

        return tuple(
            self._document_from_hit(hit)
            for hit in raw_hits
            if isinstance(hit, dict) and "_source" in hit
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"

        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        allow_404: bool = False,
    ) -> dict[str, Any] | None:
        if not self.url:
            raise ElasticIntegrationError(
                "Elasticsearch credentials are not configured."
            )

        try:
            response = httpx.request(
                method,
                f"{self.url}{path}",
                headers=self._headers(),
                json=json_body,
                params=params,
                timeout=self.timeout,
            )

            if allow_404 and response.status_code == 404:
                return None

            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ElasticIntegrationError(
                f"Elasticsearch request failed: {method} {path}"
            ) from exc

        if not isinstance(result, dict):
            raise ElasticIntegrationError(
                "Elasticsearch returned an unexpected response."
            )

        return result

    def _ensure_index(self, index: str) -> None:
        if index in self._ensured_indices:
            return

        if index not in INDEX_MAPPINGS:
            raise ElasticIntegrationError(
                f"Unknown Mira Elasticsearch index: {index}"
            )

        existing = self._request(
            "GET",
            f"/{index}",
            allow_404=True,
        )

        if existing is None:
            self._request(
                "PUT",
                f"/{index}",
                json_body=INDEX_MAPPINGS[index],
            )

        self._ensured_indices.add(index)

    @staticmethod
    def _document_from_hit(hit: dict[str, Any]) -> IndexDocument:
        source = hit["_source"]

        return IndexDocument(
            index=hit["_index"],
            doc_id=hit["_id"],
            source_id=UUID(str(source["source_id"])),
            source_type=str(source["source_type"]),
            company_id=UUID(str(source["company_id"])),
            body=source,
        )

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
