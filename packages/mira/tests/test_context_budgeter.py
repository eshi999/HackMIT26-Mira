from __future__ import annotations

import ast
import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from mira.agents.tools import collect_aws_spend_evidence, tool_evaluate_policy
from mira.context.encoding import SourceEncodingCache, encode, estimate_tokens
from mira.context.evaluation import evaluate, representative_requests, verify_pair
from mira.context.models import ContextRequest, Profile
from mira.context.profiles import ALL_CATEGORIES, PROFILES, select_profile
from mira.context.retrieval import rank_sources
from mira.context.routing import Complexity, route
from mira.context.service import prepare_context
from mira.context.telemetry import usage
from mira.finance.snapshot import (
    EvidenceView,
    FactualMemoryView,
    FinanceSnapshot,
    PrecedentView,
    load_snapshot,
)
from mira.forecasting.cash import afford_engineers
from mira.integrations.elastic import ElasticAdapter, ElasticIntegrationError
from mira.reconciliation.engine import reconcile
from mira.reconciliation.three_way import match_invoice
from mira.risk.engine import run_risk_engine
from mira.seed import ids


@pytest.fixture
def snapshot(seeded_session, as_of):
    return load_snapshot(seeded_session, ids.COMPANY, as_of)


def request(snapshot, profile=Profile.AP_INVOICE_REVIEW, **kwargs):
    fields = dict(
        company_id=snapshot.company_id,
        task_id="review",
        profile=profile,
        mode="on",
        subject_id=ids.INV_AWS_AUG if profile == Profile.AP_INVOICE_REVIEW else None,
    )
    return ContextRequest(**(fields | kwargs))


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        ("invoice_review", Profile.AP_INVOICE_REVIEW),
        ("reconciliation", Profile.TREASURY_RECONCILIATION),
        ("aws_spend", Profile.CFO_VARIANCE_INVESTIGATION),
        ("hiring_scenario", Profile.FPNA_SCENARIO),
        ("audit_review", Profile.AUDIT_REVIEW),
        ("executive_question", Profile.EXECUTIVE_QUESTION),
    ],
)
def test_profile_selection(task, expected):
    assert select_profile(task) == expected
    profile = PROFILES[expected]
    assert profile.required | profile.optional | profile.irrelevant == ALL_CATEGORIES
    assert not profile.required & profile.optional
    assert not profile.required & profile.irrelevant


def test_unknown_task_is_not_silently_routed():
    with pytest.raises(KeyError):
        select_profile("approve_payment")


def test_ap_required_evidence_and_sources(snapshot):
    packet = prepare_context(snapshot, request(snapshot), offline=True)
    invoice = snapshot.invoice(ids.INV_AWS_AUG)
    required = {item.source_id: item for item in packet.items if item.required}
    for source_id in (
        invoice.id,
        invoice.vendor_id,
        invoice.purchase_order_id,
        invoice.document_id,
    ):
        assert str(source_id) in required
        assert required[str(source_id)].facts["id"] == str(source_id)
    receipts = snapshot.receipts_for_po(invoice.purchase_order_id)
    assert receipts
    assert all(str(receipt.id) in required for receipt in receipts)
    assert str(ids.PRECEDENT_AWS) in required
    assert packet.deterministic_results["policy"] == tool_evaluate_policy(
        snapshot, subject_type="invoice", subject_id=invoice.id
    ).model_dump(mode="json")


def test_unrelated_evidence_excluded_even_if_query_matches(snapshot):
    unrelated = EvidenceView(
        id=uuid4(),
        evidence_type="document",
        source_system="test",
        title="AWS",
        snippet="Unrelated company history",
        uri="unlinked://history",
    )
    changed = snapshot.model_copy(update={"evidence": (*snapshot.evidence, unrelated)})
    packet = prepare_context(changed, request(changed, query="AWS"), offline=True)
    assert not any(v.source_id == str(unrelated.id) for v in packet.items)
    assert any(
        v.key == f"evidence:{unrelated.id}" and v.reason == "out_of_scope" for v in packet.excluded
    )
    assert "Unrelated company history" not in packet.model_context


