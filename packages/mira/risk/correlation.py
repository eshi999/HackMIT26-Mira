"""Correlate related findings into FinancialIncidents. Union-find on business objects."""

from __future__ import annotations

from uuid import UUID, uuid5

from mira.core.enums import FindingType
from mira.risk.scoring import (
    ENGINE_VERSION,
    explain_incident,
    incident_confidence,
    incident_risk_score,
    recommended_action,
    risk_level_for,
    scoring_breakdown,
)
from mira.risk.types import FinancialIncident, RelatedObject, TypedFinding

INCIDENT_NS = UUID("aaaaaaaa-bbbb-cccc-dddd-000000000098")

# Findings that should stay in their own incident even if they share a vendor.
SOLO_TYPES = {
    FindingType.ABNORMAL_TRANSACTION_TIMING,
    FindingType.OVERDUE_RECEIVABLE,
}


class _UnionFind:
    def __init__(self, items: list[UUID]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: UUID) -> UUID:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: UUID, right: UUID) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[b] = a


def _keys(finding: TypedFinding) -> set[str]:
    keys = {f"{rel.object_type}:{rel.object_id}" for rel in finding.related_objects}
    return keys


def correlate(findings: tuple[TypedFinding, ...]) -> tuple[FinancialIncident, ...]:
    if not findings:
        return ()
    solo = [f for f in findings if f.finding_type in SOLO_TYPES]
    grouped = [f for f in findings if f.finding_type not in SOLO_TYPES]
    clusters: list[list[TypedFinding]] = [[f] for f in solo]

    if grouped:
        uf = _UnionFind([f.id for f in grouped])
        by_key: dict[str, list[UUID]] = {}
        for finding in grouped:
            for key in _keys(finding):
                # Vendor-only links are too coarse (every Apex invoice would collapse).
                if key.startswith("vendor:"):
                    continue
                by_key.setdefault(key, []).append(finding.id)
        for ids in by_key.values():
            head = ids[0]
            for other in ids[1:]:
                uf.union(head, other)
        buckets: dict[UUID, list[TypedFinding]] = {}
        for finding in grouped:
            buckets.setdefault(uf.find(finding.id), []).append(finding)
        clusters.extend(buckets.values())

    incidents: list[FinancialIncident] = []
    for cluster in clusters:
        cluster_t = tuple(sorted(cluster, key=lambda f: f.finding_type.value))
        risk = incident_risk_score(cluster_t)
        confidence = incident_confidence(cluster_t)
        breakdown = scoring_breakdown(cluster_t)
        action = recommended_action(cluster_t)
        related: list[RelatedObject] = []
        seen: set[tuple[str, UUID]] = set()
        for finding in cluster_t:
            for rel in finding.related_objects:
                marker = (rel.object_type, rel.object_id)
                if marker in seen:
                    continue
                seen.add(marker)
                related.append(rel)
        evidence = tuple(dict.fromkeys(eid for f in cluster_t for eid in f.evidence_ids))
        title = cluster_t[0].title if len(cluster_t) == 1 else f"{len(cluster_t)} correlated findings: {cluster_t[0].title}"
        incident_id = uuid5(INCIDENT_NS, "|".join(sorted(str(f.id) for f in cluster_t)))
        explanation = explain_incident(
            risk_score=risk,
            risk_level=risk_level_for(risk),
            confidence=confidence,
            breakdown=breakdown,
            action=action,
            findings=cluster_t,
        )
        incidents.append(
            FinancialIncident(
                id=incident_id,
                title=title,
                findings=cluster_t,
                risk_score=risk,
                risk_level=risk_level_for(risk),
                confidence=confidence,
                evidence_ids=evidence,
                related_objects=tuple(related),
                recommended_action=action,
                scoring_breakdown=breakdown,
                explanation=explanation,
                engine_version=ENGINE_VERSION,
            )
        )
    incidents.sort(key=lambda row: row.risk_score, reverse=True)
    return tuple(incidents)
