"""13-week cash forecast and hiring scenarios. Deterministic arithmetic only."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from mira.core.agent_outputs import Confidence, EvidenceReference, ScenarioAnalysis, ScenarioCase
from mira.core.money import Money, quantize_money
from mira.finance.aging import days_overdue
from mira.finance.cash import get_cash_position
from mira.finance.snapshot import FinanceSnapshot

ENGINE_VERSION = "forecast-1"
ENGINEER_MONTHLY_COST = Decimal("15000.00")
WEEKS = 13


def _week_ending(as_of: date, week: int) -> date:
    return as_of + timedelta(days=7 * week)


def _weekly_burn(snapshot: FinanceSnapshot) -> Decimal:
    burn = snapshot.metric("monthly_burn")
    monthly = burn.value if burn else Decimal("510000.00")
    return quantize_money(monthly / Decimal("4.3333"))


def _ap_due_in_week(snapshot: FinanceSnapshot, start: date, end: date) -> Decimal:
    total = Decimal("0.00")
    for invoice in snapshot.ap_invoices():
        if invoice.status in {"paid", "void", "rejected"}:
            continue
        due = invoice.due_date or invoice.issue_date
        if start < due <= end:
            total += invoice.total
    return quantize_money(total)


def _ar_due_in_week(snapshot: FinanceSnapshot, start: date, end: date, *, delay_days: int = 0) -> Decimal:
    total = Decimal("0.00")
    for invoice in snapshot.ar_invoices():
        if invoice.status in {"paid", "void"}:
            continue
        due = invoice.due_date or invoice.issue_date
        if delay_days:
            due = due + timedelta(days=delay_days)
        if start < due <= end:
            total += invoice.total
    return quantize_money(total)


def _project(
    snapshot: FinanceSnapshot,
    *,
    extra_weekly: Decimal,
    ar_delay_days: int,
    name: str,
    assumptions: list[str],
) -> ScenarioCase:
    cash = get_cash_position(snapshot).cash.amount
    weekly_burn = _weekly_burn(snapshot)
    rows: list[dict] = []
    cursor = cash
    start = snapshot.as_of
    for week in range(1, WEEKS + 1):
        end = _week_ending(snapshot.as_of, week)
        ap = _ap_due_in_week(snapshot, start, end)
        ar = _ar_due_in_week(snapshot, start, end, delay_days=ar_delay_days)
        cursor = quantize_money(cursor + ar - ap - weekly_burn - extra_weekly)
        rows.append(
            {
                "week": week,
                "ending": end.isoformat(),
                "ar_in": str(ar),
                "ap_out": str(ap),
                "burn": str(weekly_burn),
                "extra": str(extra_weekly),
                "cash": str(cursor),
            }
        )
        start = end
    return ScenarioCase(
        name=name,
        cash_start=Money(amount=cash),
        cash_end_13w=Money(amount=cursor),
        weekly=rows,
        assumptions=assumptions,
        explanation=(
            f"{name}: start {cash}, 13-week ending cash {cursor}. "
            f"Weekly operating burn {weekly_burn}; extra weekly cost {extra_weekly}."
        ),
    )


def afford_engineers(snapshot: FinanceSnapshot, *, headcount: int = 3) -> ScenarioAnalysis:
    extra_monthly = ENGINEER_MONTHLY_COST * Decimal(headcount)
    extra_weekly = quantize_money(extra_monthly / Decimal("4.3333"))
    largest_open_ar = max(
        (inv for inv in snapshot.ar_invoices() if inv.status not in {"paid", "void"}),
        key=lambda inv: inv.total,
        default=None,
    )
    delay_days = 30
    assumptions = [
        f"Fully loaded engineer cost is {ENGINEER_MONTHLY_COST}/month (assumption, not generated).",
        f"Hiring {headcount} adds {extra_monthly}/month ({extra_weekly}/week).",
        "Weekly burn is monthly_burn / 4.3333 from the stored metric.",
        "AP leaves cash on invoice due dates; AR arrives on due dates unless delayed.",
        "This is a scenario, not a guarantee.",
    ]
    base = _project(
        snapshot,
        extra_weekly=extra_weekly,
        ar_delay_days=0,
        name="BASE CASE — hire 3",
        assumptions=assumptions,
    )
    delayed = _project(
        snapshot,
        extra_weekly=extra_weekly,
        ar_delay_days=delay_days,
        name="DELAYED RECEIVABLE CASE — customer payment arrives 30 days late",
        assumptions=assumptions
        + [
            f"Largest open AR ({largest_open_ar.invoice_number if largest_open_ar else 'n/a'}) "
            f"is shifted {delay_days} days."
        ],
    )
    buffer = Decimal("250000.00")
    if base.cash_end_13w.amount >= buffer and delayed.cash_end_13w.amount >= buffer:
        rec = (
            f"Both cases keep 13-week cash above the {buffer} operating buffer. "
            f"Hiring {headcount} engineers is affordable under the stated assumptions; "
            "treat the delayed-receivable case as the stress test, not a certainty."
        )
    elif base.cash_end_13w.amount >= buffer:
        rec = (
            f"Base case stays above the {buffer} buffer (ending {base.cash_end_13w.amount}) "
            f"but the delayed-receivable case ends at {delayed.cash_end_13w.amount}. "
            "Do not hire on the base case alone."
        )
    else:
        rec = (
            f"Base-case 13-week cash {base.cash_end_13w.amount} is below the {buffer} buffer. "
            "Do not hire on current forecast inputs."
        )
    evidence = [
        EvidenceReference(
            object_type="metric",
            object_id=snapshot.company_id,
            source_system="ledger",
            locator="metric:cash",
            excerpt=str(base.cash_start.amount),
        )
    ]
    if largest_open_ar is not None:
        evidence.append(
            EvidenceReference(
                object_type="invoice",
                object_id=largest_open_ar.id,
                source_system="ledger",
                locator=f"invoice:{largest_open_ar.invoice_number}",
                excerpt=str(largest_open_ar.total),
            )
        )
    overdue = [
        (inv, days_overdue(inv, snapshot.as_of) or 0)
        for inv in snapshot.ar_invoices()
        if (days_overdue(inv, snapshot.as_of) or 0) > 0
    ]
    return ScenarioAnalysis(
        question=f"Can we afford {headcount} new engineers?",
        base_case=base,
        delayed_receivable_case=delayed,
        recommendation=rec,
        confidence=Confidence(
            score=Decimal("0.90"),
            basis="Forecast arithmetic uses stored cash, invoice due dates, and a documented payroll assumption.",
        ),
        evidence=evidence,
        assumptions=assumptions
        + [f"{len(overdue)} open AR invoices are already overdue as of {snapshot.as_of.isoformat()}."],
    )
