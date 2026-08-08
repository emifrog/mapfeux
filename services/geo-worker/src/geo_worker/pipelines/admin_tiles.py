"""Génération des tuiles vectorielles des limites administratives.

Référence : cahier §21.1, §21.3 et §9.5 ; J3 « génération PMTiles ».

Le découpage appartient à PostGIS : `ST_AsMVTGeom` clippe, quantifie et
simplifie chaque géométrie dans la grille de la tuile, `ST_AsMVT` encode la
couche. Ce module orchestre — une requête par (zoom, bande, couche) — puis
concatène les couches d'une même tuile, ce que le format MVT permet tant que
les noms de couches diffèrent, et assemble l'archive PMTiles.

Aucun GeoJSON national n'est produit nulle part : c'est le point du jalon.
"""

from __future__ import annotations

import gzip
import time
from collections.abc import Callable
from typing import Any, BinaryIO

import psycopg

from geo_worker.logging import get_logger
from geo_worker.tiles import (
    PLAN,
    TILE_BUFFER,
    TILE_EXTENT,
    TILES_MAX_LAT,
    TILES_MAX_LON,
    TILES_MIN_LAT,
    TILES_MIN_LON,
    column_bands,
    e7,
    tile_range,
)

logger = get_logger(__name__)

TILESET_NAME = "limites-administratives"

_GRID = """
    with grille as (
      -- Casts explicites : generate_series est surchargée, et psycopg lie les
      -- entiers sans type — le choix du candidat serait ambigu.
      select x.x, y.y, extensions.st_tileenvelope(%(z)s::int, x.x, y.y) as env
      from generate_series(%(x0)s::int, %(x1)s::int) as x(x),
           generate_series(%(y0)s::int, %(y1)s::int) as y(y)
    )
"""

#: Une requête par couche. Les attributs sont le strict nécessaire au style et
#: au lien : pas de géométrie source, pas de champ interne (§14.2).
#:
#: S608 : la « construction » est la concaténation de deux constantes du
#: module — aucun fragment ne vient de l'extérieur, toutes les valeurs passent
#: en paramètres nommés psycopg.
_LAYER_SQL: dict[str, str] = {
    "communes": _GRID  # noqa: S608
    + """
    select g.x, g.y, extensions.st_asmvt(entites, 'communes', %(extent)s, 'geom') as mvt
    from grille g
    cross join lateral (
      select
        m.insee_code as insee,
        m.name as nom,
        m.department_code as departement,
        extensions.st_asmvtgeom(
          extensions.st_transform(m.geometry, 3857), g.env, %(extent)s, %(buffer)s, true
        ) as geom
      from geo.municipalities m
      where m.valid_to is null
        and m.geometry && extensions.st_transform(g.env, 4326)
    ) entites
    where entites.geom is not null
    group by g.x, g.y
    """,
    "departements": _GRID  # noqa: S608
    + """
    select g.x, g.y, extensions.st_asmvt(entites, 'departements', %(extent)s, 'geom') as mvt
    from grille g
    cross join lateral (
      select
        t.code,
        t.name as nom,
        t.slug,
        t.status::text as statut,
        extensions.st_asmvtgeom(
          extensions.st_transform(t.geometry, 3857), g.env, %(extent)s, %(buffer)s, true
        ) as geom
      from app.territories t
      where t.type = 'department'
        and t.geometry is not null
        and t.geometry && extensions.st_transform(g.env, 4326)
    ) entites
    where entites.geom is not null
    group by g.x, g.y
    """,
    "regions": _GRID  # noqa: S608
    + """
    select g.x, g.y, extensions.st_asmvt(entites, 'regions', %(extent)s, 'geom') as mvt
    from grille g
    cross join lateral (
      select
        t.code,
        t.name as nom,
        t.slug,
        t.status::text as statut,
        extensions.st_asmvtgeom(
          extensions.st_transform(t.geometry, 3857), g.env, %(extent)s, %(buffer)s, true
        ) as geom
      from app.territories t
      where t.type = 'region'
        and t.geometry is not null
        and t.geometry && extensions.st_transform(g.env, 4326)
    ) entites
    where entites.geom is not null
    group by g.x, g.y
    """,
}

TileKey = tuple[int, int, int]


