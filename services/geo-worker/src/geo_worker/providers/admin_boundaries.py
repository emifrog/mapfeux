"""Connecteur des limites administratives.

Référence : cahier §9.5 et §16.7, ADR-017 sur le choix de la source.

Source : API Découpage administratif d'Etalab, qui sert la donnée IGN ADMIN
EXPRESS en GeoJSON, département par département.

Ce module ne fait que normaliser. La validation géométrique, la conversion en
MultiPolygon et le calcul du point représentatif appartiennent à PostGIS, qui
les fait mieux et sans charger les polygones en mémoire Python.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from geo_worker.providers.models import AdministrativeUnit, MunicipalityBoundary

PROVIDER_KEY = "ign_admin_express"

BASE_URL = "https://geo.api.gouv.fr"

# Champs demandés à l'API. `contour` est réclamé séparément par `geometry`.
_FIELDS = "nom,code,codesPostaux,centre,surface,codeDepartement"

_INSEE_PATTERN = re.compile(r"^(?:\d{5}|2[AB]\d{3})$")

# Départements métropolitains et Corse — la vague A. Les DROM ont trois
# chiffres et arrivent en vague B, avec leurs fuseaux et leurs fonds.
_DEPARTMENT_PATTERN = re.compile(r"^(?:\d{2}|2[AB])$")

_REGION_PATTERN = re.compile(r"^\d{2}$")

# La surface est publiée en hectares.
_HECTARES_PER_KM2 = 100.0


class BoundaryParseError(ValueError):
    """Entité inexploitable : rejetée et comptée, sans interrompre l'import."""


def source_version(now: datetime | None = None) -> str:
    """Millésime enregistré avec chaque commune.

    L'API n'expose pas la version du COG qu'elle sert : on consigne le
    fournisseur et la date d'import, en assumant que ce n'est pas un millésime
    officiel (ADR-017).
    """
    moment = now or datetime.now(UTC)
    return f"etalab-geo-api:{moment.date().isoformat()}"


