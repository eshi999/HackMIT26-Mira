from __future__ import annotations

from mira.evidence.index_docs import ALL_INDICES, INDEX_MAPPINGS
from mira.integrations.public_data import (
    BusinessMovement,
    ModelInterpretation,
    PublicDataAdapter,
    PublicDataObservation,
)


def test_public_observation_is_not_interpretation() -> None:
    adapter = PublicDataAdapter(prefer_live=False)
    obs = adapter.observations(series_id="DGS3MO")
    assert len(obs) == 1
    assert isinstance(obs[0], PublicDataObservation)
    assert obs[0].value is not None
    movement = BusinessMovement(
        metric="operating_cash_yield",
        prior=__import__("decimal").Decimal("0.00"),
        current=__import__("decimal").Decimal("0.00"),
        change_pct=__import__("decimal").Decimal("0.00"),
    )
    paired_obs, paired_move = adapter.contextualize(obs[0], movement)
    interp = adapter.interpretation_placeholder(paired_obs, paired_move)
    assert isinstance(interp, ModelInterpretation)
    assert interp.is_generated is False
    assert "PUBLIC DATA OBSERVATION" in interp.narrative
    assert "causation is not asserted" in interp.narrative
    assert not hasattr(obs[0], "narrative")


def test_elastic_mappings_preserve_source_id() -> None:
    for name in ALL_INDICES:
        props = INDEX_MAPPINGS[name]["mappings"]["properties"]
        assert props["source_id"]["type"] == "keyword"
        assert props["company_id"]["type"] == "keyword"
