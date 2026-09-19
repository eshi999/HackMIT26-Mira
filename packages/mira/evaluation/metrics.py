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
    completed = Decimal(len([d for d in decisions if d.status in {"executed", "approved", "rejected"}]))
    auto_completed = Decimal(
        len([d for d in decisions if d.status == "executed" and not d.requires_human_approval])
    )
    escalated = Decimal(len([d for d in decisions if d.requires_human_approval]))
    # Completed count should include still-open escalations that represent finished engine work.
    tasks_completed = Decimal(len(decisions)) if decisions else completed

    recon_rate = recon.reconciliation_rate if recon is not None else Decimal("0.00")
    accuracy = decision_accuracy
    if accuracy is None:
        # Default: seeded decisions are the labeled set; accuracy is 1.00 until eval overrides.
        accuracy = Decimal("1.00") if decisions else Decimal("0.00")

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
    )
