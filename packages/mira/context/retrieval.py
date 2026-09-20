"""Existing Elastic search ranks allowlisted canonical sources; never supplies truth."""

import os
from uuid import UUID

from mira.finance.snapshot import FinanceSnapshot
from mira.integrations.elastic import ElasticAdapter, ElasticIntegrationError


def rank_sources(
    snapshot: FinanceSnapshot,
    query: str,
    allowed: set[str],
    *,
    adapter: ElasticAdapter | None = None,
    offline: bool = False,
) -> tuple[set[str], str]:
    local = ElasticAdapter()
    local.project_snapshot(snapshot)  # in-memory only; never index into a live cluster here
    selected = adapter
    if selected is None and not offline and os.getenv("ELASTICSEARCH_URL"):
        selected = ElasticAdapter(
            os.environ["ELASTICSEARCH_URL"], api_key=os.getenv("ELASTICSEARCH_API_KEY"), timeout=2
        )
    source = "local_fallback"
    hits = local.search(query)
    if selected is not None and not offline:
        try:
            hits = selected.search(query)
            source = "elasticsearch" if selected.url else "local_fallback"
        except (ElasticIntegrationError, ValueError, KeyError, TypeError):
            source = "local_fallback"
    # Search is not an authorization boundary. Reject foreign and stale/unlinked IDs,
    # and use only the IDs for ordering; model facts always come from the snapshot.
    ranked = {
        str(hit.source_id)
        for hit in hits
        if UUID(str(hit.company_id)) == snapshot.company_id and str(hit.source_id) in allowed
    }
    return ranked, source
