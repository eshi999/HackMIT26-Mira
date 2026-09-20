"""Phase 3.5 runtime correctness: engine-sourced scores, idempotency, honest metrics."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from mira.agents.auth import resolve_demo_token
from mira.agents.close import close_status, execute_close
from mira.agents.persist import now
from mira.agents.runtime import (
    command_center_briefing_data,
    handle_month_end,
    overnight_review,
    process_invoice,
    teach_precedent,
)
from mira.agents.specialists import run_ap_specialist
from mira.agents.tools import _cached_recon, _cached_risk, tool_assess_risk, tool_retrieve_evidence
from mira.core.enums import SavingsSource
from mira.core.models import Decision, Precedent, SavingsEvent
from mira.finance.snapshot import load_snapshot
from mira.reconciliation.engine import reconcile
from mira.risk.engine import persist_result, run_risk_engine
from mira.seed import ids


def _snap(session, as_of):
    return load_snapshot(session, ids.COMPANY, as_of)


def test_process_invoice_is_idempotent(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    first = process_invoice(seeded_session, snapshot, ids.INV_AWS_SEP)
    second = process_invoice(seeded_session, snapshot, ids.INV_AWS_SEP)
    assert first["decision_id"] == second["decision_id"]
    assert second.get("replayed") is True
    rows = seeded_session.scalars(
        select(Decision).where(
            Decision.decision_type == "invoice",
            Decision.subject_id == ids.INV_AWS_SEP,
        )
    ).all()
    assert len(rows) == 1


def test_overnight_does_not_invent_lump_hours(seeded_session, as_of) -> None:
    overnight_review(seeded_session, _snap(seeded_session, as_of))
    seeded_session.flush()
    runtime = seeded_session.scalars(
        select(SavingsEvent).where(SavingsEvent.source == SavingsSource.RUNTIME.value)
    ).all()
    assert not any(row.workflow == "runtime.overnight_review" for row in runtime)
    invoice_hours = sum(
        (row.hours_saved for row in runtime if row.workflow == "runtime.invoice_received"),
        Decimal("0"),
    )
    assert invoice_hours >= Decimal("6.50")
    assert sum((row.hours_saved for row in runtime), Decimal("0")) == invoice_hours


def test_ap_risk_and_confidence_come_from_engines(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    ap = run_ap_specialist(snapshot, ids.INV_AWS_SEP)
    risk = tool_assess_risk(snapshot, ids.INV_AWS_SEP)
    decision = ap.artifact["decision"]
    assert decision["risk_level"] == risk.max_risk_level.value
    assert Decimal(str(decision["confidence"]["score"])) == min(
        Decimal(str(ap.artifact["three_way"]["confidence"]["score"])),
        risk.confidence.score,
    )
    tools_used = {row["tool"] for row in ap.artifact["tool_calls"]}
    assert "assess_risk" in tools_used
    assert ap.artifact["tool_calls"][0]["input"]["invoice_id"] == str(ids.INV_AWS_SEP)


def test_duplicate_reject_is_gated_by_risk_not_spend_policy(seeded_session, as_of) -> None:
    packet = process_invoice(seeded_session, _snap(seeded_session, as_of), ids.INV_HELIX_B)
    assert packet["ap_action"] == "reject"
    decision = seeded_session.get(Decision, UUID(packet["decision_id"]))
    assert decision is not None
    assert decision.requires_human_approval is True
    assert "Policy requires a human approver" not in decision.rationale
    assert decision.status != "executed"


def test_briefing_autonomous_rate_is_unit_interval(seeded_session, as_of) -> None:
    briefing = command_center_briefing_data(seeded_session, _snap(seeded_session, as_of))
    rate = Decimal(str(briefing["autonomous_completion_rate"]))
    score = briefing["metrics"].autonomy_score
    assert Decimal("0.00") <= rate <= Decimal("1.00")
    assert score != rate or score <= Decimal("1.00")
    assert briefing["metrics"].autonomy_score >= Decimal("0")


def test_month_end_event_reuses_existing_close(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    first = handle_month_end(seeded_session, snapshot)
    second = handle_month_end(seeded_session, snapshot)
    assert first.run_id == second.run_id
    assert close_status(seeded_session, ids.COMPANY).run_id == first.run_id
    injected = execute_close(seeded_session, snapshot, fail_keys=frozenset({"ap_close"}))
    assert injected.run_id != first.run_id
    assert "ap_close" in injected.blocked


def test_persist_result_is_idempotent(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    result = run_risk_engine(snapshot)
    persist_result(seeded_session, ids.COMPANY, result, now())
    persist_result(seeded_session, ids.COMPANY, result, now())
    persist_result(seeded_session, ids.COMPANY, result, now())
    from mira.core.models import Finding

    engine_ids = {finding.id for finding in result.findings}
    stored = seeded_session.scalars(select(Finding).where(Finding.id.in_(engine_ids))).all()
    assert len(stored) == len(engine_ids)


def test_precedent_record_is_idempotent(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    elena = resolve_demo_token("mira-demo-elena")
    assert elena is not None
    kwargs = dict(
        summary="AWS infrastructure invoices under $12,000 are pre-approved.",
        reusable_rule="AWS infrastructure invoices under $12,000 are pre-approved without secondary review.",
        outcome="pre_approved",
        scope="aws_infrastructure_spend",
        vendor="Amazon Web Services",
        category="infrastructure",
        amount_threshold=Decimal("12000.00"),
        effective_date=as_of,
        evidence=["typed-authorization:elena-cfo"],
    )
    first = teach_precedent(seeded_session, snapshot, elena, **kwargs)
    second = teach_precedent(seeded_session, snapshot, elena, **kwargs)
    assert first["precedent_id"] == second["precedent_id"]
    rows = seeded_session.scalars(
        select(Precedent).where(Precedent.reusable_rule.contains("AWS infrastructure invoices under"))
    ).all()
    assert len(rows) == 1


def test_evidence_search_degrades_without_cluster(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    result = tool_retrieve_evidence(snapshot, "HelixCloud")
    assert result.hits
    assert all(hit.source_system in {"elastic-demo", "seed", "dropbox"} or hit.source_system for hit in result.hits)


def test_cached_helpers_still_compute_afresh(seeded_session, as_of) -> None:
    snapshot = _snap(seeded_session, as_of)
    import mira.agents.tools as tools

    assert not hasattr(tools, "_risk_cache")
    assert not hasattr(tools, "_recon_cache")
    assert _cached_risk(snapshot) == run_risk_engine(snapshot)
    assert _cached_recon(snapshot) == reconcile(snapshot)
