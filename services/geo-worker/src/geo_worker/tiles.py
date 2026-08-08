"""Arithmétique des tuiles Web Mercator et plan de génération PMTiles.

Référence : cahier §21.1, §21.3 et §9.5.

Ce module ne touche ni la base ni le réseau : il calcule les emprises de
tuiles, découpe le travail en bandes de colonnes — chaque bande produit des
tuiles **complètes**, jamais une tuile à cheval sur deux requêtes — et fixe le
plan zoom par zoom. Le découpage réel des géométries appartient à PostGIS
(`ST_AsMVTGeom`), l'assemblage du fichier à `pmtiles`.

Le plan suit la stratégie de zoom du cahier §21.3 : régions aux niveaux
nationaux, départements jusqu'au niveau local, communes seulement à partir du
zoom 10 — « les limites communales ne sont chargées qu'à un niveau de zoom
pertinent » (§8.3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Emprise de génération : France métropolitaine et Corse, avec marge. Les
#: tuiles vides — mer, pays voisins — ne coûtent rien : une tuile sans entité
#: n'est simplement pas écrite.
TILES_MIN_LON = -5.60
TILES_MIN_LAT = 41.20
TILES_MAX_LON = 10.00
TILES_MAX_LAT = 51.40

TILE_EXTENT = 4096
TILE_BUFFER = 64

#: Latitude limite de la projection Web Mercator.
_MERCATOR_MAX_LAT = 85.0511287798066


@dataclass(frozen=True, slots=True)
class ZoomPlan:
    """Ce qui se génère à un niveau de zoom, et en combien de bandes."""

    zoom: int
    layers: tuple[str, ...]
    bands: int


#: Plan de génération. Les bandes bornent le coût de chaque requête — au zoom
#: 11, l'emprise compte ~6 800 enveloppes de tuiles — et une bande en échec se
#: rejoue seule.
#:
#: Les communes s'arrêtent au zoom 11, et c'est une contrainte d'hébergement,
#: pas un choix cartographique : le plan gratuit de Supabase plafonne l'envoi
#: à 50 Mo, et l'archive avec le zoom 12 pesait 70. MapLibre sur-zoome le
#: dernier niveau disponible — à l'échelle d'une limite communale, l'écart de
#: quantification reste sous le pixel et demi au zoom 14. Le jour où la limite
#: monte : rajouter `ZoomPlan(zoom=12, layers=("communes",), bands=8)` et
#: régénérer.
PLAN: tuple[ZoomPlan, ...] = (
    ZoomPlan(zoom=4, layers=("regions", "departements"), bands=1),
    ZoomPlan(zoom=5, layers=("regions", "departements"), bands=1),
    ZoomPlan(zoom=6, layers=("regions", "departements"), bands=1),
    ZoomPlan(zoom=7, layers=("departements",), bands=1),
    ZoomPlan(zoom=8, layers=("departements",), bands=1),
    ZoomPlan(zoom=9, layers=("departements",), bands=1),
    ZoomPlan(zoom=10, layers=("departements", "communes"), bands=2),
    ZoomPlan(zoom=11, layers=("departements", "communes"), bands=4),
)


def lonlat_to_tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    """Indices de la tuile contenant un point, en schéma « slippy »."""
    clamped_lat = max(-_MERCATOR_MAX_LAT, min(_MERCATOR_MAX_LAT, lat))
    n = 1 << zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(clamped_lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def tile_range(zoom: int) -> tuple[int, int, int, int]:
    """Bornes inclusives (x0, y0, x1, y1) des tuiles couvrant l'emprise."""
    x0, y0 = lonlat_to_tile(TILES_MIN_LON, TILES_MAX_LAT, zoom)
    x1, y1 = lonlat_to_tile(TILES_MAX_LON, TILES_MIN_LAT, zoom)
    return x0, y0, x1, y1


def column_bands(x0: int, x1: int, count: int) -> list[tuple[int, int]]:
    """Partition des colonnes en bandes contiguës, sans trou ni recouvrement.

    Chaque tuile appartient à exactement une bande : c'est ce qui garantit
    qu'aucune tuile n'est produite par deux requêtes — deux couches de même nom
    concaténées feraient un MVT invalide.
    """
    if count < 1:
        raise ValueError("Au moins une bande.")
    total = x1 - x0 + 1
    if total <= 0:
        raise ValueError("Bornes de colonnes inversées.")
    bands = min(count, total)
    size = -(-total // bands)

    result: list[tuple[int, int]] = []
    start = x0
    while start <= x1:
        end = min(start + size - 1, x1)
        result.append((start, end))
        start = end + 1
    return result


def e7(degrees: float) -> int:
    """Degrés vers la représentation entière e7 de l'en-tête PMTiles."""
    return round(degrees * 10_000_000)


__all__ = [
    "PLAN",
    "TILES_MAX_LAT",
    "TILES_MAX_LON",
    "TILES_MIN_LAT",
    "TILES_MIN_LON",
    "TILE_BUFFER",
    "TILE_EXTENT",
    "ZoomPlan",
    "column_bands",
    "e7",
    "lonlat_to_tile",
    "tile_range",
]
