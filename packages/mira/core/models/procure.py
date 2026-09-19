from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mira.core.enums import (
    InvoiceDirection,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    POStatus,
    ReceiptStatus,
)
from mira.core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

MONEY = Numeric(18, 2)


class Budget(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("company_id", "name", "period"),)

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    period: Mapped[str] = mapped_column(String(7))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    owner_employee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )


class BudgetLine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "budget_lines"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    budget_id: Mapped[UUID] = mapped_column(ForeignKey("budgets.id"), index=True)
    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    spent_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))


class PurchaseOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("company_id", "po_number"),)

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    vendor_id: Mapped[UUID] = mapped_column(ForeignKey("vendors.id"), index=True)
    po_number: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(32), default=POStatus.DRAFT.value)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    needed_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    total: Mapped[Decimal] = mapped_column(MONEY)
    budget_id: Mapped[UUID | None] = mapped_column(ForeignKey("budgets.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseOrderLine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "purchase_order_lines"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id"), index=True
    )
    description: Mapped[str] = mapped_column(String(400))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)


class GoodsReceipt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "goods_receipts"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id"), index=True
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default=ReceiptStatus.POSTED.value)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class GoodsReceiptLine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "goods_receipt_lines"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    goods_receipt_id: Mapped[UUID] = mapped_column(ForeignKey("goods_receipts.id"), index=True)
    purchase_order_line_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("purchase_order_lines.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(400))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("company_id", "direction", "invoice_number"),)

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    customer_id: Mapped[UUID | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    invoice_number: Mapped[str] = mapped_column(String(80))
    direction: Mapped[str] = mapped_column(String(8), default=InvoiceDirection.AP.value)
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    subtotal: Mapped[Decimal] = mapped_column(MONEY)
    tax_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(32), default=InvoiceStatus.RECEIVED.value)
    purchase_order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=True
    )
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    is_duplicate_suspect: Mapped[bool] = mapped_column(Boolean, default=False)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    posted_period: Mapped[str | None] = mapped_column(String(7), nullable=True)


class InvoiceLine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invoice_lines"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    description: Mapped[str] = mapped_column(String(400))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    gl_code: Mapped[str | None] = mapped_column(String(16), nullable=True)


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    method: Mapped[str] = mapped_column(String(32), default=PaymentMethod.VISA_SANDBOX.value)
    status: Mapped[str] = mapped_column(String(32), default=PaymentStatus.PENDING.value)
    is_sandbox: Mapped[bool] = mapped_column(Boolean, default=True)
    processor_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True
    )
