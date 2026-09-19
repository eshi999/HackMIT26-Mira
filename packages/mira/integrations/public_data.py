"""Public economic data. Observations are not interpretations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict

from mira.integrations.base import AdapterStatus

TREASURY_AVG_INTEREST = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
    "v2/accounting/od/avg_interest_rates"
)


class PublicDataObservation(BaseModel):
    """A sourced public datapoint. This is not a recommendation."""

    model_config = ConfigDict(frozen=True)

    source: str
    series_id: str
    as_of: date
    value: Decimal
    unit: str
    title: str
    uri: str | None = None
    provider: str = "demo"


class ModelInterpretation(BaseModel):
    """Kept separate from PublicDataObservation on purpose.

    Agents may later write this. Deterministic code must not blend it into the observation.
    """

    model_config = ConfigDict(frozen=True)

    observation_series_id: str
    observation_as_of: date
    observation_value: Decimal
    business_metric: str
    business_value: Decimal
    narrative: str
    is_generated: bool = False
    engine: str = "none"


class BusinessMovement(BaseModel):
    model_config = ConfigDict(frozen=True)

    metric: str
    prior: Decimal
    current: Decimal
    change_pct: Decimal


class PublicDataProvider(Protocol):
    name: str

    def status(self) -> AdapterStatus: ...

    def observations(self, *, series_id: str | None = None) -> tuple[PublicDataObservation, ...]: ...


DEMO_SERIES: tuple[PublicDataObservation, ...] = (
    PublicDataObservation(
        source="FRED",
        series_id="DGS3MO",
        as_of=date(2026, 9, 18),
        value=Decimal("4.220000"),
        unit="percent",
        title="3-month Treasury yield",
        uri="https://fred.stlouisfed.org/series/DGS3MO",
        provider="demo",
    ),
    PublicDataObservation(
        source="FRED",
        series_id="CPIAUCSL",
        as_of=date(2026, 8, 31),
        value=Decimal("323.400000"),
        unit="index",
        title="CPI-U (seeded snapshot)",
        uri="https://fred.stlouisfed.org/series/CPIAUCSL",
        provider="demo",
    ),
    PublicDataObservation(
        source="TreasuryFiscalData",
        series_id="AVG_INTEREST_BILLS",
        as_of=date(2026, 8, 31),
        value=Decimal("4.180000"),
        unit="percent",
        title="Treasury Bills average interest rate (seeded snapshot)",
        uri=TREASURY_AVG_INTEREST,
        provider="demo",
    ),
)


class DemoPublicDataProvider:
    name = "public_data_demo"

    def status(self) -> AdapterStatus:
        return AdapterStatus.DEMO

    def observations(self, *, series_id: str | None = None) -> tuple[PublicDataObservation, ...]:
        if series_id is None:
            return DEMO_SERIES
        return tuple(row for row in DEMO_SERIES if row.series_id == series_id)


class TreasuryFiscalDataProvider:
    """Live Treasury Fiscal Data API. No API key required. Falls back to demo on failure."""

    name = "treasury_fiscal_data"

    def __init__(self, timeout: float = 8.0) -> None:
        self.timeout = timeout
        self._last_error: str | None = None
        self._live = False

    def status(self) -> AdapterStatus:
        return AdapterStatus.LIVE if self._live else AdapterStatus.DEMO

    def observations(self, *, series_id: str | None = None) -> tuple[PublicDataObservation, ...]:
        try:
            params = {
                "filter": "security_desc:eq:Treasury Bills",
                "sort": "-record_date",
                "page[size]": "1",
            }
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(TREASURY_AVG_INTEREST, params=params)
                response.raise_for_status()
                payload = response.json()
            rows = payload.get("data") or []
            if not rows:
                raise ValueError("Treasury Fiscal Data returned no rows")
            row = rows[0]
            obs = PublicDataObservation(
                source="TreasuryFiscalData",
                series_id="AVG_INTEREST_BILLS",
                as_of=date.fromisoformat(str(row["record_date"])),
                value=Decimal(str(row.get("avg_interest_rate_amt", "0"))),
                unit="percent",
                title="Treasury Bills average interest rate",
                uri=TREASURY_AVG_INTEREST,
                provider="treasury_fiscal_data",
            )
            self._live = True
            if series_id and series_id != obs.series_id:
                return ()
            return (obs,)
        except Exception as exc:  # network, parse, timeout
            self._last_error = str(exc)
            self._live = False
            demo = DemoPublicDataProvider().observations(series_id=series_id or "AVG_INTEREST_BILLS")
            return demo


class PublicDataAdapter:
    name = "public_data"

    def __init__(self, *, prefer_live: bool = True) -> None:
        self.demo = DemoPublicDataProvider()
        self.live = TreasuryFiscalDataProvider() if prefer_live else None

    def status(self) -> AdapterStatus:
        if self.live is not None:
            return self.live.status()
        return AdapterStatus.DEMO

    def observations(self, *, series_id: str | None = None, live: bool = False) -> tuple[PublicDataObservation, ...]:
        if live and self.live is not None:
            return self.live.observations(series_id=series_id)
        return self.demo.observations(series_id=series_id)

    def contextualize(
        self,
        observation: PublicDataObservation,
        movement: BusinessMovement,
    ) -> tuple[PublicDataObservation, BusinessMovement]:
        """Pair an observation with an internal movement. Does not interpret."""
        return observation, movement

    def interpretation_placeholder(
        self,
        observation: PublicDataObservation,
        movement: BusinessMovement,
    ) -> ModelInterpretation:
        """Factual pairing only. Agents may later replace narrative; this is not a score."""
        return ModelInterpretation(
            observation_series_id=observation.series_id,
            observation_as_of=observation.as_of,
            observation_value=observation.value,
            business_metric=movement.metric,
            business_value=movement.current,
            narrative=(
                f"PUBLIC DATA OBSERVATION: {observation.title}={observation.value} {observation.unit} "
                f"as of {observation.as_of} ({observation.source}). "
                f"BUSINESS MOVEMENT: {movement.metric} {movement.prior} → {movement.current} "
                f"({movement.change_pct}%). These two facts are listed together; causation is not asserted."
            ),
            is_generated=False,
            engine="public_data.pairing",
        )
