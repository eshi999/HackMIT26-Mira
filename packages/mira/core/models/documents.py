from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from mira.core.enums import (
    ContractStatus,
    DocumentClass,
    ExtractionStatus,
    PolicyStatus,
    PolicyType,
    StorageBackend,
)
from mira.core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

MONEY = Numeric(18, 2)


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    filename: Mapped[str] = mapped_column(String(400))
    mime_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    storage_backend: Mapped[str] = mapped_column(String(32), default=StorageBackend.LOCAL.value)
    storage_uri: Mapped[str] = mapped_column(String(800))
    document_class: Mapped[str] = mapped_column(String(32), default=DocumentClass.OTHER.value)
    extraction_status: Mapped[str] = mapped_column(
        String(32), default=ExtractionStatus.PENDING.value
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class Contract(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contracts"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    value: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(32), default=ContractStatus.ACTIVE.value)
    extracted_terms: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Policy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "policies"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    policy_type: Mapped[str] = mapped_column(String(32), default=PolicyType.SPEND.value)
    version: Mapped[str] = mapped_column(String(32), default="1")
    body: Mapped[str] = mapped_column(Text)
    rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default=PolicyStatus.ACTIVE.value)
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