def test_unscoped_memory_is_not_linked_by_missing_subject(snapshot):
    memory = FactualMemoryView(
        id=uuid4(),
        subject_type="company",
        subject_id=None,
        fact_key="background",
        statement="Unrelated company history",
    )
    precedent = PrecedentView(
        id=uuid4(),
        situation_hash="unlinked",
        summary="Unrelated precedent",
        outcome="approved",
        period="2026-09",
        conditions={"subject_id": None, "vendor_id": None},
    )
    changed = snapshot.model_copy(
        update={"factual_memories": (memory,), "precedents": (precedent,)}
    )
    packet = prepare_context(
        changed, request(changed, Profile.CFO_VARIANCE_INVESTIGATION), offline=True
    )
    assert "Unrelated company history" not in packet.model_context
    assert "Unrelated precedent" not in packet.model_context


def test_customer_scopes_retrieval_without_recalculating_company_totals(snapshot):
    customer = snapshot.customers[0]
    req = request(
        snapshot, Profile.EXECUTIVE_QUESTION, customer_id=customer.id, target_tokens=1000000
    )
    packet = prepare_context(snapshot, req, offline=True)
    invoices = [v for v in packet.items if v.category == "invoices"]
    assert invoices and all(v.facts["customer_id"] == str(customer.id) for v in invoices)
    assert any(v.source_id == str(customer.id) for v in packet.items)
    assert any("company-wide" in v for v in packet.known_unknowns)
    unfiltered = prepare_context(
        snapshot, request(snapshot, Profile.EXECUTIVE_QUESTION), offline=True
    )
    assert unfiltered.deterministic_results == packet.deterministic_results


@pytest.mark.parametrize(
    "scope", [{"customer_id": ids.NIH}, {"subject_id": ids.INV_AWS_AUG}, {"vendor_id": ids.AWS}]
)
def test_unsupported_scope_is_not_silently_ignored(snapshot, scope):
    with pytest.raises(ValueError):
        prepare_context(
            snapshot, request(snapshot, Profile.TREASURY_RECONCILIATION, **scope), offline=True
        )


def test_variance_scope_includes_current_and_prior_period(snapshot):
    packet = prepare_context(
        snapshot,
        request(snapshot, Profile.CFO_VARIANCE_INVESTIGATION, vendor_id=ids.AWS, period="2026-09"),
        offline=True,
    )
    invoices = {v.source_id for v in packet.items if v.category == "invoices"}
    assert invoices == {str(ids.INV_AWS_AUG), str(ids.INV_AWS_SEP)}
    # The existing tool's historical totals remain untouched even when raw
    # invoice context is scoped to the comparison period.
    assert "2026-07" in packet.deterministic_results["aws_spend"]["period_totals"]


def test_invalid_invoice_and_vendor_scope_rejected(snapshot):
    with pytest.raises(ValueError, match="canonical AP"):
        prepare_context(snapshot, request(snapshot, subject_id=uuid4()))
    with pytest.raises(ValueError, match="vendor"):
        prepare_context(snapshot, request(snapshot, vendor_id=ids.HELIX))
    with pytest.raises(ValueError, match="AWS only"):
        prepare_context(
            snapshot, request(snapshot, Profile.CFO_VARIANCE_INVESTIGATION, vendor_id=ids.HELIX)
        )


@pytest.mark.parametrize("profile", list(Profile))
def test_mandatory_truth_survives_tiny_budget(snapshot, profile):
    req = request(snapshot, profile, target_tokens=1)
    baseline = prepare_context(snapshot, req.model_copy(update={"mode": "off"}), offline=True)
    packet = prepare_context(snapshot, req, offline=True)
    assert packet.mandatory_over_budget
    assert packet.estimated_input_tokens > req.target_tokens
    assert all(v.required for v in packet.items)
    assert not packet.truncated
    verify_pair(snapshot, req, baseline, packet)


