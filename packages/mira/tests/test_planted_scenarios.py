"""Exact expected outcomes for every planted Northstar scenario."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from mira.core.enums import FindingType, MatchStatus, RecommendedAction, ReconStage
from mira.core.models import Invoice, Transaction
from mira.evaluation.metrics import compute_metrics
from mira.finance.contracts import compare_invoice_to_contract, facts_from_extracted
from mira.finance.snapshot import load_snapshot
from mira.integrations.elastic import ElasticAdapter
from mira.policies.engine import (
    POL_APPR_NO_SELF,
    POL_SPEND_CFO_10K,
    evaluate_invoice,
    evaluate_purchase_order,
)
from mira.reconciliation.engine import reconcile
from mira.reconciliation.three_way import match_invoice
from mira.risk.engine import run_risk_engine
from mira.seed import ids
from mira.seed.expected import PLANTED_SCENARIOS, SCENARIO_BY_KEY


def _snapshot(session, as_of):
    return load_snapshot(session, ids.COMPANY, as_of)


def _findings_for(result, finding_type: FindingType):
    return [f for f in result.findings if f.finding_type == finding_type]


def _finding_with_invoices(result, finding_type: FindingType, numbers: tuple[str, ...]):
    wanted = set(numbers)
    for finding in _findings_for(result, finding_type):
        labels = {rel.label for rel in finding.related_objects if rel.label}
        facts_numbers = set(finding.facts.get("invoice_numbers", []))
        if wanted <= labels or wanted <= facts_numbers or wanted & labels or wanted & facts_numbers:
            return finding
        if any(num in finding.title or num in finding.description for num in numbers):
            return finding
    raise AssertionError(f"no {finding_type} finding covering {numbers}")


def test_seed_volume_thresholds(seeded_session) -> None:
    invoices = seeded_session.scalars(select(Invoice)).all()
    txns = seeded_session.scalars(select(Transaction)).all()
    ap = [i for i in invoices if i.direction == "ap"]
    assert len(txns) >= 100
    assert len(ap) >= 30
    assert len([i for i in invoices if i.direction == "ar"]) >= 1


def test_scenario_duplicate_4850(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["duplicate_4850"]
    result = run_risk_engine(_snapshot(seeded_session, as_of))
    finding = _finding_with_invoices(result, FindingType.DUPLICATE_INVOICE, expected.invoice_numbers)
    assert finding.risk_contribution == expected.risk_score
    assert finding.confidence.score == expected.confidence_score
    assert finding.facts["amount"] == "4850.00"
    incident = next(i for i in result.incidents if finding in i.findings)
    assert incident.recommended_action == expected.recommended_action
    assert incident.risk_score == expected.risk_score
    assert incident.confidence.score == expected.confidence_score
    assert incident.risk_score != incident.confidence.score
    assert "Risk " in incident.explanation
    assert "Confidence " in incident.explanation
    assert expected.recommended_action.value in incident.explanation


def test_scenario_invoice_exceeds_po(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["invoice_exceeds_po"]
    snapshot = _snapshot(seeded_session, as_of)
    result = run_risk_engine(snapshot)
    finding = _finding_with_invoices(result, FindingType.INVOICE_PO_MISMATCH, expected.invoice_numbers)
    assert finding.facts["invoice_total"] == "12500.00"
    assert finding.facts["po_total"] == "10000.00"
    assert finding.risk_contribution == expected.risk_score
    assert finding.confidence.score == expected.confidence_score
    matched = match_invoice(snapshot, ids.INV_EXCEED)
    assert matched.status == MatchStatus.MISMATCH
    assert matched.confidence.score == Decimal("0.99")


def test_scenario_self_approved(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["self_approved"]
    snapshot = _snapshot(seeded_session, as_of)
    result = run_risk_engine(snapshot)
    finding = next(f for f in result.findings if f.finding_type == FindingType.SELF_APPROVED_REQUEST)
    assert finding.risk_contribution == expected.risk_score
    assert finding.confidence.score == expected.confidence_score
    assert finding.facts["requested_by_user_id"] == str(ids.SAM)
    assert finding.facts["approver_user_id"] == str(ids.SAM)
    policy = evaluate_purchase_order(snapshot, ids.PO_SELF)
    assert policy is not None
    assert POL_APPR_NO_SELF in policy.violated_policy_ids
    incident = next(i for i in result.incidents if finding in i.findings)
    assert incident.recommended_action == RecommendedAction.REVERSE_APPROVAL


def test_scenario_ach_covers_three(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["ach_covers_three"]
    report = reconcile(_snapshot(seeded_session, as_of))
    match = next(m for m in report.matches if m.transaction_id == ids.TXN_ACH_THREE)
    assert match.stage == ReconStage.ONE_TO_MANY
    assert match.forced is False
    assert match.confidence.score == expected.confidence_score
    assert match.amount_delta == Decimal("0.00")
    numbers = set()
    snapshot = _snapshot(seeded_session, as_of)
    for cid in match.counterpart_ids:
        inv = snapshot.invoice(cid)
        assert inv is not None
        numbers.add(inv.invoice_number)
    assert numbers == set(expected.invoice_numbers)


def test_scenario_duplicated_refund(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["duplicated_refund"]
    result = run_risk_engine(_snapshot(seeded_session, as_of))
    finding = next(
        f
        for f in result.findings
        if f.finding_type == FindingType.DUPLICATE_PAYMENT and f.facts.get("kind") == "refund"
    )
    assert finding.risk_contribution == expected.risk_score
    assert finding.confidence.score == expected.confidence_score
    assert finding.facts["amount"] == "185.00"
    report = reconcile(_snapshot(seeded_session, as_of))
    refund_matches = [
        m for m in report.matches if m.transaction_id in {ids.TXN_REFUND_A, ids.TXN_REFUND_B}
    ]
    assert len(refund_matches) <= 1


def test_scenario_unexplained_12_40(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["unexplained_12_40"]
    snapshot = _snapshot(seeded_session, as_of)
    invoice = snapshot.invoice(ids.INV_FEE_GAP)
    txn = next(t for t in snapshot.transactions if t.id == ids.TXN_FEE_GAP)
    delta = (txn.amount.copy_abs() - invoice.total).copy_abs()
    assert delta == expected.unexplained_delta
    report = reconcile(snapshot)
    unresolved = next(m for m in report.unresolved if m.transaction_id == ids.TXN_FEE_GAP)
    assert unresolved.stage == ReconStage.UNRESOLVED
    assert unresolved.forced is False
    assert unresolved.confidence.score == expected.confidence_score
    assert not any(m.transaction_id == ids.TXN_FEE_GAP for m in report.matches)


def test_scenario_aws_spend_spike(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["aws_spend_spike"]
    snapshot = _snapshot(seeded_session, as_of)
    result = run_risk_engine(snapshot)
    finding = _finding_with_invoices(result, FindingType.UNUSUAL_VENDOR_AMOUNT, expected.invoice_numbers)
    assert finding.risk_contribution == expected.risk_score
    assert finding.confidence.score == expected.confidence_score
    sep = evaluate_invoice(snapshot, ids.INV_AWS_SEP)
    aug = evaluate_invoice(snapshot, ids.INV_AWS_AUG)
    assert sep is not None and POL_SPEND_CFO_10K in sep.violated_policy_ids
    assert aug is not None and POL_SPEND_CFO_10K not in aug.violated_policy_ids


def test_scenario_contract_11_vs_4(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["contract_increase_11_vs_4"]
    snapshot = _snapshot(seeded_session, as_of)
    result = run_risk_engine(snapshot)
    finding = _finding_with_invoices(result, FindingType.CONTRACT_PRICING_VIOLATION, expected.invoice_numbers)
    assert finding.facts["increase_pct"] == "11.00"
    assert Decimal(finding.facts["allowed_annual_increase_pct"]) == expected.contract_allowed_pct
    assert finding.facts["expected_price"] == "10400.00"
    assert finding.facts["actual_price"] == "11100.00"
    assert finding.risk_contribution == expected.risk_score
    assert finding.confidence.score == expected.confidence_score
    contract = next(c for c in snapshot.contracts if c.id == ids.CONTRACT_COLDCHAIN)
    comparison = compare_invoice_to_contract(
        contract_id=contract.id,
        invoice_id=ids.INV_COLDCHAIN,
        facts=facts_from_extracted(contract.extracted_terms),
        invoice_amount=__import__("mira.core.money", fromlist=["Money"]).Money(amount=Decimal("11100.00")),
        invoice_date=__import__("datetime").date(2026, 9, 1),
    )
    assert comparison.is_violation is True
    assert comparison.increase_pct == Decimal("11.00")


def test_scenario_ar_overdue_45(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["ar_overdue_45"]
    result = run_risk_engine(_snapshot(seeded_session, as_of))
    finding = _finding_with_invoices(result, FindingType.OVERDUE_RECEIVABLE, expected.invoice_numbers)
    assert finding.facts["days_overdue"] == expected.days_overdue
    assert finding.risk_contribution == expected.risk_score
    assert finding.confidence.score == expected.confidence_score


def test_scenario_unused_figma(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["unused_figma"]
    result = run_risk_engine(_snapshot(seeded_session, as_of))
    finding = next(f for f in result.findings if f.finding_type == FindingType.UNUSED_RECURRING_CHARGE)
    assert finding.facts["amount"] == "75.00"
    assert finding.risk_contribution == expected.risk_score
    assert finding.confidence.score == expected.confidence_score


def test_scenario_closed_period(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["closed_period"]
    snapshot = _snapshot(seeded_session, as_of)
    result = run_risk_engine(snapshot)
    finding = _finding_with_invoices(result, FindingType.CLOSED_PERIOD_POSTING, expected.invoice_numbers)
    assert finding.facts["posted_period"] == "2026-06"
    assert finding.risk_contribution == expected.risk_score
    policy = evaluate_invoice(snapshot, ids.INV_CLOSED)
    assert policy is not None
    assert expected.violated_policy_ids[0] in policy.violated_policy_ids


def test_scenario_missing_receipt(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["missing_receipt"]
    snapshot = _snapshot(seeded_session, as_of)
    matched = match_invoice(snapshot, ids.INV_MISSING_GR)
    assert matched.status == MatchStatus.MISSING_EVIDENCE
    assert matched.po_id == ids.PO_MISSING_GR
    assert matched.receipt_ids == ()
    assert matched.confidence.score == expected.confidence_score
    assert "not forced" in matched.explanation.lower() or "cannot" in matched.explanation.lower() or "no goods receipt" in matched.explanation.lower()


def test_scenario_new_vendor_outside_policy(seeded_session, as_of) -> None:
    expected = SCENARIO_BY_KEY["new_vendor_outside_policy"]
    snapshot = _snapshot(seeded_session, as_of)
    result = run_risk_engine(snapshot)
    finding = _finding_with_invoices(result, FindingType.NEW_VENDOR, expected.invoice_numbers)
    assert finding.risk_contribution == expected.risk_score
    assert finding.confidence.score == expected.confidence_score
    policy = evaluate_invoice(snapshot, ids.INV_QUARTZ)
    assert policy is not None
    assert set(expected.violated_policy_ids) <= set(policy.violated_policy_ids)


def test_all_numbered_scenarios_are_covered() -> None:
    assert len(PLANTED_SCENARIOS) == 13


def test_additional_detectors_on_seed(seeded_session, as_of) -> None:
    snapshot = _snapshot(seeded_session, as_of)
    result = run_risk_engine(snapshot)
    types = {f.finding_type for f in result.findings}
    assert FindingType.DUPLICATE_PAYMENT in types
    assert FindingType.MISSING_PURCHASE_ORDER in types
    assert FindingType.MISSING_SUPPORTING_DOCUMENT in types
    assert FindingType.VENDOR_BANK_DETAIL_CHANGE in types
    assert FindingType.APPROVAL_AUTHORITY_EXCEEDED in types
    assert FindingType.ABNORMAL_TRANSACTION_TIMING in types
    assert FindingType.SUSPICIOUS_ROUND_NUMBER_PAYMENT in types
    assert FindingType.PREVIOUSLY_FLAGGED_VENDOR in types
    assert FindingType.UNEXPECTED_RECURRING_SUBSCRIPTION in types
    authority = next(f for f in result.findings if f.finding_type == FindingType.APPROVAL_AUTHORITY_EXCEEDED)
    assert authority.facts["amount"] == "25000.00"
    assert authority.facts["approval_limit"] == "10000.00"
    bank = next(f for f in result.findings if f.finding_type == FindingType.VENDOR_BANK_DETAIL_CHANGE)
    assert bank.facts["previous"] == "****0099"
    assert bank.facts["current"] == "****2210"


def test_risk_and_confidence_are_not_combined(seeded_session, as_of) -> None:
    result = run_risk_engine(_snapshot(seeded_session, as_of))
    unusual = next(f for f in result.findings if f.finding_type == FindingType.UNUSUAL_VENDOR_AMOUNT)
    dup = next(
        f
        for f in result.findings
        if f.finding_type == FindingType.DUPLICATE_INVOICE and "4850" in f.title
    )
    assert unusual.risk_contribution != unusual.confidence.score
    assert dup.confidence.score > unusual.confidence.score
    assert unusual.risk_contribution != dup.risk_contribution


def test_metrics_and_elastic_projection(seeded_session, as_of) -> None:
    snapshot = _snapshot(seeded_session, as_of)
    result = run_risk_engine(snapshot)
    recon = reconcile(snapshot)
    metrics = compute_metrics(snapshot, risk=result, recon=recon)
    assert metrics.money_protected >= Decimal("18400.00")
    assert metrics.estimated_hours_saved >= Decimal("6.50")
    assert Decimal("0.00") <= metrics.reconciliation_rate <= Decimal("1.00")
    assert Decimal("0.00") <= metrics.autonomy_score <= Decimal("100.00")
    adapter = ElasticAdapter()
    docs = adapter.project_snapshot(snapshot, findings=result.findings, incidents=result.incidents)
    assert docs
    hit = adapter.get("mira-invoices", ids.INV_4850)
    assert hit is not None
    assert hit.source_id == ids.INV_4850
    assert hit.doc_id == str(ids.INV_4850)
    search = adapter.search("INV-4850")
    assert any(doc.source_id == ids.INV_4850 for doc in search)
