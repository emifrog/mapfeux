"""Stratégie raster CAMS : COG, tuiles web et métadonnées versionnées.

Référence : cahier v2.1 §19.1 et §16.5 ; plan J9.

Le NetCDF brut, relu du compartiment `raw` avec son empreinte vérifiée,
devient par échéance deux actifs : un **COG** d'archive et de calcul —
EPSG:4326, la grille du fournisseur, valeurs intactes — et une archive
**PMTiles de tuiles PNG** Web Mercator, colorées par la palette versionnée
(`air_palette`). Le JSON brut vers le navigateur n'existe nulle part
(§19.1) : ce module ne produit que des rasters et un alias de métadonnées
légères.

Deux pièges du produit réel, vus sur le run du 25 août : les longitudes
sont servies en 0-360 avec enroulement au méridien (354,25° puis 10,15°),
et les bords de grille se déduisent des **centres** de cellules — le
premier centre à 51,45° porte un bord nord à 51,5°.

Les actifs sont déposés dans le compartiment **public** `tiles`, sous des
noms porteurs d'empreinte : l'échantillonnage ponctuel (§19.2) lit le COG
par une URL simple et immuable, sans clé côté web — la donnée est publique
et attribuée, seul le brut d'ingestion reste privé.
"""

from __future__ import annotations

import io
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO
from uuid import UUID

import numpy as np
import psycopg
import xarray as xr
from numpy.typing import NDArray

from geo_worker.air_palette import BANDS, PALETTE_VERSION, color_rgb, legend, thresholds
from geo_worker.logging import get_logger
from geo_worker.providers.cams import EXTENT, MODEL, RESOLUTION, UNIT
from geo_worker.tiles import e7, lonlat_to_tile

logger = get_logger(__name__)

#: Version de la conversion : gravée dans chaque actif. Changer la
#: projection, la compression ou le rendu impose une nouvelle version.
RASTERS_VERSION = "cams-rasters-v1"

ATTRIBUTION = "Qualité de l'air modélisée : Copernicus Atmosphere Monitoring Service"

#: Variable NetCDF par polluant du registre — le produit nomme PM2,5
#: « pm2p5 », le registre « pm2_5 » ; la correspondance vit ici, une fois.
POLLUTANT_VARIABLES: dict[str, str] = {"pm2_5": "pm2p5_conc", "pm10": "pm10_conc"}

#: Zooms des tuiles web. Au zoom 6, une cellule de 0,1° couvre déjà ~4,5
#: pixels : au-delà, MapLibre sur-zoome le dernier niveau sans perte
#: d'information — la grille n'en contient pas davantage.
TILE_ZOOMS: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)
TILE_SIZE = 256

TileKey = tuple[int, int, int]


@dataclass(frozen=True)
class PollutantGrid:
    """La grille complète d'un polluant, orientée nord en haut, ouest à gauche.

    `west` et `north` sont des **bords** de grille, pas des centres de
    cellules ; `step` est le pas en degrés. La provenance voyage avec la
    grille : `source_checksum` est l'empreinte du NetCDF dont elle vient.
    """

    pollutant: str
    run_at: datetime
    lead_hours: tuple[int, ...]
    values: NDArray[np.float32]  # (échéances, lignes, colonnes)
    west: float
    north: float
    step: float
    source_checksum: str

    @property
    def height(self) -> int:
        return int(self.values.shape[1])

    @property
    def width(self) -> int:
        return int(self.values.shape[2])

    @property
    def south(self) -> float:
        return round(self.north - self.height * self.step, 4)

    @property
    def east(self) -> float:
        return round(self.west + self.width * self.step, 4)

    def valid_at(self, index: int) -> datetime:
        return self.run_at + timedelta(hours=self.lead_hours[index])


@dataclass(frozen=True)
class RasterAsset:
    """Ce qu'un actif dérivé et déposé laisse derrière lui."""

    pollutant: str
    kind: str  # 'cog' ou 'tile'
    lead_hours: int
    valid_at: datetime
    object_name: str  # chemin dans le compartiment, sans préfixe
    checksum: str
    size_bytes: int
    tile_count: int  # 0 pour un COG