def test_exact_decimal_and_currency_preserved(snapshot):
    invoice = snapshot.invoice(ids.INV_AWS_AUG)
    precise = Decimal("11000.12345678901234567890")
    changed = snapshot.model_copy(
        update={
            "invoices": tuple(
                v.model_copy(update={"total": precise}) if v.id == invoice.id else v
                for v in snapshot.invoices
            )
        }
    )
    packet = prepare_context(changed, request(changed), offline=True)
    item = next(
        v for v in json.loads(packet.model_context)["items"] if v["source_id"] == str(invoice.id)
    )
    assert item["facts"]["total"] == str(precise)
    assert item["facts"]["currency"] == invoice.currency


def test_missing_evidence_and_known_unknowns_survive_budget(snapshot):
    changed = snapshot.model_copy(update={"documents": (), "receipts": (), "purchase_orders": ()})
    packet = prepare_context(changed, request(changed, target_tokens=1), offline=True)
    assert any("source document is missing" in v for v in packet.known_unknowns)
    assert any("purchase order" in v for v in packet.known_unknowns)
    assert list(packet.known_unknowns) == json.loads(packet.model_context)["known_unknowns"]
    assert not any(v.category == "documents" for v in packet.items)


def test_cache_reuse_content_revision_and_scope():
    cache = SourceEncodingCache(capacity=2)
    args = dict(
        company_id=ids.COMPANY,
        task_id="a",
        profile="AP",
        source_id="policy:1",
        revision="v1",
        value={"rules": {"limit": Decimal("10.00")}},
    )
    first = cache.serialize(**args)
    assert cache.serialize(**args) == first
    assert (cache.hits, cache.misses) == (1, 1)
    args["value"]["rules"]["limit"] = Decimal("20.00")
    assert cache.serialize(**args) != first
    for change in (
        {"revision": "v2"},
        {"company_id": uuid4()},
        {"task_id": "b"},
        {"profile": "AUDIT"},
    ):
        misses = cache.misses
        cache.serialize(**(args | change))
        assert cache.misses == misses + 1
    assert len(cache._entries) == 2


def test_cache_cannot_contaminate_fresh_or_alternating_snapshots(snapshot, monkeypatch):
    from mira.context import encoding, service

    monkeypatch.setattr(encoding, "id", lambda _: 7, raising=False)
    monkeypatch.setattr(service, "id", lambda _: 7, raising=False)
    cache = SourceEncodingCache()
    empty = FinanceSnapshot(company_id=snapshot.company_id, as_of=snapshot.as_of)
    for current in (empty, snapshot, empty.model_copy(deep=True), snapshot.model_copy(deep=True)):
        req = request(current, Profile.AUDIT_REVIEW)
        packet = prepare_context(current, req, cache=cache, offline=True)
        assert packet.deterministic_results["risk"]["result"] == run_risk_engine(
            current
        ).model_dump(mode="json")
        assert packet.deterministic_results["reconciliation"] == reconcile(current).model_dump(
            mode="json"
        )


def test_context_package_has_no_identity_cache():
    directory = Path(__file__).resolve().parents[1] / "context"
    for path in directory.glob("*.py"):
        tree = ast.parse(path.read_text())
        assert not any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "id"
            for node in ast.walk(tree)
        ), path


def test_company_mismatch_is_rejected(snapshot):
    with pytest.raises(ValueError, match="company"):
        prepare_context(snapshot, request(snapshot, company_id=uuid4()))


def test_cache_never_stores_decision_or_engine_output(snapshot):
    cache = SourceEncodingCache()
    packet = prepare_context(snapshot, request(snapshot), cache=cache, offline=True)
    assert packet.deterministic_results
    assert cache.misses
    assert all(
        key[3].split(":")[0] in {"documents", "evidence", "policies"} for key in cache._entries
    )
    packet.items[0].facts["injected"] = "caller mutation"
    fresh = prepare_context(snapshot, request(snapshot), cache=cache, offline=True)
    assert "caller mutation" not in fresh.model_context
    assert cache.hits


