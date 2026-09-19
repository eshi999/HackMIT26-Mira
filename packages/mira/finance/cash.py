"""Cash position from canonical metrics and open obligations. No LLM arithmetic."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from mira.core.agent_outputs import Confidence, EvidenceReference
from mira.core.money import Money, quantize_money
from mira.finance.aging import days_overdue
from mira.finance.snapshot import FinanceSnapshot

ENGINE_VERSION = "cash-1"


class CashPositionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    cash: Money
    open_ap: Money
    open_ar: Money
    ar_overdue: Money
    net_liquidity: Money
    currency: str = "USD"
    as_of: str
    source: str
    confidence: Confidence
    evidence: list[EvidenceReference] = Field(default_factory=list)
    explanation: str
    engine_version: str = ENGINE_VERSION


def get_cash_position(snapshot: FinanceSnapshot) -> CashPositionResult:
    cash_metric = snapshot.metric("cash")
    cash_amount = quantize_money(cash_metric.value if cash_metric else Decimal("0.00"))
    ap = sum(
        (inv.total for inv in snapshot.ap_invoices() if inv.status not in {"paid", "void", "rejected"}),
        Decimal("0.00"),
    )
    ar = sum(
        (inv.total for inv in snapshot.ar_invoices() if inv.status not in {"paid", "void"}),
        Decimal("0.00"),
    )
    overdue = sum(
        (
            inv.total
            for inv in snapshot.ar_invoices()
            if inv.status not in {"paid", "void"}
            and (days_overdue(inv, snapshot.as_of) or 0) > 0
        ),
        Decimal("0.00"),
    )
    source = cash_metric.source if cash_metric else "computed"
    evidence = [
        EvidenceReference(
            object_type="metric",
            object_id=snapshot.company_id,
            source_system="ledger",
            locator="metric:cash",
            excerpt=str(cash_amount),
        )
    ]
    return CashPositionResult(
        cash=Money(amount=cash_amount),
        open_ap=Money(amount=quantize_money(ap)),
        open_ar=Money(amount=quantize_money(ar)),
        ar_overdue=Money(amount=quantize_money(overdue)),
        net_liquidity=Money(amount=quantize_money(cash_amount + ar - ap)),
        as_of=snapshot.as_of.isoformat(),
        source=source,
        confidence=Confidence(
            score=Decimal("0.99") if cash_metric else Decimal("0.70"),
            basis="Cash is the stored metric; AP/AR are sums of open canonical invoices.",
        ),
        evidence=evidence,
        explanation=(
            f"Operating cash {cash_amount} as of {snapshot.as_of.isoformat()} "
            f"(source={source}). Open AP {quantize_money(ap)}; open AR {quantize_money(ar)}."
        ),
    )
