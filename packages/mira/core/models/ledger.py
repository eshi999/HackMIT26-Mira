from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mira.core.enums import AccountType, TransactionSource
from mira.core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

MONEY = Numeric(18, 2)


class Account(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("company_id", "code"),)

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(200))
    account_type: Mapped[str] = mapped_column(String(32), default=AccountType.ASSET.value)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_cash: Mapped[bool] = mapped_column(Boolean, default=False)


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transactions"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    customer_id: Mapped[UUID | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[str] = mapped_column(String(400))
    source: Mapped[str] = mapped_column(String(32), default=TransactionSource.MANUAL.value)
    external_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_sandbox: Mapped[bool] = mapped_column(Boolean, default=False)
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)


class LedgerEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ledger_entries"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True, index=True
    )
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    debit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    credit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
