"""Connecteur NASA FIRMS.

Référence : cahier §9.1, §16.3 et §17.1.

Deux règles structurent ce module :

1. Une détection n'est jamais interprétée. Le connecteur normalise des champs,
   il ne conclut pas qu'un incendie est en cours (§9.1).
2. La clé d'idempotence est calculée ici et nulle part ailleurs. Elle est la
   seule protection contre les doublons au rejeu d'un import (FR-033), et sa
   définition ne doit pas diverger entre le worker et les tests.
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any

from geo_worker.providers.models import ThermalDetection

PROVIDER = "nasa_firms"

# Précision retenue pour la clé d'idempotence. FIRMS publie 5 décimales ; figer
# l'arrondi évite qu'une variation de formatage côté fournisseur ne produise une
# clé différente pour la même observation.
_COORD_PRECISION = 5

# VIIRS publie une confiance qualitative, MODIS un pourcentage. Les deux sont
# ramenés à un score interne 0-1, la valeur brute restant conservée.
_VIIRS_CONFIDENCE = {"l": 0.25, "n": 0.60, "h": 0.90}

_SENSOR_BY_INSTRUMENT = {
    "VIIRS": "VIIRS",
    "MODIS": "MODIS",
}


class FirmsParseError(ValueError):
    """Ligne inexploitable : elle est rejetée et comptée, sans interrompre l'import."""


def build_provider_key(
    *,
    product: str,
    satellite: str,
    sensor: str,
    acquired_at: datetime,
    latitude: float,
    longitude: float,
    version: str | None,
) -> str:
    """Calcule la clé idempotente d'une détection.

    Le hash porte sur les seuls attributs qui identifient l'observation. Les
    champs enrichis ultérieurement (score, source thermique connue) en sont
    volontairement exclus : ils changent, l'observation non.
    """
    if acquired_at.tzinfo is None:
        raise FirmsParseError("acquired_at doit être conscient du fuseau et exprimé en UTC.")

    parts = (
        PROVIDER,
        product,
        satellite,
        sensor,
        acquired_at.astimezone(UTC).isoformat(),
        f"{latitude:.{_COORD_PRECISION}f}",
        f"{longitude:.{_COORD_PRECISION}f}",
        version or "",
    )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def parse_acquisition_time(acq_date: str, acq_time: str) -> datetime:
    """Combine `acq_date` (YYYY-MM-DD) et `acq_time` (HHMM) en UTC.

    FIRMS transmet l'heure sans séparateur et parfois sans zéro initial :
    « 45 » signifie 00:45.
    """
    try:
        # Seule la partie date est retenue ; le fuseau est appliqué plus bas.
        date_part = datetime.strptime(acq_date.strip(), "%Y-%m-%d").date()  # noqa: DTZ007
    except ValueError as exc:
        raise FirmsParseError(f"Date d'acquisition illisible : {acq_date!r}") from exc

    raw_time = acq_time.strip().replace(":", "")
    if not raw_time.isdigit() or len(raw_time) > 4:
        raise FirmsParseError(f"Heure d'acquisition illisible : {acq_time!r}")

    padded = raw_time.zfill(4)
    hours, minutes = int(padded[:2]), int(padded[2:])
    if hours > 23 or minutes > 59:
        raise FirmsParseError(f"Heure d'acquisition hors bornes : {acq_time!r}")

    return datetime(date_part.year, date_part.month, date_part.day, hours, minutes, tzinfo=UTC)


def normalize_confidence(raw: str | None, sensor: str) -> tuple[str | None, float | None]:
    """Ramène la confiance fournisseur à un score interne 0-1.

    Retourne le couple (valeur brute conservée, score normalisé). Un format
    inattendu produit un score nul plutôt qu'une erreur : la détection reste
    valide, seule sa pondération est inconnue.
    """
    if raw is None or raw.strip() == "":
        return None, None

    value = raw.strip()

    if sensor == "VIIRS":
        return value, _VIIRS_CONFIDENCE.get(value.lower())

    try:
        percent = float(value)
    except ValueError:
        return value, None

    if not 0 <= percent <= 100:
        return value, None
    return value, round(percent / 100, 3)


