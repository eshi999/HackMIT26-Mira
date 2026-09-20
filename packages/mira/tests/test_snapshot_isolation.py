"""Financial tools must use the supplied snapshot, independent of object identity."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from mira.agents import runtime, tools
from mira.core.models import Decision
from mira.evaluation.metrics import compute_metrics
from mira.finance.snapshot import FinanceSnapshot, load_snapshot
from mira.reconciliation.engine import reconcile
from mira.risk.engine import run_risk_engine
from mira.seed import ids


@pytest.fixture(autouse=True)
def reused_snapshot_identity(monkeypatch):
    # Reproduce allocator ID reuse deterministically, without relying on GC timing.
    # Patch only this module's lookup, not Python's built-in id globally.
    identity = uuid4().int
    monkeypatch.setattr(tools, "id", lambda snapshot: identity, raising=False)


@pytest.fixture
def snapshots(seeded_session, as_of):
    populated = load_snapshot(seeded_session, ids.COMPANY, as_of)
    empty = FinanceSnapshot(company_id=ids.COMPANY, as_of=as_of)
    return empty, populated


def test_fresh_snapshots_do_not_share_risk(snapshots):
    empty, populated = snapshots
    assert empty is not populated
    assert not tools.tool_assess_risk(empty).result.findings
    expected = run_risk_engine(populated)
    assert expected.findings
    assert tools.tool_assess_risk(populated).result == expected


def test_fresh_snapshots_do_not_share_reconciliation(snapshots):
    empty, populated = snapshots
    assert empty is not populated
    assert not tools.tool_reconcile_period(empty).matches
    expected = reconcile(populated)
    assert expected.matches
    assert tools.tool_reconcile_period(populated) == expected


@pytest.mark.parametrize("engine", ["risk", "reconciliation"])
def test_alternating_fresh_snapshots_agree_with_direct_engine(snapshots, engine):
    empty, populated = snapshots
    for source in (populated, empty, populated, empty, populated):
        snapshot = source.model_copy()
        assert snapshot is not source
        if engine == "risk":
            assert tools.tool_assess_risk(snapshot).result == run_risk_engine(snapshot)
        else:
            assert tools.tool_reconcile_period(snapshot) == reconcile(snapshot)


def test_finance_metrics_use_current_snapshot_engine_results(snapshots):
    empty, populated = snapshots
    for source in (empty, populated, empty, populated):
        snapshot = source.model_copy()
        expected = compute_metrics(
            snapshot, risk=run_risk_engine(snapshot), recon=reconcile(snapshot)
        )
        assert tools.tool_calculate_finance_metrics(snapshot) == expected


def _repeated_invoice_and_briefing_outputs(session, as_of):
    outputs = []
    for invoice_id in (ids.INV_AWS_SEP, ids.INV_MISSING_GR, ids.INV_AWS_SEP):
        packet = runtime.process_invoice(
            session, load_snapshot(session, ids.COMPANY, as_of), invoice_id
        )
        decision = session.get(Decision, UUID(packet["decision_id"]))
        briefing = runtime.command_center_briefing_data(
            session, load_snapshot(session, ids.COMPANY, as_of)
        )
        # Exclude generated run/decision UUIDs and timestamps; compare finance truth.
        outputs.append(
            {
                "decision": decision.structured_output,
                "decision_status": decision.status,
                "briefing": {
                    key: value
                    for key, value in briefing.items()
                    if key not in {"close", "pending_decisions"}
                },
            }
        )
    return outputs


def test_repeated_workflows_agree_with_direct_engines_despite_reused_identity(
    seeded_session, as_of, monkeypatch
):
    # Build an uncached oracle from the same database state, then roll back its writes.
    with monkeypatch.context() as direct:
        direct.setattr(tools, "_cached_risk", run_risk_engine)
        direct.setattr(tools, "_cached_recon", reconcile)
        direct.setattr(runtime, "_cached_risk", run_risk_engine)
        savepoint = seeded_session.begin_nested()
        try:
            expected = _repeated_invoice_and_briefing_outputs(seeded_session, as_of)
        finally:
            savepoint.rollback()
            seeded_session.expire_all()

    # An earlier, unrelated snapshot must not influence any subsequent workflow.
    empty = FinanceSnapshot(company_id=ids.COMPANY, as_of=as_of)
    tools.tool_assess_risk(empty)
    tools.tool_reconcile_period(empty)
    actual = _repeated_invoice_and_briefing_outputs(seeded_session, as_of)
    assert actual == expected
