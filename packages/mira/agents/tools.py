"""Deterministic tools Mira and specialists may call.

Every function returns a typed object. None of these functions ask an LLM
for an amount, score, match, or policy outcome.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from mira.core.agent_outputs import Confidence, EvidenceReference, ScenarioAnalysis
from mira.core.enums import MatchStatus, RiskLevel
from mira.core.money import Money, quantize_money
from mira.evaluation.metrics import FinanceMetrics, autonomy_score, compute_metrics
from mira.finance.aging import ar_overdue
from mira.finance.cash import CashPositionResult, get_cash_position
from mira.finance.contracts import compare_invoice_to_contract, facts_from_extracted
from mira.finance.snapshot import FinanceSnapshot
from mira.forecasting.cash import afford_engineers
from mira.integrations.elastic import ElasticAdapter
from mira.integrations.public_data import PublicDataAdapter, PublicDataObservation
from mira.policies.engine import evaluate_invoice, evaluate_subject
from mira.policies.types import PolicyEvaluation, PolicySubject
from mira.reconciliation.engine import reconcile
from mira.reconciliation.three_way import match_invoice
from mira.reconciliation.types import ReconciliationReport, ThreeWayMatchResult
from mira.risk.engine import run_risk_engine
from mira.risk.types import RiskEngineResult

_risk_cache: dict[int, RiskEngineResult] = {}
_recon_cache: dict[int, ReconciliationReport] = {}


def _cached_risk(snapshot: FinanceSnapshot) -> RiskEngineResult:
    key = id(snapshot)
    if key not in _risk_cache:
        _risk_cache[key] = run_risk_engine(snapshot)
    return _risk_cache[key]


def _cached_recon(snapshot: FinanceSnapshot) -> ReconciliationReport:
    key = id(snapshot)
    if key not in _recon_cache:
        _recon_cache[key] = reconcile(snapshot)
    return _recon_cache[key]

TOOL_NAMES = (
    "evaluate_invoice",
    "three_way_match",
    "detect_duplicates",
    "evaluate_policy",
    "assess_risk",
    "reconcile_transaction",
    "reconcile_period",
    "get_cash_position",
    "get_ar_aging",
    "evaluate_contract",
    "get_company_context",
    "retrieve_evidence",
    "calculate_finance_metrics",
    "calculate_autonomy_score",
    "obtain_public_signal",
)


class DuplicateDetection(BaseModel):
    model_config = ConfigDict(frozen=True)

    invoice_id: UUID
    duplicate_invoice_ids: tuple[UUID, ...]
    is_duplicate: bool
    confidence: Confidence
    evidence: list[EvidenceReference] = Field(default_factory=list)
    explanation: str


class PolicyToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    evaluation: PolicyEvaluation
    explanation: str


class RiskToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject_type: str
    subject_id: UUID | None
    result: RiskEngineResult
    subject_finding_types: tuple[str, ...]
    max_risk_level: RiskLevel
    confidence: Confidence
    explanation: str


class ReconTransactionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    transaction_id: UUID
    matched: bool
    stage: str | None
    counterpart_ids: tuple[UUID, ...] = ()
    amount_delta: Decimal | None = None
    forced: bool = False
    confidence: Confidence
    explanation: str


class AgingBucket(BaseModel):
    model_config = ConfigDict(frozen=True)

    invoice_id: UUID
    invoice_number: str
    customer_id: UUID | None
    total: Decimal
    days_overdue: int
    status: str


class ARAgingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    as_of: str
    overdue: tuple[AgingBucket, ...]
    overdue_total: Money
    confidence: Confidence
    explanation: str


class CompanyContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    as_of: str
    cash: Money
    open_ap: Money
    vendor_count: int
    open_ap_invoices: int
    factual_memory: tuple[str, ...]
    historical_memory: tuple[str, ...]
    active_precedents: tuple[str, ...]
    policies: tuple[str, ...]
    explanation: str


class EvidenceHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    object_type: str
    object_id: UUID | None
    title: str
    snippet: str | None = None
    source_system: str


class EvidenceSearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    hits: tuple[EvidenceHit, ...]
    explanation: str


class AutonomyScoreResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    autonomy_score: Decimal
    inputs: dict[str, str]
    explanation: str


class PublicSignalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    observation: PublicDataObservation
    explanation: str


def _risk_level_from_result(result: RiskEngineResult, subject_id: UUID | None) -> RiskLevel:
    incidents = result.incidents
    if subject_id is not None:
        incidents = tuple(
            inc
            for inc in result.incidents
            if any(rel.object_id == subject_id for rel in inc.related_objects)
        )
    if not incidents:
        return RiskLevel.LOW
    order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}
    return max((inc.risk_level for inc in incidents), key=lambda lvl: order[lvl])


def tool_evaluate_invoice(snapshot: FinanceSnapshot, invoice_id: UUID) -> ThreeWayMatchResult:
    return match_invoice(snapshot, invoice_id)


def tool_three_way_match(snapshot: FinanceSnapshot, invoice_id: UUID) -> ThreeWayMatchResult:
    return match_invoice(snapshot, invoice_id)


def tool_detect_duplicates(snapshot: FinanceSnapshot, invoice_id: UUID) -> DuplicateDetection:
    matched = match_invoice(snapshot, invoice_id)
    invoice = snapshot.invoice(invoice_id)
    return DuplicateDetection(
        invoice_id=invoice_id,
        duplicate_invoice_ids=matched.duplicate_invoice_ids,
        is_duplicate=bool(matched.duplicate_invoice_ids),
        confidence=matched.confidence,
        evidence=list(matched.evidence),
        explanation=(
            f"Invoice {invoice.invoice_number if invoice else invoice_id} "
            f"{'is a duplicate of ' + ', '.join(str(i) for i in matched.duplicate_invoice_ids) if matched.duplicate_invoice_ids else 'has no duplicate in the snapshot'}."
        ),
    )


def tool_evaluate_policy(
    snapshot: FinanceSnapshot,
    *,
    subject_type: str,
    subject_id: UUID,
    amount: Decimal | None = None,
    vendor_name: str | None = None,
    vendor_id: UUID | None = None,
    is_new_vendor: bool = False,
) -> PolicyToolResult:
    if subject_type == "invoice":
        evaluation = evaluate_invoice(snapshot, subject_id)
        if evaluation is None:
            raise KeyError(subject_id)
        return PolicyToolResult(evaluation=evaluation, explanation=evaluation.explanation)
    invoice = snapshot.invoice(subject_id) if subject_type == "invoice" else None
    vendor = snapshot.vendor(vendor_id or (invoice.vendor_id if invoice else None))
    subject = PolicySubject(
        subject_type=subject_type,
        subject_id=subject_id,
        amount=amount if amount is not None else (invoice.total if invoice else Decimal("0.00")),
        vendor_id=vendor.id if vendor else vendor_id,
        vendor_name=vendor_name or (vendor.name if vendor else None),
        vendor_onboarded_at=vendor.onboarded_at if vendor else None,
        is_new_vendor=is_new_vendor,
        as_of=snapshot.as_of,
    )
    evaluation = evaluate_subject(snapshot, subject)
    return PolicyToolResult(evaluation=evaluation, explanation=evaluation.explanation)


def tool_assess_risk(snapshot: FinanceSnapshot, subject_id: UUID | None = None) -> RiskToolResult:
    result = _cached_risk(snapshot)
    findings = result.findings
    if subject_id is not None:
        findings = tuple(
            f for f in result.findings if any(rel.object_id == subject_id for rel in f.related_objects)
        )
    level = _risk_level_from_result(result, subject_id)
    conf_score = min((f.confidence.score for f in findings), default=Decimal("0.80"))
    return RiskToolResult(
        subject_type="invoice" if subject_id else "company",
        subject_id=subject_id,
        result=result,
        subject_finding_types=tuple(f.finding_type.value for f in findings),
        max_risk_level=level,
        confidence=Confidence(
            score=conf_score,
            basis="Risk engine findings; score is engine-computed, not agent-authored.",
        ),
        explanation=(
            f"{len(findings)} finding(s) for subject; max risk {level.value}."
            if findings
            else "Risk engine produced no findings for this subject."
        ),
    )


def tool_reconcile_period(snapshot: FinanceSnapshot) -> ReconciliationReport:
    return _cached_recon(snapshot)


def tool_reconcile_transaction(snapshot: FinanceSnapshot, transaction_id: UUID) -> ReconTransactionResult:
    report = reconcile(snapshot)
    match = next((m for m in report.matches if m.transaction_id == transaction_id), None)
    unresolved = next((m for m in report.unresolved if m.transaction_id == transaction_id), None)
    row = match or unresolved
    if row is None:
        return ReconTransactionResult(
            transaction_id=transaction_id,
            matched=False,
            stage=None,
            confidence=Confidence(score=Decimal("0.99"), basis="Transaction id is not in the reconciliation report."),
            explanation="Transaction is not in the current bank-feed reconciliation set.",
        )
    return ReconTransactionResult(
        transaction_id=transaction_id,
        matched=match is not None,
        stage=row.stage.value,
        counterpart_ids=row.counterpart_ids,
        amount_delta=row.amount_delta,
        forced=row.forced,
        confidence=row.confidence,
        explanation=row.explanation,
    )


def tool_get_cash_position(snapshot: FinanceSnapshot) -> CashPositionResult:
    return get_cash_position(snapshot)


def tool_get_ar_aging(snapshot: FinanceSnapshot, min_days: int = 1) -> ARAgingResult:
    rows = ar_overdue(snapshot, min_days=min_days)
    buckets = tuple(
        AgingBucket(
            invoice_id=inv.id,
            invoice_number=inv.invoice_number,
            customer_id=inv.customer_id,
            total=inv.total,
            days_overdue=days,
            status=inv.status,
        )
        for inv, days in rows
    )
    total = sum((b.total for b in buckets), Decimal("0.00"))
    return ARAgingResult(
        as_of=snapshot.as_of.isoformat(),
        overdue=buckets,
        overdue_total=Money(amount=quantize_money(total)),
        confidence=Confidence(
            score=Decimal("0.99"),
            basis="Calendar difference between as_of and invoice.due_date on open AR rows.",
        ),
        explanation=f"{len(buckets)} open AR invoice(s) overdue by at least {min_days} day(s); total {quantize_money(total)}.",
    )


def tool_evaluate_contract(snapshot: FinanceSnapshot, invoice_id: UUID) -> dict[str, Any]:
    invoice = snapshot.invoice(invoice_id)
    if invoice is None:
        raise KeyError(invoice_id)
    contract = next((c for c in snapshot.contracts if c.vendor_id == invoice.vendor_id), None)
    if contract is None:
        return {
            "invoice_id": str(invoice_id),
            "has_contract": False,
            "is_violation": False,
            "explanation": "No contract is on file for this vendor.",
            "confidence": Confidence(score=Decimal("0.99"), basis="Contract table lookup by vendor_id.").model_dump(
                mode="json"
            ),
        }
    comparison = compare_invoice_to_contract(
        contract_id=contract.id,
        invoice_id=invoice.id,
        facts=facts_from_extracted(contract.extracted_terms, fallback_price=Money(amount=invoice.total)),
        invoice_amount=Money(amount=invoice.total, currency=invoice.currency),
        invoice_date=invoice.issue_date,
    )
    return comparison.model_dump(mode="json")


def tool_get_company_context(snapshot: FinanceSnapshot) -> CompanyContext:
    cash = get_cash_position(snapshot)
    return CompanyContext(
        company_id=snapshot.company_id,
        as_of=snapshot.as_of.isoformat(),
        cash=cash.cash,
        open_ap=cash.open_ap,
        vendor_count=len(snapshot.vendors),
        open_ap_invoices=len([i for i in snapshot.ap_invoices() if i.status not in {"paid", "void"}]),
        factual_memory=tuple(row.statement for row in snapshot.factual_memories if row.status == "active"),
        historical_memory=tuple(row.statement for row in snapshot.historical_memories if row.status == "active"),
        active_precedents=tuple(row.summary for row in snapshot.active_precedents()),
        policies=tuple(f"{p.name} v{p.version}" for p in snapshot.active_policies()),
        explanation="Company context assembled from the finance snapshot, memory, and active precedent rows.",
    )


def tool_retrieve_evidence(snapshot: FinanceSnapshot, query: str) -> EvidenceSearchResult:
    adapter = ElasticAdapter()
    adapter.project_snapshot(snapshot)
    docs = adapter.search(query)
    hits = [
        EvidenceHit(
            object_type=doc.source_type,
            object_id=doc.source_id,
            title=str(doc.body.get("title") or doc.source_type),
            snippet=str(doc.body.get("body") or "")[:280] or None,
            source_system="elastic-demo",
        )
        for doc in docs[:12]
    ]
    if not hits:
        lowered = query.lower()
        for row in snapshot.evidence:
            blob = f"{row.title} {row.snippet or ''}".lower()
            if lowered in blob:
                hits.append(
                    EvidenceHit(
                        object_type=row.evidence_type,
                        object_id=row.id,
                        title=row.title,
                        snippet=row.snippet,
                        source_system=row.source_system,
                    )
                )
    return EvidenceSearchResult(
        query=query,
        hits=tuple(hits),
        explanation=f"{len(hits)} evidence hit(s) for {query!r}. Search does not invent documents.",
    )


def tool_calculate_finance_metrics(
    snapshot: FinanceSnapshot,
    *,
    runtime_only: bool = False,
) -> FinanceMetrics:
    risk = _cached_risk(snapshot)
    recon = _cached_recon(snapshot)
    if runtime_only:
        from mira.finance.snapshot import SavingsView

        runtime = tuple(row for row in snapshot.savings if row.source == "runtime")
        snapshot = snapshot.model_copy(update={"savings": runtime, "decisions": snapshot.decisions})
        _ = SavingsView
    return compute_metrics(snapshot, risk=risk, recon=recon)


def tool_calculate_autonomy_score(
    snapshot: FinanceSnapshot,
    *,
    false_escalations: Decimal = Decimal("0.00"),
    decision_accuracy: Decimal | None = None,
) -> AutonomyScoreResult:
    metrics = tool_calculate_finance_metrics(snapshot)
    score = autonomy_score(
        reconciliation_rate=metrics.reconciliation_rate,
        tasks_completed=metrics.tasks_completed,
        tasks_auto_completed=metrics.tasks_auto_completed,
        tasks_escalated=metrics.tasks_escalated,
        false_escalations=false_escalations,
        decision_accuracy=decision_accuracy if decision_accuracy is not None else metrics.decision_accuracy,
    )
    return AutonomyScoreResult(
        autonomy_score=score,
        inputs={
            "reconciliation_rate": str(metrics.reconciliation_rate),
            "tasks_completed": str(metrics.tasks_completed),
            "tasks_auto_completed": str(metrics.tasks_auto_completed),
            "tasks_escalated": str(metrics.tasks_escalated),
            "false_escalations": str(false_escalations),
            "decision_accuracy": str(decision_accuracy if decision_accuracy is not None else metrics.decision_accuracy),
        },
        explanation="Autonomy score is the published weighted formula; agents may not override it.",
    )


def tool_obtain_public_signal(series_id: str = "DGS3MO") -> PublicSignalResult:
    adapter = PublicDataAdapter(prefer_live=False)
    obs = adapter.observations(series_id=series_id)
    if not obs:
        raise KeyError(series_id)
    return PublicSignalResult(
        observation=obs[0],
        explanation="Public observation only. Interpretation is not mixed into this object.",
    )


def tool_afford_engineers(snapshot: FinanceSnapshot, headcount: int = 3) -> ScenarioAnalysis:
    return afford_engineers(snapshot, headcount=headcount)


def invoice_operational_action(matched: ThreeWayMatchResult) -> str:
    """AP operational recommendation from match/duplicate tools only."""
    if matched.duplicate_invoice_ids:
        return "reject"
    if matched.status == MatchStatus.MATCH:
        return "pay"
    if matched.status in {MatchStatus.PARTIAL_MATCH}:
        return "hold"
    return "hold"
