"""Event intake. Mira works when nobody is chatting."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from mira.agents.persist import write_audit
from mira.core.enums import ActorType, OfficeEventStatus, OfficeEventType
from mira.core.models import OfficeEvent

SUPPORTED_EVENTS = (
    OfficeEventType.INVOICE_RECEIVED,
    OfficeEventType.BANK_FEED_UPDATED,
    OfficeEventType.PAYMENT_RECEIVED,
    OfficeEventType.PURCHASE_REQUESTED,
    OfficeEventType.MONTH_END_STARTED,
    OfficeEventType.CLOSE_DEADLINE_APPROACHING,
    OfficeEventType.DOCUMENT_INGESTED,
    OfficeEventType.HUMAN_FEEDBACK_RECEIVED,
)


def record_event(
    session: Session,
    *,
    company_id: UUID,
    event_type: OfficeEventType,
    payload: dict | None = None,
    correlation_id: UUID | None = None,
) -> OfficeEvent:
    row = OfficeEvent(
        id=uuid4(),
        company_id=company_id,
        event_type=event_type.value,
        status=OfficeEventStatus.RECEIVED.value,
        payload=payload or {},
        occurred_at=datetime.now(UTC),
        correlation_id=correlation_id,
    )
    session.add(row)
    session.flush()
    write_audit(
        session,
        company_id=company_id,
        event_type="office_event_received",
        actor_type=ActorType.SYSTEM,
        object_type="office_event",
        object_id=row.id,
        correlation_id=correlation_id,
        payload={"event_type": event_type.value, "payload": payload or {}},
    )
    return row


def attach_run(session: Session, event: OfficeEvent, run_id: UUID) -> OfficeEvent:
    event.agent_run_id = run_id
    event.status = OfficeEventStatus.RUNNING.value
    session.flush()
    return event


def finish_event(session: Session, event: OfficeEvent, status: OfficeEventStatus) -> OfficeEvent:
    event.status = status.value
    session.flush()
    return event