def _optional_float(row: dict[str, str], key: str) -> float | None:
    value = row.get(key, "").strip()
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _required_float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "").strip()
    try:
        return float(value)
    except ValueError as exc:
        raise FirmsParseError(f"Champ numérique obligatoire absent ou invalide : {key}") from exc


def parse_row(row: dict[str, str], *, product: str) -> ThermalDetection:
    """Normalise une ligne CSV FIRMS.

    `product` est le jeu demandé (VIIRS_NOAA20_NRT, MODIS_NRT, …) : il fait
    partie de la clé d'idempotence car un même pixel peut être publié dans
    plusieurs jeux.
    """
    instrument = row.get("instrument", "").strip().upper()
    sensor = _SENSOR_BY_INSTRUMENT.get(instrument, instrument or "UNKNOWN")

    latitude = _required_float(row, "latitude")
    longitude = _required_float(row, "longitude")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise FirmsParseError(f"Coordonnées hors bornes : {latitude}, {longitude}")

    acquired_at = parse_acquisition_time(row.get("acq_date", ""), row.get("acq_time", ""))
    satellite = row.get("satellite", "").strip() or "UNKNOWN"
    version = row.get("version", "").strip() or None

    confidence_raw, confidence_score = normalize_confidence(row.get("confidence"), sensor)

    # MODIS et VIIRS ne nomment pas la température de brillance de la même façon.
    brightness = _optional_float(row, "brightness")
    if brightness is None:
        brightness = _optional_float(row, "bright_ti4")

    day_night = row.get("daynight", "").strip() or None
    if day_night is not None:
        day_night = day_night.upper()[:1]
        if day_night not in {"D", "N"}:
            day_night = None

    return ThermalDetection(
        provider_key=build_provider_key(
            product=product,
            satellite=satellite,
            sensor=sensor,
            acquired_at=acquired_at,
            latitude=latitude,
            longitude=longitude,
            version=version,
        ),
        sensor=sensor,
        satellite=satellite,
        product_version=version,
        acquired_at=acquired_at,
        latitude=latitude,
        longitude=longitude,
        confidence_raw=confidence_raw,
        confidence_score=confidence_score,
        frp_mw=_optional_float(row, "frp"),
        brightness=brightness,
        day_night=day_night,
        scan_km=_optional_float(row, "scan"),
        track_km=_optional_float(row, "track"),
        thermal_type=(row.get("type", "").strip() or None),
        raw_payload=dict(row),
    )


def parse_csv(content: str, *, product: str) -> tuple[list[ThermalDetection], list[str]]:
    """Normalise un export CSV complet.

    Retourne les détections valides et les motifs de rejet. Une ligne
    inexploitable est comptée puis ignorée : elle ne doit pas faire échouer
    l'import entier (§16.2, « erreur métier isolée »).
    """
    detections: list[ThermalDetection] = []
    rejections: list[str] = []

    reader: Iterable[dict[str, Any]] = csv.DictReader(content.splitlines())

    for index, raw_row in enumerate(reader, start=2):  # ligne 1 = en-têtes
        row = {key: (value or "") for key, value in raw_row.items() if key is not None}
        try:
            detections.append(parse_row(row, product=product))
        except FirmsParseError as exc:
            rejections.append(f"ligne {index} : {exc}")

    return detections, rejections


def deduplicate(detections: Iterable[ThermalDetection]) -> Iterator[ThermalDetection]:
    """Élimine les doublons d'un même lot, la première occurrence gagnant.

    FIRMS peut republier une observation d'un appel à l'autre ; la contrainte
    d'unicité en base tranche en dernier ressort, mais dédoublonner en amont
    évite des transactions inutiles.
    """
    seen: set[str] = set()
    for detection in detections:
        if detection.provider_key in seen:
            continue
        seen.add(detection.provider_key)
        yield detection