def test_policy_content_change_invalidates_cached_source_and_preserves_control(snapshot):
    cache = SourceEncodingCache()
    req = request(snapshot, target_tokens=1)
    first = prepare_context(snapshot, req, cache=cache, offline=True)
    policy = snapshot.active_policies()[0]
    changed_policy = policy.model_copy(
        update={"version": "changed", "rules": {**policy.rules, "cfo_approval_above": "1.00"}}
    )
    changed = snapshot.model_copy(
        update={
            "policies": tuple(changed_policy if p.id == policy.id else p for p in snapshot.policies)
        }
    )
    second = prepare_context(changed, req, cache=cache, offline=True)
    before = next(v for v in first.items if v.source_id == str(policy.id))
    after = next(v for v in second.items if v.source_id == str(policy.id))
    assert before.facts != after.facts
    assert after.required and after.facts["version"] == "changed"
    assert second.deterministic_results["policy"] == tool_evaluate_policy(
        changed, subject_type="invoice", subject_id=ids.INV_AWS_AUG
    ).model_dump(mode="json")


def test_elasticsearch_failure_uses_local_fallback(snapshot, monkeypatch):
    adapter = ElasticAdapter("https://unavailable.invalid")

    def unavailable(*args, **kwargs):
        raise ElasticIntegrationError("offline")

    monkeypatch.setattr(adapter, "search", unavailable)
    req = request(snapshot, Profile.CFO_VARIANCE_INVESTIGATION, query="AWS")
    packet = prepare_context(snapshot, req, adapter=adapter)
    local = prepare_context(snapshot, req, offline=True)
    assert packet.retrieval_source == "local_fallback"
    assert packet.model_context == local.model_context


def test_elasticsearch_foreign_stale_and_forged_facts_rejected(snapshot, monkeypatch):
    local = ElasticAdapter()
    docs = local.project_snapshot(snapshot)
    source = next(v for v in docs if v.source_id == ids.INV_AWS_AUG)
    adapter = ElasticAdapter("https://elastic.invalid")
    forged = source.model_copy(update={"body": {"amount": "9999999999"}})
    foreign = source.model_copy(update={"company_id": uuid4()})
    stale = source.model_copy(update={"source_id": uuid4()})
    monkeypatch.setattr(adapter, "search", lambda query: (forged, foreign, stale))
    ranked, status = rank_sources(snapshot, "AWS", {str(source.source_id)}, adapter=adapter)
    assert ranked == {str(source.source_id)}
    assert status == "elasticsearch"
    packet = prepare_context(snapshot, request(snapshot), adapter=adapter)
    assert "9999999999" not in packet.model_context


@pytest.mark.parametrize("profile", list(Profile))
def test_routing_is_configurable_and_does_not_change_truth(snapshot, profile, monkeypatch):
    req = request(snapshot, profile)
    before = prepare_context(snapshot, req, offline=True)
    tier = route(profile).tier
    monkeypatch.setenv(f"MIRA_MODEL_{tier.value}", "configured-model")
    assert route(profile).model == "configured-model"
    assert route(profile, {tier: "explicit-model"}).model == "explicit-model"
    after = prepare_context(snapshot, req, offline=True)
    assert after.model_context == before.model_context
    assert after.telemetry.model == "configured-model"


def test_all_routing_tiers_are_used():
    assert {route(p).tier for p in Profile} == set(Complexity)


@pytest.mark.parametrize(("text", "tokens"), [("", 0), ("abcd", 1), ("abcde", 2), ("ééé", 2)])
def test_offline_token_estimation(text, tokens):
    assert estimate_tokens(text) == tokens
    assert estimate_tokens(text) == tokens


