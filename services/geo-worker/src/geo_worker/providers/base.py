"""Interfaces fournisseurs génériques.

Référence : cahier §30.1.

Le MVP n'a qu'une implémentation par famille, mais les contrats sont posés dès
maintenant : la migration annoncée des portails Météo-France (§9.2) et l'arrivée
des AASQA en phase 2 (FR-085) ne doivent toucher qu'un adaptateur, jamais le
métier.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from geo_worker.providers.models import (
    AirQualityGrid,
    BoundingBox,
    RadarFrame,
    ThermalDetection,
    WindField,
)


@runtime_checkable
class ThermalDetectionProvider(Protocol):
    """Source de détections thermiques (FIRMS aujourd'hui)."""

    key: str

    async def fetch_detections(
        self, bbox: BoundingBox, since: datetime
    ) -> list[ThermalDetection]: ...


@runtime_checkable
class WeatherProvider(Protocol):
    """Source de champs de vent (AROME aujourd'hui)."""

    key: str

    async def latest_run(self) -> datetime | None: ...

    async def fetch_wind_field(self, bbox: BoundingBox, valid_at: datetime) -> WindField: ...


@runtime_checkable
class AirQualityProvider(Protocol):
    """Source de qualité de l'air (CAMS aujourd'hui, AASQA en phase 2)."""

    key: str

    async def fetch_grid(self, pollutant: str, valid_at: datetime) -> AirQualityGrid: ...


@runtime_checkable
class RadarProvider(Protocol):
    """Source d'images radar de précipitations."""

    key: str

    async def fetch_latest_frame(self) -> RadarFrame | None: ...


@runtime_checkable
class AdministrativeBoundaryProvider(Protocol):
    """Source de limites administratives (IGN ADMIN EXPRESS aujourd'hui)."""

    key: str

    async def available_versions(self) -> list[str]: ...
