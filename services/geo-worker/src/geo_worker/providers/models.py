"""Modèles normalisés échangés entre connecteurs et pipelines.

Référence : cahier §13.5 et §16.1.

Ces objets sont la frontière entre le format d'un fournisseur et le schéma de la
base. Un changement de colonne chez NASA ou Météo-France doit se corriger dans
l'adaptateur, sans toucher à ces définitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Emprise géographique en degrés décimaux, EPSG:4326."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def __post_init__(self) -> None:
        if self.min_lon >= self.max_lon or self.min_lat >= self.max_lat:
            raise ValueError("Emprise invalide : bornes inversées.")
        if not (-180 <= self.min_lon <= 180 and -180 <= self.max_lon <= 180):
            raise ValueError("Longitude hors bornes.")
        if not (-90 <= self.min_lat <= 90 and -90 <= self.max_lat <= 90):
            raise ValueError("Latitude hors bornes.")

    def as_firms_area(self) -> str:
        """Format attendu par l'API Area de FIRMS : ouest,sud,est,nord."""
        return f"{self.min_lon},{self.min_lat},{self.max_lon},{self.max_lat}"


@dataclass(frozen=True, slots=True)
class ThermalDetection:
    """Détection thermique normalisée, prête pour `fire.detections`."""

    provider_key: str
    sensor: str
    satellite: str
    product_version: str | None
    # Heure d'observation satellitaire, toujours en UTC (FR-032).
    acquired_at: datetime
    latitude: float
    longitude: float
    confidence_raw: str | None
    confidence_score: float | None
    frp_mw: float | None
    brightness: float | None
    day_night: str | None
    scan_km: float | None
    track_km: float | None
    thermal_type: str | None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AdministrativeUnit:
    """Région ou département du découpage administratif, sans géométrie.

    La géométrie n'est volontairement pas transportée : les contours des
    territoires sont construits en base par union des communes déjà
    importées — une seule source de vérité géométrique, pas deux tracés qui
    divergent le long des mêmes frontières.
    """

    code: str
    name: str
    #: Code de la région d'appartenance — None pour une région elle-même.
    region_code: str | None


@dataclass(frozen=True, slots=True)
class MunicipalityBoundary:
    """Limite communale normalisée, prête pour `geo.municipalities`."""

    insee_code: str
    name: str
    department_code: str
    postal_codes: tuple[str, ...]
    # Géométrie GeoJSON sérialisée : la validation et la conversion en
    # MultiPolygon sont faites par PostGIS, qui le fait mieux et sans charger
    # la géométrie en mémoire Python.
    geometry_geojson: str
    centroid_lon: float | None
    centroid_lat: float | None
    area_km2: float | None
    source_version: str


@dataclass(frozen=True, slots=True)
class WindSample:
    """Vent en un point et une échéance."""

    longitude: float
    latitude: float
    valid_at: datetime
    u_ms: float
    v_ms: float
    speed_ms: float
    # Direction météorologique : d'où vient le vent, en degrés depuis le nord.
    direction_deg: float


@dataclass(frozen=True, slots=True)
class WindField:
    model: str
    run_at: datetime
    valid_at: datetime
    samples: list[WindSample]


@dataclass(frozen=True, slots=True)
class AirQualityGrid:
    model: str
    pollutant: str
    unit: str
    run_at: datetime
    valid_at: datetime
    resolution_deg: float
    asset_path: str


@dataclass(frozen=True, slots=True)
class RadarFrame:
    product: str
    acquired_at: datetime
    projection: str
    asset_path: str
    checksum: str