def test_telemetry_distinguishes_actual_provider_usage(snapshot):
    req = request(snapshot)
    estimate = usage(req, "abcd", 1, enabled=True)
    actual = usage(req, "abcd", 1, enabled=True, provider_input_tokens=20, provider_output_tokens=8)
    assert estimate.usage_source == "estimated" and estimate.input_tokens == 1
    assert estimate.output_tokens is None
    assert actual.usage_source == "provider_reported" and actual.input_tokens == 20
    assert actual.output_tokens == 8
    assert actual.scope != estimate.scope
    with pytest.raises(ValueError):
        usage(req, "abcd", 1, enabled=True, provider_output_tokens=8)


def test_optimization_environment_switch(snapshot, monkeypatch):
    req = request(snapshot, Profile.CFO_VARIANCE_INVESTIGATION, mode=None)
    monkeypatch.setenv("CONTEXT_OPTIMIZATION", "off")
    baseline = prepare_context(snapshot, req, offline=True)
    monkeypatch.setenv("CONTEXT_OPTIMIZATION", "on")
    optimized = prepare_context(snapshot, req, offline=True)
    assert optimized.context_bytes < baseline.context_bytes
    assert optimized.deterministic_results == baseline.deterministic_results
    monkeypatch.setenv("CONTEXT_OPTIMIZATION", "invalid")
    with pytest.raises(ValueError, match="CONTEXT_OPTIMIZATION"):
        prepare_context(snapshot, req)


def test_evaluation_reproducible_offline_without_any_provider(snapshot, monkeypatch):
    import httpx

    for key in ("TOKEN_COMPANY_API_KEY", "ELASTICSEARCH_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ELASTICSEARCH_URL", "https://must-not-call.invalid")

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline evaluation attempted network access")

    monkeypatch.setattr(httpx, "request", forbidden)
    first, second = evaluate(snapshot), evaluate(snapshot.model_copy(deep=True))
    assert first == second
    assert first["correctness_retained"] and first["correctness_delta"] == 0
    assert first["cost_savings"] is None
    assert first["token_company_status"] == "disabled_not_integrated"
    assert len(first["scenarios"]) == 6
    for scenario in first["scenarios"]:
        assert scenario["optimized"]["context_bytes"] < scenario["baseline"]["context_bytes"]
        assert scenario["tokens_avoided"] > 0


@pytest.mark.parametrize("corruption", ["truth", "evidence", "unknowns"])
def test_evaluator_rejects_corrupted_serialized_context(snapshot, corruption):
    req = representative_requests(snapshot)[0]
    baseline = prepare_context(snapshot, req.model_copy(update={"mode": "off"}), offline=True)
    optimized = prepare_context(snapshot, req.model_copy(update={"mode": "on"}), offline=True)
    data = json.loads(optimized.model_context)
    if corruption == "truth":
        data["deterministic_results"] = {"invented": "0.00"}
    elif corruption == "evidence":
        data["items"] = []
    else:
        data["known_unknowns"] = []
    with pytest.raises(AssertionError):
        verify_pair(
            snapshot, req, baseline, optimized.model_copy(update={"model_context": encode(data)})
        )


def test_serialized_outputs_equal_direct_engines(snapshot):
    ap = prepare_context(snapshot, request(snapshot), offline=True).deterministic_results
    assert ap["match"] == match_invoice(snapshot, ids.INV_AWS_AUG).model_dump(mode="json")
    assert ap["risk"]["result"] == run_risk_engine(snapshot).model_dump(mode="json")
    fpna = prepare_context(
        snapshot, request(snapshot, Profile.FPNA_SCENARIO, headcount=3), offline=True
    )
    assert fpna.deterministic_results["forecast"] == afford_engineers(
        snapshot, headcount=3
    ).model_dump(mode="json")
    variance = prepare_context(
        snapshot,
        request(snapshot, Profile.CFO_VARIANCE_INVESTIGATION, period="2026-09"),
        offline=True,
    )
    assert variance.deterministic_results["aws_spend"] == collect_aws_spend_evidence(
        snapshot, "2026-09"
    )
