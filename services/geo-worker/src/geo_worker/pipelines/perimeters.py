"""Périmètres versionnés des événements — `fire.event_perimeters`.

Référence : cahier v2.1 §13.23 et FR-090 à FR-096 ; plan J9.

Un périmètre est une **version**, jamais un remplacement : chaque import
s'ajoute, chaîné à la version précédente de même nature et de même source
(`supersedes_id`), et la relecture les rejouera (FR-094). La surface est
recalculée chez nous — `ST_Area` sur géographie, l'ellipsoïde WGS84 — et la
méthode consignée (FR-095) ; la surface annoncée par la source est conservée
à côté, jamais confondue avec la nôtre.

La géométrie d'entrée est du GeoJSON : réparée si besoin (`make_valid`),
réduite à sa part surfacique, refusée si rien de surfacique ne reste — un
périmètre-point n'est pas un périmètre.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.validation import make_valid

from geo_worker.logging import get_logger

logger = get_logger(__name__)

#: Méthode de recalcul de surface, consignée avec chaque version (FR-095).
AREA_METHOD = "ST_Area sur géographie WGS84 (ellipsoïde), hectares arrondis au centième"


class PerimeterError(RuntimeError):
    """Géométrie inexploitable — rien n'est enregistré sur un doute."""


def _polygonal(geometry: BaseGeometry) -> list[Polygon]:
    """La part surfacique d'une géométrie, quelle que soit son enveloppe."""
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    if hasattr(geometry, "geoms"):
        polygons: list[Polygon] = []
        for part in geometry.geoms:
            polygons.extend(_polygonal(part))
        return polygons
    return []


def geojson_to_multipolygon_wkt(payload: dict[str, Any]) -> str:
    """Un GeoJSON — géométrie, Feature ou FeatureCollection — en MultiPolygon WKT.

    Les géométries invalides sont réparées par `make_valid` avant toute
    décision : un anneau auto-intersecté est un défaut d'export courant, pas
    une raison de perdre un périmètre. Ce qui n'est pas surfacique après
    réparation est écarté ; s'il ne reste rien, l'import est refusé (§13.23,
    contrainte de géométrie non vide).
    """
    kind = payload.get("type")
    if kind == "FeatureCollection":
        geometries = [feature.get("geometry") for feature in payload.get("features", [])]
    elif kind == "Feature":
        geometries = [payload.get("geometry")]
    else:
        geometries = [payload]

    parts: list[Polygon] = []
    for geometry in geometries:
        if geometry is None:
            continue
        repaired = make_valid(shape(geometry))
        parts.extend(_polygonal(repaired))

    if not parts:
        raise PerimeterError("Aucune surface dans ce GeoJSON : un périmètre est un polygone.")

    merged = unary_union(parts)
    polygons = _polygonal(merged)
    if not polygons:
        raise PerimeterError("La fusion des surfaces n'a rien laissé d'exploitable.")
    return str(MultiPolygon(polygons).wkt)


def store_perimeter(
    conn: psycopg.Connection[Any],
    *,
    event_id: UUID,
    source_key: str,
    perimeter_type: str,
    valid_at: datetime,
    published_at: datetime | None,
    geometry_wkt: str,
    source_area_ha: float | None,
    resolution_m: float | None,
    confidence: str,
    raw_payload: dict[str, Any],
) -> tuple[UUID, float, UUID | None]:
    """Enregistre une version de périmètre, chaînée à la précédente.

    Retourne (id, surface recalculée en hectares, version remplacée). La
    surface est calculée par la base, sur la géométrie réellement stockée —
    pas sur ce que l'appelant croit avoir envoyé.
    """
    source = conn.execute(
        "select id from ingest.data_sources where key = %(key)s",
        {"key": source_key},
    ).fetchone()
    if source is None:
        raise PerimeterError(f"Source inconnue au registre : {source_key!r}")

    previous = conn.execute(
        """
        select id from fire.event_perimeters
        where event_id = %(event_id)s
          and perimeter_type = %(type)s
          and source_id = %(source_id)s
        order by valid_at desc, imported_at desc
        limit 1
        """,
        {"event_id": event_id, "type": perimeter_type, "source_id": source[0]},
    ).fetchone()
    supersedes = None if previous is None else UUID(str(previous[0]))

    with conn.cursor() as cur:
        cur.execute(
            """
            with incoming as (
              select extensions.st_multi(
                extensions.st_geomfromtext(%(wkt)s, 4326)
              ) as geom
            )
            insert into fire.event_perimeters
              (event_id, source_id, perimeter_type, valid_at, published_at,
               geometry, area_ha, source_area_ha, resolution_m,
               confidence_level, method, supersedes_id, raw_payload)
            select
              %(event_id)s, %(source_id)s, %(type)s, %(valid_at)s, %(published_at)s,
              incoming.geom,
              round((extensions.st_area(incoming.geom::extensions.geography) / 10000)::numeric, 2),
              %(source_area)s, %(resolution)s, %(confidence)s, %(method)s,
              %(supersedes)s, %(raw)s
            from incoming
            returning id, area_ha
            """,
            {
                "wkt": geometry_wkt,
                "event_id": event_id,
                "source_id": source[0],
                "type": perimeter_type,
                "valid_at": valid_at,
                "published_at": published_at,
                "source_area": source_area_ha,
                "resolution": resolution_m,
                "confidence": confidence,
                "method": AREA_METHOD,
                "supersedes": supersedes,
                "raw": json.dumps(raw_payload, ensure_ascii=False, default=str),
            },
        )
        row = cur.fetchone()
        assert row is not None  # returning sur insert : toujours une ligne
        perimeter_id, area_ha = UUID(str(row[0])), float(row[1])

    logger.info(
        "perimeter.stored",
        perimeter_id=str(perimeter_id),
        perimeter_type=perimeter_type,
        area_ha=area_ha,
        supersedes=None if supersedes is None else str(supersedes),
    )
    return perimeter_id, area_ha, supersedes


__all__ = [
    "AREA_METHOD",
    "PerimeterError",
    "geojson_to_multipolygon_wkt",
    "store_perimeter",
]