def load_grid(
    path: Path, *, pollutant: str, run_at: datetime, source_checksum: str
) -> PollutantGrid:
    """Lit et normalise le NetCDF d'un polluant, garde-fous compris.

    Refuse plutôt que de deviner : variable absente, longitudes
    irrégulières, latitudes croissantes, échéances non entières ou grille
    vide sont des erreurs franches — un raster publié sur une grille mal
    comprise serait faux partout, silencieusement.
    """
    variable = POLLUTANT_VARIABLES.get(pollutant)
    if variable is None:
        raise ValueError(f"Polluant inconnu : {pollutant!r}.")

    with xr.open_dataset(path) as dataset:
        if variable not in dataset.data_vars:
            raise ValueError(
                f"Variable {variable!r} absente du NetCDF ({sorted(map(str, dataset.data_vars))})."
            )
        array = dataset[variable]
        if "level" in array.dims:
            array = array.squeeze("level", drop=True)
        array = array.transpose("time", "latitude", "longitude")

        hours = np.asarray(dataset["time"].values, dtype=np.float64)
        if not np.allclose(hours, np.round(hours)):
            raise ValueError(f"Échéances non entières : {hours[:5]}…")
        leads = tuple(int(h) for h in np.round(hours))

        latitudes = np.asarray(dataset["latitude"].values, dtype=np.float64)
        if latitudes.size < 2 or not np.all(np.diff(latitudes) < 0):
            raise ValueError("Latitudes non strictement décroissantes : orientation inconnue.")

        # Longitudes 0-360 avec enroulement → signées, ordre croissant.
        longitudes = np.asarray(dataset["longitude"].values, dtype=np.float64)
        signed = np.where(longitudes > 180.0, longitudes - 360.0, longitudes)
        order = np.argsort(signed)
        signed = signed[order]

        lon_steps = np.diff(signed)
        lat_steps = -np.diff(latitudes)
        step = float(round(np.mean(lon_steps), 6))
        if step <= 0 or not np.allclose(lon_steps, step, atol=1e-4):
            raise ValueError("Pas de longitude irrégulier après enroulement.")
        if not np.allclose(lat_steps, step, atol=1e-4):
            raise ValueError("Pas de latitude différent du pas de longitude.")

        values = np.asarray(array.values, dtype=np.float32)[:, :, order]
        if not np.isfinite(values).any():
            raise ValueError("Grille sans aucune valeur finie : rien à publier.")

    grid = PollutantGrid(
        pollutant=pollutant,
        run_at=run_at,
        lead_hours=leads,
        values=values,
        # Les coordonnées float32 du produit portent un bruit d'un millionième
        # de degré ; 4 décimales (~11 m) le gomment sans toucher à la grille.
        west=round(float(signed[0]) - step / 2, 4),
        north=round(float(latitudes[0]) + step / 2, 4),
        step=step,
        source_checksum=source_checksum,
    )

    # La grille annoncée par le fournisseur est celle qu'on a demandée : un
    # écart signale un changement de produit, pas une variation normale.
    expected = (EXTENT.min_lon, EXTENT.min_lat, EXTENT.max_lon, EXTENT.max_lat)
    actual = (grid.west, grid.south, grid.east, grid.north)
    if any(abs(a - b) > 0.01 for a, b in zip(actual, expected, strict=True)):
        raise ValueError(f"Emprise inattendue : {actual} au lieu de {expected}.")

    return grid


def cog_bytes(grid: PollutantGrid, index: int) -> bytes:
    """Le COG d'une échéance : EPSG:4326, valeurs intactes, DEFLATE."""
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    profile = {
        "driver": "COG",
        "dtype": "float32",
        "count": 1,
        "width": grid.width,
        "height": grid.height,
        "crs": "EPSG:4326",
        "transform": from_origin(grid.west, grid.north, grid.step, grid.step),
        "compress": "DEFLATE",
        "nodata": float("nan"),
    }
    with MemoryFile() as memory:
        with memory.open(**profile) as dst:
            dst.write(grid.values[index], 1)
        return bytes(memory.read())


def _band_indices(grid: PollutantGrid, index: int) -> tuple[NDArray[np.intp], NDArray[np.bool_]]:
    """Indice de bande de palette par cellule, et masque des cellules finies."""
    values = grid.values[index]
    finite = np.isfinite(values)
    # right=True : borne supérieure incluse, la sémantique de `band_for`.
    bands = np.digitize(np.nan_to_num(values), thresholds(grid.pollutant), right=True)
    return bands, finite


