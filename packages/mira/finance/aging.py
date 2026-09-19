"""Aging helpers. Deterministic calendar math."""

from __future__ import annotations

from datetime import date

from mira.finance.snapshot import FinanceSnapshot, InvoiceView


def days_overdue(invoice: InvoiceView, as_of: date) -> int | None:
    if invoice.due_date is None:
        return None
    return (as_of - invoice.due_date).days


def ar_overdue(snapshot: FinanceSnapshot, *, min_days: int = 45) -> tuple[tuple[InvoiceView, int], ...]:
    out: list[tuple[InvoiceView, int]] = []
    for invoice in snapshot.ar_invoices():
        if invoice.status in {"paid", "void"}:
            continue
        days = days_overdue(invoice, snapshot.as_of)
        if days is None or days <= min_days:
            continue
        out.append((invoice, days))
    return tuple(out)
