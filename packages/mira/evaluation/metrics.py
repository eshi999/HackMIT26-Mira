"""Ramp scoreboard metrics and Autonomy Score. Written by code, never by an LLM."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from mira.core.money import quantize_money
from mira.finance.snapshot import FinanceSnapshot
from mira.reconciliation.types import ReconciliationReport
from mira.risk.types import RiskEngineResult

ENGINE_VERSION = "eval-1"


class FinanceMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    money_saved: Decimal
    money_protected: Decimal
    money_recovered: Decimal
    estimated_hours_saved: Decimal
    tasks_completed: Decimal
    tasks_auto_completed: Decimal
    tasks_escalated: Decimal
    false_escalations: Decimal
    reconciliation_rate: Decimal
    decision_accuracy: Decimal
    autonomy_score: Decimal
    autonomous_completion_rate: Decimal = Decimal("0.00")
    false_escalation_rate: Decimal = Decimal("0.00")
    correct_escalation_rate: Decimal = Decimal("0.00")
    evidence_completeness: Decimal = Decimal("0.00")
    human_interventions: Decimal = Decimal("0.00")
    engine_version: str = ENGINE_VERSION


def _ratio(num: Decimal, den: Decimal) -> Decimal:
    if den == 0:
        return Decimal("0.00")
    return quantize_money(num / den)


def autonomy_score(
    *,
    reconciliation_rate: Decimal,
    tasks_completed: Decimal,
    tasks_auto_completed: Decimal,
    tasks_escalated: Decimal,
    false_escalations: Decimal,
    decision_accuracy: Decimal,
) -> Decimal:
    """0–100. Escalating true high-risk work is not penalized; false escalations are.

    autonomy = 100 * (
        0.30 * reconciliation_rate
      + 0.25 * auto_complete_rate
      + 0.25 * decision_accuracy
      + 0.20 * (1 - false_escalation_rate)
    )
    """
    auto_rate = _ratio(tasks_auto_completed, tasks_completed) if tasks_completed else Decimal("0.00")
    false_rate = _ratio(false_escalations, tasks_escalated) if tasks_escalated else Decimal("0.00")
    score = (
        Decimal("0.30") * reconciliation_rate
        + Decimal("0.25") * auto_rate
        + Decimal("0.25") * decision_accuracy
        + Decimal("0.20") * (Decimal("1.00") - false_rate)
    )
    return min(Decimal("100.00"), quantize_money(score * Decimal("100")))


def compute_metrics(
    snapshot: FinanceSnapshot,
    *,
    risk: RiskEngineResult | None = None,
    recon: ReconciliationReport | None = None,
    money_recovered: Decimal = Decimal("0.00"),
    false_escalations: Decimal = Decimal("0.00"),
    decision_accuracy: Decimal | None = None,
) -> FinanceMetrics:
    protected = sum(
        (row.amount_usd for row in snapshot.savings if row.category in {"duplicate_prevented", "policy_block"}),
        Decimal("0.00"),
    )
    saved = sum(
        (row.amount_usd for row in snapshot.savings if row.category in {"early_pay_discount", "other"}),
        Decimal("0.00"),
    )
    hours = sum((row.hours_saved for row in snapshot.savings), Decimal("0.00"))

    decisions = snapshot.decisions
    auto_done = {"evaluated", "proposed", "executed"}
    completed_statuses = auto_done | {"approved", "rejected"}
    completed = Decimal(len([d for d in decisions if d.status in completed_statuses]))
    auto_completed = Decimal(
        len([d for d in decisions if d.status in auto_done and not d.requires_human_approval])
    )
    escalated = Decimal(len([d for d in decisions if d.requires_human_approval]))
    tasks_completed = Decimal(len(decisions)) if decisions else completed
    human_interventions = escalated

    recon_rate = recon.reconciliation_rate if recon is not None else Decimal("0.00")
    accuracy = decision_accuracy
    if accuracy is None:
        accuracy = Decimal("1.00") if decisions else Decimal("0.00")

    auto_rate = _ratio(auto_completed, tasks_completed) if tasks_completed else Decimal("0.00")
    false_rate = _ratio(false_escalations, escalated) if escalated else Decimal("0.00")
    correct_rate = (Decimal("1.00") - false_rate) if escalated else Decimal("0.00")
    evidence_completeness = (
        _ratio(
            Decimal(len([d for d in decisions if d.subject_id is not None])),
            Decimal(len(decisions)),
        )
        if decisions
        else Decimal("0.00")
    )

    score = autonomy_score(
        reconciliation_rate=recon_rate,
        tasks_completed=tasks_completed,
        tasks_auto_completed=auto_completed,
        tasks_escalated=escalated,
        false_escalations=false_escalations,
        decision_accuracy=accuracy,
    )
    return FinanceMetrics(
        money_saved=quantize_money(saved),
        money_protected=quantize_money(protected),
        money_recovered=quantize_money(money_recovered),
        estimated_hours_saved=quantize_money(hours),
        tasks_completed=tasks_completed,
        tasks_auto_completed=auto_completed,
        tasks_escalated=escalated,
        false_escalations=false_escalations,
        reconciliation_rate=recon_rate,
        decision_accuracy=accuracy,
        autonomy_score=score,
        autonomous_completion_rate=auto_rate,
        false_escalation_rate=false_rate,
        correct_escalation_rate=correct_rate,
        evidence_completeness=evidence_completeness,
        human_interventions=human_interventions,
    )
