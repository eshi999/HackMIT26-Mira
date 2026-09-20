from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from mira.context.encoding import SourceEncodingCache, encode, estimate_tokens
from mira.context.models import ContextItem, ContextPacket, ContextRequest, ExcludedItem, Profile
from mira.context.profiles import ALL_CATEGORIES, PROFILES
from mira.context.retrieval import rank_sources
from mira.context.routing import route
from mira.context.telemetry import usage
from mira.context.truth import deterministic_truth
from mira.finance.snapshot import FinanceSnapshot
from mira.integrations.elastic import ElasticAdapter


def _source_id(row: dict) -> str:
    # Metrics/forecasts have no UUID in the snapshot: label a content reference,
    # never misrepresent it as an evidence ID.
    return str(row.get("id") or "content:" + hashlib.sha256(encode(row).encode()).hexdigest())


def _references(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_references(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_references(v) for v in value))
    return {value} if isinstance(value, str) else set()


def _selection(
    snapshot: FinanceSnapshot, request: ContextRequest, truth: dict
) -> tuple[dict[str, set[str]], list[str]]:
    """Explicit object links and periods, never similarity as proof of relevance."""
    profile = request.profile
    selected: dict[str, set[str]] = {key: set() for key in ALL_CATEGORIES}
    unknowns = [
        "Document text is not present in FinanceSnapshot; document records contain metadata only."
    ]
    invoice = snapshot.invoice(request.subject_id) if request.subject_id else None
    vendor_id = request.vendor_id or (invoice.vendor_id if invoice else None)
    if profile == Profile.CFO_VARIANCE_INVESTIGATION:
        vendor = next((v for v in snapshot.vendors if v.name == truth["aws_spend"]["vendor"]), None)
        vendor_id = vendor.id if vendor else None
        if vendor is None:
            unknowns.append(
                "AWS vendor is missing; zero ledger totals do not establish zero economic spend."
            )

    def add(category: str, rows: Any) -> None:
        selected[category].update(_source_id(row.model_dump(mode="json")) for row in rows)

    # Policies remain conservative: all active policies, not guessed applicability.
    add("policies", snapshot.active_policies())
    if profile == Profile.AP_INVOICE_REVIEW:
        add("invoices", [invoice])
        duplicate_ids = truth["match"].get("duplicate_invoice_ids", [])
        add("invoices", [v for v in snapshot.invoices if str(v.id) in duplicate_ids])
        po = snapshot.purchase_order(invoice.purchase_order_id)
        if po:
            add("purchase_orders", [po])
            add("receipts", snapshot.receipts_for_po(po.id))
            if not snapshot.receipts_for_po(po.id):
                unknowns.append("No goods receipt linked to the invoice purchase order.")
        else:
            unknowns.append("No canonical purchase order linked to the invoice.")
        if not invoice.document_id or not any(
            d.id == invoice.document_id for d in snapshot.documents
        ):
            unknowns.append("Invoice source document is missing from the snapshot.")
    elif profile == Profile.CFO_VARIANCE_INVESTIGATION:
        periods = {truth["aws_spend"]["period"], truth["aws_spend"]["prior_period"]}
        add(
            "invoices",
            [
                v
                for v in snapshot.ap_invoices()
                if v.vendor_id == vendor_id
                and (v.posted_period or v.issue_date.strftime("%Y-%m")) in periods
            ],
        )
        for period in sorted(periods):
            if period not in truth["aws_spend"]["invoices_by_period"]:
                unknowns.append(f"No AWS ledger invoices for {period}; completeness is unknown.")
    elif profile == Profile.TREASURY_RECONCILIATION:
        # Existing reconciliation is snapshot-wide, not period-filtered. Retain
        # its complete inputs; never imply a narrowed report was calculated.
        add("transactions", snapshot.transactions)
        add("payments", snapshot.payments)
        add("invoices", snapshot.invoices)
    elif profile == Profile.AUDIT_REVIEW:
        for key in (
            "evidence",
            "documents",
            "precedents",
            "invoices",
            "transactions",
            "payments",
            "contracts",
            "vendors",
        ):
            add(key, getattr(snapshot, key))
    elif profile in {Profile.FPNA_SCENARIO, Profile.EXECUTIVE_QUESTION}:
        add("metrics", snapshot.metrics)
        add("forecasts", snapshot.forecasts)
        add("employees", snapshot.employees)
        add(
            "invoices",
            [
                v
                for v in snapshot.invoices
                if not request.customer_id or v.customer_id == request.customer_id
            ],
        )
        add(
            "savings",
            [v for v in snapshot.savings if not request.period or v.period == request.period],
        )

    if vendor_id:
        add("vendors", [v for v in snapshot.vendors if v.id == vendor_id])
        add("contracts", [v for v in snapshot.contracts if v.vendor_id == vendor_id])
    if request.customer_id:
        add("customers", [v for v in snapshot.customers if v.id == request.customer_id])
        unknowns.append(
            "Customer filter scopes retrieved records only; deterministic cash, AR aging and risk reports remain company-wide."
        )
    linked = set().union(*selected.values()) | {
        str(value)
        for value in (request.subject_id, vendor_id, request.customer_id)
        if value is not None
    }
    add(
        "documents",
        [
            v
            for v in snapshot.documents
            if any(
                str(i.id) in selected["invoices"] and i.document_id == v.id
                for i in snapshot.invoices
            )
        ],
    )
    uris = {v.storage_uri for v in snapshot.documents if str(v.id) in selected["documents"]}
    # Required engine evidence IDs always survive. AP risk includes a company
    # report; only pull raw evidence for incidents explicitly linked to this invoice.
    reference_truth = truth
    if profile == Profile.AP_INVOICE_REVIEW:
        reference_truth = {k: v for k, v in truth.items() if k != "risk"}
        reference_truth["subject_incidents"] = [
            i
            for i in truth["risk"]["result"]["incidents"]
            if str(invoice.id) in _references(i.get("related_objects", []))
        ]
    refs = _references(reference_truth)
    add(
        "evidence", [v for v in snapshot.evidence if str(v.id) in refs or (v.uri and v.uri in uris)]
    )
    add("documents", [v for v in snapshot.documents if str(v.id) in refs])
    add(
        "precedents",
        [
            v
            for v in snapshot.active_precedents()
            if str(v.id) in refs
            or (vendor_id is not None and str(v.conditions.get("vendor_id", "")) == str(vendor_id))
            or (
                request.subject_id is not None
                and str(v.conditions.get("subject_id", "")) == str(request.subject_id)
            )
        ],
    )
    if (
        profile in {Profile.AP_INVOICE_REVIEW, Profile.CFO_VARIANCE_INVESTIGATION}
        and not selected["precedents"]
    ):
        unknowns.append(
            "No active precedent linked by engine result or explicit subject/vendor conditions."
        )
    for category in ("approvals", "decisions"):
        rows = getattr(snapshot, category)
        add(
            category,
            [
                v
                for v in rows
                if profile
                in {
                    Profile.AUDIT_REVIEW,
                    Profile.EXECUTIVE_QUESTION,
                    Profile.FPNA_SCENARIO,
                    Profile.TREASURY_RECONCILIATION,
                }
                or str(v.subject_id) in linked
            ],
        )
    for category in ("factual_memories", "historical_memories"):
        add(
            category,
            [
                v
                for v in getattr(snapshot, category)
                if v.status == "active"
                and str(v.subject_id) in linked
                and (
                    not request.period
                    or category != "historical_memories"
                    or v.period_start <= request.period <= v.period_end
                )
            ],
        )
    if request.period and profile in {Profile.TREASURY_RECONCILIATION, Profile.AUDIT_REVIEW}:
        unknowns.append(
            "Reconciliation engine covers the complete supplied snapshot, not a period-filtered ledger."
        )
    if profile == Profile.EXECUTIVE_QUESTION:
        unknowns.append(
            "Executive packet supports cash, AR aging and risk; other questions require additional tools."
        )
    return selected, unknowns


