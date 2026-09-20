"""Evidence search: Elastic when live, SQL/demo projection otherwise."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.routers.company import _require_northstar
from mira.agents.tools import tool_retrieve_evidence
from mira.finance.snapshot import load_snapshot
from mira.integrations.elastic import ElasticAdapter
from mira.seed.northstar import AS_OF

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])


@router.get("/search")
def search_evidence(
    q: str = Query(min_length=1, max_length=200),
    db: Session = Depends(get_db),
) -> dict:
    company = _require_northstar(db)
    snapshot = load_snapshot(db, company.id, AS_OF.date())
    result = tool_retrieve_evidence(snapshot, q)
    adapter = ElasticAdapter(
        os.environ.get("ELASTICSEARCH_URL") or None,
        api_key=os.environ.get("ELASTICSEARCH_API_KEY") or None,
    )
    retrieval_source = "elastic" if adapter.status().value == "live" else "elastic-demo"
    return {
        "query": result.query,
        "retrieval_source": retrieval_source,
        "hit_count": len(result.hits),
        "explanation": result.explanation,
        "hits": [
            {
                "object_type": hit.object_type,
                "object_id": str(hit.object_id) if hit.object_id else None,
                "title": hit.title,
                "snippet": hit.snippet,
                "source_system": hit.source_system,
            }
            for hit in result.hits
        ],
    }
