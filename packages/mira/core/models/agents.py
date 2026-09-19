from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from mira.core.enums import ActorType, AgentRole, AgentRunStatus, AgentTaskStatus, OfficeEventStatus
from mira.core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A body of work Mira owns."""

    __tablename__ = "agent_runs"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    workflow_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(32), default=AgentRunStatus.QUEUED.value)
    initiated_by: Mapped[str] = mapped_column(String(32), default=ActorType.MIRA.value)
    initiator_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_tasks"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    agent_run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    agent_role: Mapped[str] = mapped_column(String(40), default=AgentRole.MIRA_CFO.value)
    parent_task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_tasks.id"), nullable=True
    )
    originating_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_object_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    evidence_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=AgentTaskStatus.QUEUED.value)
    input_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    result_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OfficeEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Internal event that may spawn an AgentRun. Not a chat message."""

    __tablename__ = "office_events"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(32), default=OfficeEventStatus.RECEIVED.value)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    agent_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_runs.id"), nullable=True, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