def prepare_context(
    snapshot: FinanceSnapshot,
    request: ContextRequest,
    *,
    cache: SourceEncodingCache | None = None,
    adapter: ElasticAdapter | None = None,
    offline: bool = False,
) -> ContextPacket:
    mode = request.mode or os.getenv("CONTEXT_OPTIMIZATION", "off").lower()
    if mode not in {"off", "on"}:
        raise ValueError("CONTEXT_OPTIMIZATION must be off or on")
    truth = deterministic_truth(snapshot, request)
    selected, unknowns = _selection(snapshot, request, truth)
    profile = PROFILES[request.profile]
    candidates: list[ContextItem] = []
    excluded: list[ExcludedItem] = []
    for category in sorted(ALL_CATEGORIES):
        for model in getattr(snapshot, category):
            facts = model.model_dump(mode="json")
            source_id = _source_id(facts)
            key = f"{category}:{source_id}"
            scoped = source_id in selected[category]
            required = scoped and category in profile.required
            if mode == "on" and (category in profile.irrelevant or not scoped):
                excluded.append(
                    ExcludedItem(
                        key=key,
                        reason="irrelevant" if category in profile.irrelevant else "out_of_scope",
                    )
                )
                continue
            # Cache only immutable serialized source representations, never outcomes,
            # approvals, decisions, metrics, or any deterministic engine output.
            if cache is not None and category in {"documents", "evidence", "policies"}:
                facts = json.loads(
                    cache.serialize(
                        company_id=request.company_id,
                        task_id=request.task_id,
                        profile=request.profile,
                        source_id=key,
                        revision=str(facts.get("version", "content")),
                        value=facts,
                    )
                )
            candidates.append(
                ContextItem(
                    key=key, category=category, source_id=source_id, required=required, facts=facts
                )
            )
    candidates.sort(key=lambda item: item.key)
    ranked, retrieval_source = (
        rank_sources(
            snapshot,
            request.query,
            {v.source_id for v in candidates},
            adapter=adapter,
            offline=offline,
        )
        if mode == "on"
        else (set(), "baseline_snapshot")
    )
    required = [v for v in candidates if v.required]
    optional = sorted(
        (v for v in candidates if not v.required), key=lambda v: (v.source_id not in ranked, v.key)
    )

    def pack(items: list[ContextItem]) -> str:
        return encode(
            {
                "company_id": request.company_id,
                "task_id": request.task_id,
                "profile": request.profile,
                "as_of": snapshot.as_of,
                "period": request.period,
                "deterministic_results": truth,
                "known_unknowns": unknowns,
                "items": [v.model_dump(mode="json") for v in items],
            }
        )

    mandatory_tokens = estimate_tokens(pack(required))
    included = required.copy()
    for item in optional:
        if mode == "off" or estimate_tokens(pack([*included, item])) <= request.target_tokens:
            included.append(item)
        else:
            excluded.append(ExcludedItem(key=item.key, reason="budget"))
    text = pack(included)
    telemetry = usage(
        request, text, len(included), enabled=mode == "on", model=route(request.profile).model
    )
    return ContextPacket(
        request=request,
        mode=mode,
        deterministic_results=truth,
        items=tuple(included),
        known_unknowns=tuple(unknowns),
        excluded=tuple(excluded),
        model_context=text,
        context_bytes=len(text.encode("utf-8")),
        estimated_input_tokens=estimate_tokens(text),
        mandatory_tokens=mandatory_tokens,
        mandatory_over_budget=mandatory_tokens > request.target_tokens,
        retrieval_source=retrieval_source,
        telemetry=telemetry,
    )