def render_tiles(grid: PollutantGrid, index: int) -> dict[TileKey, bytes]:
    """Les tuiles PNG d'une échéance ; une tuile sans donnée n'est pas écrite."""
    from PIL import Image

    lut = np.array([color_rgb(band) for band in BANDS[grid.pollutant]], dtype=np.uint8)
    bands, finite = _band_indices(grid, index)

    tiles: dict[TileKey, bytes] = {}
    for zoom in TILE_ZOOMS:
        x0, y0 = lonlat_to_tile(grid.west, grid.north - 1e-9, zoom)
        x1, y1 = lonlat_to_tile(grid.east - 1e-9, grid.south + 1e-9, zoom)
        n = 1 << zoom
        for tx in range(x0, x1 + 1):
            lons = (tx + (np.arange(TILE_SIZE) + 0.5) / TILE_SIZE) / n * 360.0 - 180.0
            cols = np.floor((lons - grid.west) / grid.step).astype(np.intp)
            valid_cols = (cols >= 0) & (cols < grid.width)
            for ty in range(y0, y1 + 1):
                mercator = math.pi * (1 - 2 * (ty + (np.arange(TILE_SIZE) + 0.5) / TILE_SIZE) / n)
                lats = np.degrees(np.arctan(np.sinh(mercator)))
                rows = np.floor((grid.north - lats) / grid.step).astype(np.intp)
                valid_rows = (rows >= 0) & (rows < grid.height)

                sampled_rows = np.clip(rows, 0, grid.height - 1)
                sampled_cols = np.clip(cols, 0, grid.width - 1)
                sampled = bands[np.ix_(sampled_rows, sampled_cols)]
                opaque = (
                    finite[np.ix_(sampled_rows, sampled_cols)]
                    & valid_rows[:, None]
                    & valid_cols[None, :]
                )
                if not opaque.any():
                    continue

                rgba = np.dstack([lut[sampled], np.where(opaque, 255, 0).astype(np.uint8)])
                buffer = io.BytesIO()
                Image.fromarray(rgba, "RGBA").save(buffer, format="PNG", optimize=True)
                tiles[(zoom, tx, ty)] = buffer.getvalue()

    return tiles


def tileset_metadata(grid: PollutantGrid, index: int) -> dict[str, Any]:
    """Métadonnées d'une archive de tuiles — palette et conversion versionnées."""
    return {
        "name": f"MapFeux — {grid.pollutant} modélisé, {grid.valid_at(index).isoformat()}",
        "format": "png",
        "attribution": ATTRIBUTION,
        "version": RASTERS_VERSION,
        "palette": PALETTE_VERSION,
        "polluant": grid.pollutant,
        "unite": UNIT,
    }


def write_air_pmtiles(
    handle: BinaryIO, tiles: dict[TileKey, bytes], metadata: dict[str, Any], grid: PollutantGrid
) -> int:
    """Écrit l'archive PMTiles v3 en type PNG et retourne le nombre de tuiles.

    Contrairement aux MVT des limites administratives, les tuiles ne sont
    pas re-compressées : le PNG l'est déjà, et la spécification attend
    `Compression.NONE` pour les formats d'image.
    """
    from pmtiles.tile import Compression, TileType, zxy_to_tileid
    from pmtiles.writer import Writer

    if not tiles:
        raise ValueError("Aucune tuile à écrire : archive refusée plutôt que vide.")

    writer = Writer(handle)  # type: ignore[no-untyped-call]
    for (z, x, y), payload in sorted(tiles.items(), key=lambda item: zxy_to_tileid(*item[0])):
        writer.write_tile(zxy_to_tileid(z, x, y), payload)  # type: ignore[no-untyped-call]

    header: dict[str, Any] = {
        "version": 3,
        "tile_type": TileType.PNG,
        "tile_compression": Compression.NONE,
        "min_zoom": min(TILE_ZOOMS),
        "max_zoom": max(TILE_ZOOMS),
        "min_lon_e7": e7(grid.west),
        "min_lat_e7": e7(grid.south),
        "max_lon_e7": e7(grid.east),
        "max_lat_e7": e7(grid.north),
        "center_zoom": 5,
        "center_lon_e7": e7(2.55),
        "center_lat_e7": e7(46.60),
    }
    writer.finalize(header, metadata)  # type: ignore[no-untyped-call]
    return len(tiles)


def cog_object_name(grid: PollutantGrid, index: int, checksum: str) -> str:
    """`cams/pm10/20260825/cog-h14-<sha12>.tif` — daté, lisible, immuable."""
    return (
        f"cams/{grid.pollutant}/{grid.run_at:%Y%m%d}/"
        f"cog-h{grid.lead_hours[index]:02d}-{checksum[:12]}.tif"
    )


