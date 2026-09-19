from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mira.core.enums import EmployeeStatus, PartyStatus, RiskTier, UserRole
from mira.core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    legal_name: Mapped[str] = mapped_column(String(300))
    industry: Mapped[str] = mapped_column(String(120))
    stage: Mapped[str] = mapped_column(String(80), default="seed")
    fiscal_year_start_month: Mapped[int] = mapped_column(Integer, default=1)
    base_currency: Mapped[str] = mapped_column(String(3), default="USD")
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("company_id", "email"),)

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    email: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.EXECUTIVE.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    company: Mapped[Company] = relationship()


class Employee(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("company_id", "employee_number"),)

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    employee_number: Mapped[str] = mapped_column(String(40))
    full_name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(160))
    department: Mapped[str] = mapped_column(String(120))
    cost_center: Mapped[str | None] = mapped_column(String(40), nullable=True)
    manager_id: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=EmployeeStatus.ACTIVE.value)
    approval_limit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)


class Vendor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vendors"
    __table_args__ = (UniqueConstraint("company_id", "name"),)

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    tax_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(80), nullable=True)
    default_currency: Mapped[str] = mapped_column(String(3), default="USD")
    risk_tier: Mapped[str] = mapped_column(String(16), default=RiskTier.MEDIUM.value)
    status: Mapped[str] = mapped_column(String(32), default=PartyStatus.ACTIVE.value)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    onboarded_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    bank_account_ref: Mapped[str | None] = mapped_column(String(40), nullable=True)
    previous_bank_account_ref: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bank_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("company_id", "name"),)

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    tax_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(80), nullable=True)
    default_currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(32), default=PartyStatus.ACTIVE.value)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
