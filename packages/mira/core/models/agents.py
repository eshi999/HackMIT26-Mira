from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from mira.core.enums import ActorType, AgentRole, AgentRunStatus, AgentTaskStatus
from mira.core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A body of work Mira owns. Runtime is not implemented in this slice."""

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
    status: Mapped[str] = mapped_column(String(32), default=AgentTaskStatus.QUEUED.value)
    input_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    result_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