def tiles_object_name(grid: PollutantGrid, index: int, checksum: str) -> str:
    """`cams/pm10/20260825/tuiles-h14-<sha12>.pmtiles` — même convention."""
    return (
        f"cams/{grid.pollutant}/{grid.run_at:%Y%m%d}/"
        f"tuiles-h{grid.lead_hours[index]:02d}-{checksum[:12]}.pmtiles"
    )


def alias_name(pollutant: str) -> str:
    """Le pointeur mutable d'un polluant : `cams-pm10.json`."""
    return f"cams-{pollutant}.json"


def alias_payload(
    grid: PollutantGrid, tile_assets: list[RasterAsset], *, published_at: datetime
) -> dict[str, Any]:
    """Les métadonnées JSON légères du §19.1 — ce que le front lit, en entier.

    La palette et la légende partent ici plutôt que d'être recopiées côté
    web : le front affiche la légende de la version qui a réellement coloré
    les tuiles qu'il montre.
    """
    return {
        "modele": f"cams-europe-{MODEL}",
        "polluant": grid.pollutant,
        "unite": UNIT,
        "resolution": RESOLUTION,
        "run": grid.run_at.isoformat(),
        "palette": legend(grid.pollutant),
        "attribution": ATTRIBUTION,
        "zooms": {"min": min(TILE_ZOOMS), "max": max(TILE_ZOOMS)},
        "emprise": [grid.west, grid.south, grid.east, grid.north],
        "echeances": [
            {
                "echeance": asset.lead_hours,
                "valide_a": asset.valid_at.isoformat(),
                "objet": asset.object_name,
                "sha256": asset.checksum,
                "octets": asset.size_bytes,
                "tuiles": asset.tile_count,
            }
            for asset in tile_assets
        ],
        "publie_le": published_at.isoformat(),
    }


def record_raster_assets(
    conn: psycopg.Connection[Any], *, run_id: UUID, bucket: str, assets: list[RasterAsset]
) -> None:
    """Enregistre les actifs dérivés au registre — une ligne par échéance.

    Même clé d'upsert que le brut : rejouer la dérivation remplace les
    lignes, jamais ne les double (§13.17).
    """
    with conn.cursor() as cur:
        for asset in assets:
            if asset.kind == "cog":
                metadata: dict[str, Any] = {
                    "conversion": RASTERS_VERSION,
                    "variable": POLLUTANT_VARIABLES[asset.pollutant],
                    "crs": "EPSG:4326",
                    "compression": "deflate",
                }
            else:
                metadata = {
                    "conversion": RASTERS_VERSION,
                    "palette": PALETTE_VERSION,
                    "zooms": [min(TILE_ZOOMS), max(TILE_ZOOMS)],
                    "tuiles": asset.tile_count,
                    "alias": alias_name(asset.pollutant),
                }
            cur.execute(
                """
                insert into air.grid_assets
                  (model_run_id, pollutant, unit, lead_hours, valid_at, kind,
                   extent, resolution, asset_path, checksum, metadata)
                values
                  (%(run_id)s, %(pollutant)s, %(unit)s, %(lead)s, %(valid_at)s, %(kind)s,
                   %(extent)s, %(resolution)s, %(path)s, %(checksum)s, %(metadata)s)
                on conflict (model_run_id, pollutant, kind, lead_hours) do update set
                  valid_at = excluded.valid_at,
                  asset_path = excluded.asset_path,
                  checksum = excluded.checksum,
                  metadata = excluded.metadata
                """,
                {
                    "run_id": run_id,
                    "pollutant": asset.pollutant,
                    "unit": UNIT,
                    "lead": asset.lead_hours,
                    "valid_at": asset.valid_at,
                    "kind": asset.kind,
                    "extent": EXTENT.as_firms_area(),
                    "resolution": RESOLUTION,
                    "path": f"{bucket}/{asset.object_name}",
                    "checksum": asset.checksum,
                    "metadata": json.dumps(metadata, ensure_ascii=False),
                },
            )
    logger.info(
        "cams.rasters_recorded",
        run_id=str(run_id),
        assets=len(assets),
    )


__all__ = [
    "ATTRIBUTION",
    "POLLUTANT_VARIABLES",
    "RASTERS_VERSION",
    "TILE_SIZE",
    "TILE_ZOOMS",
    "PollutantGrid",
    "RasterAsset",
    "TileKey",
    "alias_name",
    "alias_payload",
    "cog_bytes",
    "cog_object_name",
    "load_grid",
    "record_raster_assets",
    "render_tiles",
    "tiles_object_name",
    "tileset_metadata",
    "write_air_pmtiles",
]
