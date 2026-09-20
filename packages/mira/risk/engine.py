"""Run detectors, correlate, score. Agents may explain the result; they may not set it."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from mira.core.enums import FindingStatus, IncidentStatus
from mira.core.models.control import Finding, Incident, IncidentFinding
from mira.finance.snapshot import FinanceSnapshot, load_snapshot
from mira.risk.correlation import correlate
from mira.risk.detectors import run_detectors
from mira.risk.scoring import ENGINE_VERSION
from mira.risk.types import RiskEngineResult


def run_risk_engine(snapshot: FinanceSnapshot) -> RiskEngineResult:
    findings = run_detectors(snapshot)
    incidents = correlate(findings)
    return RiskEngineResult(findings=findings, incidents=incidents, engine_version=ENGINE_VERSION)


def run_for_company(session: Session, company_id: UUID, as_of) -> RiskEngineResult:
    snapshot = load_snapshot(session, company_id, as_of)
    return run_risk_engine(snapshot)


def persist_result(session: Session, company_id: UUID, result: RiskEngineResult, opened_at: datetime) -> None:
    """Optional materialization. Seeded demo findings are separate from engine output.

    Finding and incident IDs are deterministic (uuid5), so a second persist is a no-op.
    """
    for finding in result.findings:
        if session.get(Finding, finding.id) is not None:
            continue
        session.add(
            Finding(
                id=finding.id,
                company_id=company_id,
                finding_type=finding.finding_type.value,
                severity=finding.severity.value,
                title=finding.title,
                description=finding.description,
                status=FindingStatus.OPEN.value,
                related_object_type=finding.related_objects[0].object_type if finding.related_objects else None,
                related_object_id=finding.related_objects[0].object_id if finding.related_objects else None,
                detector=finding.finding_type.value,
                details=finding.facts,
                confidence_score=finding.confidence.score,
                risk_contribution=finding.risk_contribution,
                evidence_ids=[str(eid) for eid in finding.evidence_ids],
            )
        )
    for incident in result.incidents:
        if session.get(Incident, incident.id) is None:
            session.add(
                Incident(
                    id=incident.id,
                    company_id=company_id,
                    title=incident.title,
                    severity=incident.risk_level.value,
                    status=IncidentStatus.OPEN.value,
                    opened_at=opened_at,
                    incident_type=incident.findings[0].finding_type.value if incident.findings else None,
                    risk_score=incident.risk_score,
                    risk_level=incident.risk_level.value,
                    confidence_score=incident.confidence.score,
                    evidence_ids=[str(eid) for eid in incident.evidence_ids],
                    related_objects=[rel.model_dump(mode="json") for rel in incident.related_objects],
                    recommended_action=incident.recommended_action.value,
                    scoring_breakdown=incident.scoring_breakdown.model_dump(mode="json"),
                    explanation=incident.explanation,
                    engine_version=incident.engine_version,
                )
            )
        for finding in incident.findings:
            link_exists = session.query(IncidentFinding).filter(
                IncidentFinding.incident_id == incident.id,
                IncidentFinding.finding_id == finding.id,
            ).first()
            if link_exists is not None:
                continue
            session.add(IncidentFinding(incident_id=incident.id, finding_id=finding.id))
    session.flush()