def generate_tiles(
    conn: psycopg.Connection[Any],
    on_progress: Callable[[str], None] | None = None,
) -> dict[TileKey, bytes]:
    """Produit toutes les tuiles du plan, couches concaténées par tuile.

    Chaque bande de colonnes produit des tuiles complètes : une tuile n'est
    jamais partagée entre deux requêtes d'une même couche, donc jamais deux
    couches homonymes à concaténer — ce serait un MVT invalide.
    """
    tiles: dict[TileKey, bytes] = {}

    for plan in PLAN:
        x0, y0, x1, y1 = tile_range(plan.zoom)
        started = time.monotonic()
        before = len(tiles)

        for band_x0, band_x1 in column_bands(x0, x1, plan.bands):
            for layer in plan.layers:
                with conn.cursor() as cur:
                    cur.execute(
                        _LAYER_SQL[layer],
                        {
                            "z": plan.zoom,
                            "x0": band_x0,
                            "x1": band_x1,
                            "y0": y0,
                            "y1": y1,
                            "extent": TILE_EXTENT,
                            "buffer": TILE_BUFFER,
                        },
                    )
                    for x, y, mvt in cur:
                        key: TileKey = (plan.zoom, int(x), int(y))
                        tiles[key] = tiles.get(key, b"") + bytes(mvt)

        elapsed = time.monotonic() - started
        message = (
            f"z{plan.zoom} : {len(tiles) - before} tuile(s), "
            f"couches {'+'.join(plan.layers)}, {elapsed:.1f} s"
        )
        logger.info(
            "tiles.zoom_done",
            zoom=plan.zoom,
            tiles=len(tiles) - before,
            seconds=round(elapsed, 1),
        )
        if on_progress is not None:
            on_progress(message)

    return tiles


def tileset_metadata(version: str) -> dict[str, Any]:
    """Métadonnées de l'archive, dérivées du plan — jamais écrites deux fois."""
    fields_territories = {"code": "String", "nom": "String", "slug": "String", "statut": "String"}
    fields_municipalities = {"insee": "String", "nom": "String", "departement": "String"}

    layers: list[dict[str, Any]] = []
    for layer_id, fields in (
        ("regions", fields_territories),
        ("departements", fields_territories),
        ("communes", fields_municipalities),
    ):
        zooms = [plan.zoom for plan in PLAN if layer_id in plan.layers]
        if not zooms:
            continue
        layers.append(
            {"id": layer_id, "minzoom": min(zooms), "maxzoom": max(zooms), "fields": fields}
        )

    return {
        "name": f"MapFeux — {TILESET_NAME}",
        "format": "pbf",
        "attribution": "Limites administratives : IGN ADMIN EXPRESS COG via Etalab",
        "version": version,
        "vector_layers": layers,
    }


def write_pmtiles(handle: BinaryIO, tiles: dict[TileKey, bytes], metadata: dict[str, Any]) -> int:
    """Écrit l'archive PMTiles v3 et retourne le nombre de tuiles écrites."""
    from pmtiles.tile import Compression, TileType, zxy_to_tileid
    from pmtiles.writer import Writer

    if not tiles:
        raise ValueError("Aucune tuile à écrire : archive refusée plutôt que vide.")

    # `pmtiles` livre un marqueur py.typed sans annoter son écrivain : les
    # appels sont neutralisés un à un plutôt que de détendre mypy sur tout le
    # module.
    writer = Writer(handle)  # type: ignore[no-untyped-call]
    for (z, x, y), payload in sorted(tiles.items(), key=lambda item: zxy_to_tileid(*item[0])):
        writer.write_tile(  # type: ignore[no-untyped-call]
            zxy_to_tileid(z, x, y), gzip.compress(payload)
        )

    zooms = [plan.zoom for plan in PLAN]
    header: dict[str, Any] = {
        "version": 3,
        "tile_type": TileType.MVT,
        "tile_compression": Compression.GZIP,
        "min_zoom": min(zooms),
        "max_zoom": max(zooms),
        "min_lon_e7": e7(TILES_MIN_LON),
        "min_lat_e7": e7(TILES_MIN_LAT),
        "max_lon_e7": e7(TILES_MAX_LON),
        "max_lat_e7": e7(TILES_MAX_LAT),
        "center_zoom": 5,
        "center_lon_e7": e7(2.55),
        "center_lat_e7": e7(46.60),
    }
    writer.finalize(header, metadata)  # type: ignore[no-untyped-call]
    return len(tiles)


__all__ = [
    "TILESET_NAME",
    "TileKey",
    "generate_tiles",
    "tileset_metadata",
    "write_pmtiles",
]
