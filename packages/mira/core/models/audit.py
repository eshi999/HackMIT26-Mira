from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, event
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.types import JSON

from mira.core.enums import ActorType
from mira.core.models.base import Base, UUIDPrimaryKeyMixin


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only. Application repositories must insert, never update or delete."""

    __tablename__ = "audit_events"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), default=ActorType.SYSTEM.value)
    actor_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    object_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    correlation_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


@event.listens_for(AuditEvent, "before_update")
def _forbid_update(mapper, connection, target: AuditEvent) -> None:  # noqa: ARG001
    raise RuntimeError("AuditEvent is append-only and cannot be updated")


@event.listens_for(Session, "persistent_to_deleted")
def _forbid_delete(session: Session, instance: object) -> None:  # noqa: ARG001
    if isinstance(instance, AuditEvent):
        raise RuntimeError("AuditEvent is append-only and cannot be deleted")
