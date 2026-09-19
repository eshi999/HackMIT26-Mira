from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from mira.core.enums import MetricSource, ReconciliationStatus, SavingsCategory
from mira.core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

MONEY = Numeric(18, 2)


class Precedent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "precedents"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    situation_hash: Mapped[str] = mapped_column(String(64), index=True)
    decision_id: Mapped[UUID | None] = mapped_column(ForeignKey("decisions.id"), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String(200))
    period: Mapped[str] = mapped_column(String(7))
    reusable_rule: Mapped[str | None] = mapped_column(Text, nullable=True)


class Forecast(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "forecasts"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    metric_name: Mapped[str] = mapped_column(String(80))
    period: Mapped[str] = mapped_column(String(16))
    method: Mapped[str] = mapped_column(String(80))
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    lower: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    upper: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    inputs_hash: Mapped[str] = mapped_column(String(64))
    engine_version: Mapped[str] = mapped_column(String(32), default="forecast-0")


class Metric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "metrics"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    period: Mapped[str] = mapped_column(String(16))
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(32), default=MetricSource.SEED.value)


class SavingsEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "savings_events"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    category: Mapped[str] = mapped_column(String(40), default=SavingsCategory.OTHER.value)
    amount_usd: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    hours_saved: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"))
    workflow: Mapped[str] = mapped_column(String(80))
    period: Mapped[str] = mapped_column(String(7))
    related_object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    related_object_id: Mapped[UUID | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExternalSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_signals"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    source: Mapped[str] = mapped_column(String(40))
    series_id: Mapped[str] = mapped_column(String(40), index=True)
    as_of: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    uri: Mapped[str | None] = mapped_column(String(800), nullable=True)


class ReconciliationCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reconciliation_cases"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    case_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(32), default=ReconciliationStatus.OPEN.value)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    title: Mapped[str] = mapped_column(String(300))


class RecurringSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Expected recurring vendor charge. Used by unused/unexpected subscription detectors."""

    __tablename__ = "recurring_subscriptions"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    vendor_id: Mapped[UUID] = mapped_column(ForeignKey("vendors.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    expected_amount: Mapped[Decimal] = mapped_column(MONEY)
    cadence: Mapped[str] = mapped_column(String(32), default="monthly")
    is_in_use: Mapped[bool] = mapped_column(Boolean, default=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancelled_at: Mapped[date | None] = mapped_column(Date, nullable=True)
