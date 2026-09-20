"""Paired, offline context evaluation on identical canonical snapshots."""

from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mira.context.encoding import encode
from mira.context.models import ContextPacket, ContextRequest, Profile
from mira.context.service import prepare_context
from mira.context.truth import deterministic_truth
from mira.core.models import Base
from mira.finance.snapshot import FinanceSnapshot, load_snapshot
from mira.seed import ids
from mira.seed.northstar import AS_OF, seed_northstar


def representative_requests(snapshot: FinanceSnapshot) -> tuple[ContextRequest, ...]:
    invoice = next((i for i in snapshot.ap_invoices() if i.id == ids.INV_HELIX_A), None)
    if invoice is None:
        invoice = next(iter(snapshot.ap_invoices()), None)
    if invoice is None:
        raise ValueError("Evaluation requires a canonical AP invoice")
    return tuple(
        ContextRequest(
            company_id=snapshot.company_id,
            task_id=f"token-eval:{profile.value}",
            profile=profile,
            period="2026-09",
            query=query,
            subject_id=invoice.id if profile == Profile.AP_INVOICE_REVIEW else None,
        )
        for profile, query in (
            (Profile.AP_INVOICE_REVIEW, invoice.invoice_number),
            (Profile.CFO_VARIANCE_INVESTIGATION, "AWS"),
            (Profile.TREASURY_RECONCILIATION, "bank"),
            (Profile.FPNA_SCENARIO, "hiring"),
            (Profile.AUDIT_REVIEW, "audit"),
            (Profile.EXECUTIVE_QUESTION, "cash"),
        )
    )


def verify_pair(
    snapshot: FinanceSnapshot,
    request: ContextRequest,
    baseline: ContextPacket,
    optimized: ContextPacket,
) -> None:
    """Check the actual serialized model input, not just adjacent result metadata."""
    oracle = deterministic_truth(snapshot, request)
    left, right = json.loads(baseline.model_context), json.loads(optimized.model_context)
    for packet, parsed in ((baseline, left), (optimized, right)):
        if parsed["deterministic_results"] != oracle or packet.deterministic_results != oracle:
            raise AssertionError(f"Financial truth changed: {request.profile}")
        if parsed["company_id"] != str(request.company_id) or parsed["task_id"] != request.task_id:
            raise AssertionError("Context scope changed")
    mandatory = {v["key"]: v for v in left["items"] if v["required"]}
    retained = {v["key"]: v for v in right["items"]}
    if any(retained.get(key) != item for key, item in mandatory.items()):
        raise AssertionError("Required evidence/control facts changed")
    if left["known_unknowns"] != right["known_unknowns"]:
        raise AssertionError("Known unknowns changed")


def _measured(packet: ContextPacket) -> dict:
    return {
        "context_items": len(packet.items),
        "context_bytes": packet.context_bytes,
        "estimated_input_tokens": packet.estimated_input_tokens,
        "correctness": True,
        "mandatory_over_budget": packet.mandatory_over_budget,
    }


def evaluate(snapshot: FinanceSnapshot) -> dict:
    before = encode(snapshot)
    rows = []
    for request in representative_requests(snapshot):
        baseline = prepare_context(
            snapshot, request.model_copy(update={"mode": "off"}), offline=True
        )
        optimized = prepare_context(
            snapshot, request.model_copy(update={"mode": "on"}), offline=True
        )
        verify_pair(snapshot, request, baseline, optimized)
        avoided = baseline.estimated_input_tokens - optimized.estimated_input_tokens
        rows.append(
            {
                "profile": request.profile.value,
                "baseline": _measured(baseline),
                "optimized": _measured(optimized),
                "tokens_avoided": avoided,
                "reduction_percent": str(
                    (Decimal(avoided) * 100 / baseline.estimated_input_tokens).quantize(
                        Decimal("0.01")
                    )
                ),
                "correctness_delta": 0,
            }
        )
    if encode(snapshot) != before:
        raise AssertionError("Evaluation mutated canonical financial data")
    totals = {
        mode: {
            key: sum(row[mode][key] for row in rows)
            for key in ("context_items", "context_bytes", "estimated_input_tokens")
        }
        for mode in ("baseline", "optimized")
    }
    avoided = (
        totals["baseline"]["estimated_input_tokens"] - totals["optimized"]["estimated_input_tokens"]
    )
    return {
        "evaluation": "paired_context_packets",
        "company_id": str(snapshot.company_id),
        "as_of": str(snapshot.as_of),
        "baseline_definition": "Full structured snapshot plus task deterministic outputs",
        "usage_source": "estimated",
        "estimator": "ceil(UTF-8 bytes / 4)",
        "scenarios": rows,
        **totals,
        "tokens_avoided": avoided,
        "reduction_percent": str(
            (Decimal(avoided) * 100 / totals["baseline"]["estimated_input_tokens"]).quantize(
                Decimal("0.01")
            )
        ),
        "correctness_retained": True,
        "correctness_delta": 0,
        "cost_savings": None,
        "pricing_status": "not_configured",
        "openai_status": "not_used_offline_evaluation",
        "elasticsearch_status": "local_fallback",
        "token_company_status": "disabled_not_integrated",
    }


def main() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            company = seed_northstar(session)
            session.flush()
            snapshot = load_snapshot(session, company.id, AS_OF.date())
            print(json.dumps(evaluate(snapshot), indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