def _postal_codes(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(str(code).strip() for code in raw if str(code).strip() != "")


def _centroid(properties: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extrait le centre officiel s'il est fourni.

    À défaut, PostGIS calculera un point garanti à l'intérieur du polygone.
    Un centroïde géométrique peut tomber hors de la commune sur les formes
    concaves ou les communes littorales très découpées.
    """
    centre = properties.get("centre")
    if not isinstance(centre, dict):
        return None, None

    coordinates = centre.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None, None

    try:
        lon, lat = float(coordinates[0]), float(coordinates[1])
    except (TypeError, ValueError):
        return None, None

    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None, None
    return lon, lat


def _area_km2(properties: dict[str, Any]) -> float | None:
    surface = properties.get("surface")
    if surface is None:
        return None
    try:
        hectares = float(surface)
    except (TypeError, ValueError):
        return None
    return None if hectares <= 0 else hectares / _HECTARES_PER_KM2


def parse_feature(feature: dict[str, Any], version: str) -> MunicipalityBoundary:
    """Normalise une entité GeoJSON en limite communale."""
    properties = feature.get("properties")
    if not isinstance(properties, dict):
        raise BoundaryParseError("Entité sans propriétés.")

    insee = str(properties.get("code", "")).strip().upper()
    if _INSEE_PATTERN.match(insee) is None:
        raise BoundaryParseError(f"Code INSEE invalide : {insee!r}")

    name = str(properties.get("nom", "")).strip()
    if name == "":
        raise BoundaryParseError(f"Commune {insee} sans nom.")

    department = str(properties.get("codeDepartement", "")).strip().upper()
    if department == "":
        # Le code département se déduit du code INSEE : deux premiers
        # caractères, la Corse utilisant 2A et 2B.
        department = insee[:2]

    geometry = feature.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") not in {
        "Polygon",
        "MultiPolygon",
    }:
        raise BoundaryParseError(f"Commune {insee} sans géométrie surfacique exploitable.")

    lon, lat = _centroid(properties)

    return MunicipalityBoundary(
        insee_code=insee,
        name=name,
        department_code=department,
        postal_codes=_postal_codes(properties.get("codesPostaux")),
        geometry_geojson=json.dumps(geometry, separators=(",", ":")),
        centroid_lon=lon,
        centroid_lat=lat,
        area_km2=_area_km2(properties),
        source_version=version,
    )


def parse_feature_collection(
    payload: dict[str, Any], version: str
) -> tuple[list[MunicipalityBoundary], list[str]]:
    """Normalise une collection complète.

    Retourne les communes valides et les motifs de rejet. Une entité
    inexploitable est comptée puis ignorée : elle ne doit pas faire échouer
    l'import d'un département entier (§16.2).
    """
    features = payload.get("features")
    if not isinstance(features, list):
        raise BoundaryParseError("Réponse sans collection d'entités.")

    boundaries: list[MunicipalityBoundary] = []
    rejections: list[str] = []

    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            rejections.append(f"entité {index} : format inattendu")
            continue
        try:
            boundaries.append(parse_feature(feature, version))
        except BoundaryParseError as exc:
            rejections.append(f"entité {index} : {exc}")

    return boundaries, rejections


def parse_regions_payload(payload: Any) -> tuple[list[AdministrativeUnit], list[str]]:
    """Normalise la liste des régions. Une entrée invalide est comptée, pas fatale."""
    if not isinstance(payload, list):
        raise BoundaryParseError("Réponse régions : liste attendue.")

    units: list[AdministrativeUnit] = []
    rejections: list[str] = []
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            rejections.append(f"région {index} : format inattendu")
            continue
        code = str(entry.get("code", "")).strip()
        name = str(entry.get("nom", "")).strip()
        if _REGION_PATTERN.match(code) is None:
            rejections.append(f"région {index} : code invalide {code!r}")
            continue
        if name == "":
            rejections.append(f"région {code} : sans nom")
            continue
        units.append(AdministrativeUnit(code=code, name=name, region_code=None))
    return units, rejections


def parse_departments_payload(payload: Any) -> tuple[list[AdministrativeUnit], list[str]]:
    """Normalise la liste des départements métropolitains."""
    if not isinstance(payload, list):
        raise BoundaryParseError("Réponse départements : liste attendue.")

    units: list[AdministrativeUnit] = []
    rejections: list[str] = []
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            rejections.append(f"département {index} : format inattendu")
            continue
        code = str(entry.get("code", "")).strip().upper()
        name = str(entry.get("nom", "")).strip()
        region = str(entry.get("codeRegion", "")).strip()
        if _DEPARTMENT_PATTERN.match(code) is None:
            rejections.append(f"département {index} : code invalide {code!r}")
            continue
        if name == "":
            rejections.append(f"département {code} : sans nom")
            continue
        if _REGION_PATTERN.match(region) is None:
            rejections.append(f"département {code} : région invalide {region!r}")
            continue
        units.append(AdministrativeUnit(code=code, name=name, region_code=region))
    return units, rejections


class AdminBoundariesProvider:
    """Adaptateur HTTP. Cahier §30.1 : le métier ne connaît que les modèles."""

    key = PROVIDER_KEY

    def __init__(self, client: httpx.Client, base_url: str = BASE_URL) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    def fetch_municipalities(
        self, department_code: str, version: str | None = None
    ) -> tuple[list[MunicipalityBoundary], list[str]]:
        """Récupère les communes d'un département avec leur contour."""
        response = self._client.get(
            f"{self._base_url}/departements/{department_code}/communes",
            params={"fields": _FIELDS, "format": "geojson", "geometry": "contour"},
            timeout=120.0,
        )
        response.raise_for_status()

        return parse_feature_collection(response.json(), version or source_version())

    def fetch_regions(self) -> tuple[list[AdministrativeUnit], list[str]]:
        """Liste des régions — codes et noms seulement, sans géométrie."""
        response = self._client.get(
            f"{self._base_url}/regions",
            params={"fields": "nom,code"},
            timeout=60.0,
        )
        response.raise_for_status()
        return parse_regions_payload(response.json())

    def fetch_departments(self) -> tuple[list[AdministrativeUnit], list[str]]:
        """Départements métropolitains et Corse, avec leur région (`zone=metro`)."""
        response = self._client.get(
            f"{self._base_url}/departements",
            params={"fields": "nom,code,codeRegion", "zone": "metro"},
            timeout=60.0,
        )
        response.raise_for_status()
        return parse_departments_payload(response.json())
