"""Insertion des détections thermiques.

Référence : cahier §16.3, §17.1 et FR-033.

L'insertion est idempotente par construction : la clé fournisseur est un hash
des seuls attributs qui identifient l'observation. Rejouer un import ne crée
donc aucun doublon, ce qui rend la reprise après incident sans danger.

Les champs enrichis plus tard — source thermique connue, visibilité — ne sont
jamais écrasés par un réimport : ce sont des décisions prises en aval, que la
source ne connaît pas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from geo_worker.logging import get_logger
from geo_worker.providers.models import ThermalDetection

logger = get_logger(__name__)


@dataclass
class DetectionInsertResult:
    inserted: int = 0
    already_known: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.already_known


def ensure_partitions(conn: psycopg.Connection[Any], detections: list[ThermalDetection]) -> None:
    """Crée les partitions mensuelles couvrant le lot.

    Sans elles, les lignes tombent dans la partition par défaut. Elles n'y sont
    pas perdues, mais l'ajout ultérieur d'une partition nominale devient
    coûteux : PostgreSQL doit alors scanner la partition par défaut sous verrou
    exclusif pour vérifier qu'aucune ligne n'y appartient (ADR-015).
    """
    months = {detection.acquired_at.date().replace(day=1) for detection in detections}
    with conn.cursor() as cur:
        for month in sorted(months):
            cur.execute("select fire.ensure_detection_partition(%s)", (month,))


def insert_detections(
    conn: psycopg.Connection[Any],
    *,
    detections: list[ThermalDetection],
    source_key: str,
    import_run_id: str | None,
) -> DetectionInsertResult:
    """Insère un lot de détections. L'appelant gère la transaction."""
    result = DetectionInsertResult()
    if not detections:
        return result

    ensure_partitions(conn, detections)

    with conn.cursor() as cur:
        cur.execute("select id from ingest.data_sources where key = %s", (source_key,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Source inconnue : {source_key}")
        source_id = row[0]

        for detection in detections:
            cur.execute(
                """
                insert into fire.detections (
                  provider_key, source_id, import_run_id, sensor, satellite, product_version,
                  acquired_at, location, latitude, longitude,
                  confidence_raw, confidence_score, frp_mw, brightness, day_night,
                  scan_km, track_km, thermal_type, raw_payload
                )
                values (
                  %(provider_key)s, %(source_id)s, %(import_run_id)s, %(sensor)s,
                  %(satellite)s, %(product_version)s, %(acquired_at)s,
                  extensions.st_setsrid(
                    extensions.st_makepoint(%(longitude)s::double precision,
                                            %(latitude)s::double precision),
                    4326
                  ),
                  %(latitude)s::double precision, %(longitude)s::double precision,
                  %(confidence_raw)s, %(confidence_score)s::numeric, %(frp_mw)s::numeric,
                  %(brightness)s::numeric, %(day_night)s, %(scan_km)s::numeric,
                  %(track_km)s::numeric, %(thermal_type)s, %(raw_payload)s
                )
                -- La même observation republiée par FIRMS ne produit rien.
                -- On ne met pas à jour : la donnée brute est immuable (ADR-004),
                -- et les champs enrichis en aval ne doivent pas être écrasés.
                on conflict (provider_key, acquired_at) do nothing
                """,
                {
                    "provider_key": detection.provider_key,
                    "source_id": source_id,
                    "import_run_id": import_run_id,
                    "sensor": detection.sensor,
                    "satellite": detection.satellite,
                    "product_version": detection.product_version,
                    "acquired_at": detection.acquired_at,
                    "latitude": detection.latitude,
                    "longitude": detection.longitude,
                    "confidence_raw": detection.confidence_raw,
                    "confidence_score": detection.confidence_score,
                    "frp_mw": detection.frp_mw,
                    "brightness": detection.brightness,
                    "day_night": detection.day_night,
                    "scan_km": detection.scan_km,
                    "track_km": detection.track_km,
                    "thermal_type": detection.thermal_type,
                    "raw_payload": Jsonb(detection.raw_payload),
                },
            )
            if cur.rowcount == 1:
                result.inserted += 1
            else:
                result.already_known += 1

    logger.info(
        "detections.inserted",
        source=source_key,
        inserted=result.inserted,
        already_known=result.already_known,
    )
    return result


def mark_known_thermal_sources(conn: psycopg.Connection[Any], since: datetime | None = None) -> int:
    """Rattache les détections proches d'une source thermique connue.

    Référence : cahier FR-036 et §17.7. Une correspondance **classe** la
    détection, elle ne la supprime pas : une torchère peut se trouver à côté
    d'un vrai départ de feu, et effacer l'observation reviendrait à décider à la
    place de l'utilisateur.
    """
    window = since or datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    with conn.cursor() as cur:
        cur.execute(
            """
            update fire.detections d
            set known_source_id = k.id
            from fire.known_thermal_sources k
            where d.known_source_id is null
              and d.acquired_at >= %(since)s
              and k.is_active
              and extensions.st_dwithin(
                d.location::extensions.geography,
                k.location::extensions.geography,
                k.match_radius_m
              )
            """,
            {"since": window},
        )
        return cur.rowcount
