"""Frames radar : lecture ODIM, conversion contrôlée, image web, timeline.

Référence : cahier v2.1 §16.6, §19.1, §19.3, FR-123 ; plan J9.

La mosaïque HDF5 ODIM (maille 500 m, projection stéréographique polaire)
devient une **image PNG géoréférencée en Web Mercator**, colorée par la
palette versionnée `radar_palette` — jamais de grille brute vers le
navigateur (§19.1). La conversion est contrôlée : grandeur `ACRR` exigée,
dimensions vérifiées contre l'en-tête, et la convention de grille — coin
bas-gauche à l'origine, y vers le nord — est **prouvée sur chaque fichier**
en reprojetant son propre coin haut-gauche, pas supposée d'après un
descriptif.

La frame rejoint `radar.frames` avec son expiration : une lame d'eau de
plus de deux heures ne décrit plus rien, l'animation ne doit jamais la
servir (§16.6). La timeline est l'alias JSON publié à côté des images —
les métadonnées légères du §19.1, au plus 24 frames (§19.3).
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import psycopg
from numpy.typing import NDArray

from geo_worker.logging import get_logger
from geo_worker.radar_palette import (
    BANDS,
    DRAWN_FROM_MM_H,
    RADAR_PALETTE_VERSION,
    color_rgb,
    legend,
    thresholds,
)

logger = get_logger(__name__)

PRODUCT_KEY = "lame_d_eau"

#: Version de la conversion ODIM → image web, gravée dans l'alias.
CONVERSION_VERSION = "radar-frames-v1"

ATTRIBUTION = "Radar de précipitations : Météo-France, mosaïque lame d'eau"

#: Une frame expire deux heures après son acquisition : c'est la fenêtre de
#: l'animation (24 frames x 5 minutes) et rien de plus (§16.6).
FRAME_TTL = timedelta(hours=2)

#: Au plus 24 frames dans la timeline servie au client (§19.3).
TIMELINE_LENGTH = 24

#: Résolution de l'image web, en mètres Mercator. La maille source est à
#: 500 m ; 2 000 m suffisent largement à une carte nationale de pluie et
#: divisent le poids par seize.
WEB_SCALE_M = 2000.0

#: Garde-fou : une image web ne dépasse jamais quatre mégapixels.
MAX_WEB_PIXELS = 4_000_000


@dataclass(frozen=True)
class RadarMosaic:
    """Une mosaïque ODIM relue, valeurs brutes et géoréférencement compris."""

    acquired_at: datetime
    accumulation_start_at: datetime
    values: NDArray[np.uint16]  # (lignes, colonnes), ligne 0 au nord
    gain: float
    offset: float
    nodata: float
    undetect: float
    projdef: str
    xscale: float
    yscale: float
    ul_lon: float
    ul_lat: float
    source: str

    @property
    def height(self) -> int:
        return int(self.values.shape[0])

    @property
    def width(self) -> int:
        return int(self.values.shape[1])

    @property
    def accumulation_seconds(self) -> float:
        return (self.acquired_at - self.accumulation_start_at).total_seconds()


def _stamp(date_raw: bytes | str, time_raw: bytes | str) -> datetime:
    date_text = date_raw.decode() if isinstance(date_raw, bytes) else str(date_raw)
    time_text = time_raw.decode() if isinstance(time_raw, bytes) else str(time_raw)
    return datetime.strptime(f"{date_text}{time_text}", "%Y%m%d%H%M%S").replace(tzinfo=UTC)


def _text(raw: object) -> str:
    return raw.decode() if isinstance(raw, bytes) else str(raw)


def parse_odim(payload: bytes) -> RadarMosaic:
    """Lit la mosaïque ODIM, garde-fous compris — refuse plutôt que deviner."""
    import h5py

    with h5py.File(io.BytesIO(payload)) as archive:
        what = dict(archive["what"].attrs)
        where = dict(archive["where"].attrs)
        data_what = dict(archive["dataset1/data1/what"].attrs)
        window = dict(archive["dataset1/what"].attrs)

        quantity = _text(data_what.get("quantity", ""))
        if quantity != "ACRR":
            raise ValueError(f"Grandeur inattendue : {quantity!r} au lieu de ACRR.")
        if _text(what.get("object", "")) != "COMP":
            raise ValueError(f"Objet inattendu : {what.get('object')!r} au lieu de COMP.")

        values = np.asarray(archive["dataset1/data1/data"], dtype=np.uint16)
        xsize, ysize = int(where["xsize"]), int(where["ysize"])
        if values.shape != (ysize, xsize):
            raise ValueError(f"Grille {values.shape} ≠ en-tête ({ysize}, {xsize}).")

        mosaic = RadarMosaic(
            acquired_at=_stamp(what["date"], what["time"]),
            accumulation_start_at=_stamp(window["startdate"], window["starttime"]),
            values=values,
            gain=float(data_what["gain"]),
            offset=float(data_what["offset"]),
            nodata=float(data_what["nodata"]),
            undetect=float(data_what["undetect"]),
            projdef=_text(where["projdef"]).strip(),
            xscale=float(where["xscale"]),
            yscale=float(where["yscale"]),
            ul_lon=float(where["UL_lon"]),
            ul_lat=float(where["UL_lat"]),
            source=_text(what.get("source", "")),
        )

    seconds = mosaic.accumulation_seconds
    if not 0 < seconds <= 900:
        raise ValueError(f"Fenêtre de cumul invraisemblable : {seconds:.0f} s.")
    return mosaic


def _check_grid_convention(mosaic: RadarMosaic, to_grid: Any) -> None:
    """Prouve la convention de grille sur le fichier lui-même.

    Le coin haut-gauche annoncé en longitude/latitude doit tomber, dans la
    projection du fichier, sur (0, ysize x yscale) : origine au coin
    bas-gauche, y vers le nord. Un fichier qui en dévie serait projeté de
    travers en silence — d'où l'erreur franche.
    """
    x, y = to_grid.transform(mosaic.ul_lon, mosaic.ul_lat)
    expected_y = mosaic.height * mosaic.yscale
    if abs(x) > 1.0 or abs(y - expected_y) > 1.0:
        raise ValueError(
            f"Convention de grille inattendue : UL → ({x:.1f}, {y:.1f}) "
            f"au lieu de (0, {expected_y:.0f})."
        )


@dataclass(frozen=True)
class WebFrame:
    """L'image web d'une frame : PNG et emprise géographique exacte."""

    png: bytes
    west: float
    south: float
    east: float
    north: float
    width: int
    height: int

    @property
    def extent(self) -> str:
        return f"{self.west},{self.south},{self.east},{self.north}"


def render_web_frame(mosaic: RadarMosaic, *, scale_m: float = WEB_SCALE_M) -> WebFrame:
    """Reprojette la mosaïque en image Mercator colorée par la palette.

    Rééchantillonnage au plus proche voisin — les cellules restent des
    cellules — et emprise calculée sur le **pourtour échantillonné** de la
    grille, pas sur les seuls coins : les bords d'une grille stéréographique
    bombent en Mercator, et les coins seuls rogneraient la donnée.
    """
    from PIL import Image
    from pyproj import Transformer

    to_grid = Transformer.from_crs("EPSG:4326", mosaic.projdef, always_xy=True)
    _check_grid_convention(mosaic, to_grid)

    grid_to_mercator = Transformer.from_crs(mosaic.projdef, "EPSG:3857", always_xy=True)
    mercator_to_grid = Transformer.from_crs("EPSG:3857", mosaic.projdef, always_xy=True)
    mercator_to_lonlat = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    # Pourtour de la grille en coordonnées projetées, échantillonné.
    max_x = mosaic.width * mosaic.xscale
    max_y = mosaic.height * mosaic.yscale
    steps = np.linspace(0.0, 1.0, 101)
    edge_x = np.concatenate(
        [steps * max_x, np.full_like(steps, max_x), steps * max_x, np.zeros_like(steps)]
    )
    edge_y = np.concatenate(
        [np.full_like(steps, max_y), steps * max_y, np.zeros_like(steps), steps * max_y]
    )
    boundary_x, boundary_y = grid_to_mercator.transform(edge_x, edge_y)
    x_min, x_max = float(np.min(boundary_x)), float(np.max(boundary_x))
    y_min, y_max = float(np.min(boundary_y)), float(np.max(boundary_y))

    width = math.ceil((x_max - x_min) / scale_m)
    height = math.ceil((y_max - y_min) / scale_m)
    if width * height > MAX_WEB_PIXELS:
        raise ValueError(f"Image web démesurée : {width}x{height}.")

    xs = x_min + (np.arange(width) + 0.5) * scale_m
    ys = y_max - (np.arange(height) + 0.5) * scale_m
    mesh_x, mesh_y = np.meshgrid(xs, ys)
    grid_x, grid_y = mercator_to_grid.transform(mesh_x, mesh_y)

    cols = np.floor(grid_x / mosaic.xscale).astype(np.intp)
    rows = np.floor((max_y - grid_y) / mosaic.yscale).astype(np.intp)
    inside = (cols >= 0) & (cols < mosaic.width) & (rows >= 0) & (rows < mosaic.height)
    cols_safe = np.clip(cols, 0, mosaic.width - 1)
    rows_safe = np.clip(rows, 0, mosaic.height - 1)

    raw = mosaic.values[rows_safe, cols_safe].astype(np.float64)
    valid = inside & (raw != mosaic.nodata) & (raw != mosaic.undetect)

    # Cumul (mm) → intensité (mm/h) : la fenêtre vient du fichier, pas d'une
    # constante — un produit qui passerait à six minutes resterait juste.
    intensity = (raw * mosaic.gain + mosaic.offset) * (3600.0 / mosaic.accumulation_seconds)
    drawn = valid & (intensity >= DRAWN_FROM_MM_H)

    bands = np.digitize(np.nan_to_num(intensity), thresholds(), right=True)
    lut = np.array([color_rgb(band) for band in BANDS], dtype=np.uint8)
    rgba = np.dstack([lut[bands], np.where(drawn, 255, 0).astype(np.uint8)])

    buffer = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buffer, format="PNG", optimize=True)

    west, south = mercator_to_lonlat.transform(x_min, y_min)
    east, north = mercator_to_lonlat.transform(x_max, y_max)
    return WebFrame(
        png=buffer.getvalue(),
        west=round(float(west), 6),
        south=round(float(south), 6),
        east=round(float(east), 6),
        north=round(float(north), 6),
        width=width,
        height=height,
    )


def raw_object_name(mosaic: RadarMosaic, filename: str | None) -> str:
    """`radar/2026/08/25/T_IPRN20_C_LFPW_20260825181000.h5` — le nom servi."""
    fallback = f"lame-d-eau-{mosaic.acquired_at:%Y%m%d%H%M%S}.h5"
    return f"radar/{mosaic.acquired_at:%Y/%m/%d}/{filename or fallback}"


def frame_object_name(acquired_at: datetime, checksum: str) -> str:
    """`radar/lame-d-eau/20260825/1810-<sha12>.png` — daté, immuable."""
    return f"radar/lame-d-eau/{acquired_at:%Y%m%d}/{acquired_at:%H%M}-{checksum[:12]}.png"


def alias_name() -> str:
    """Le pointeur mutable de la timeline : `radar-lame-d-eau.json`."""
    return "radar-lame-d-eau.json"


def has_ready_frame(conn: psycopg.Connection[Any], acquired_at: datetime) -> bool:
    """La frame est-elle déjà servie ? Évite de retélécharger 1,8 Mo pour rien."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select 1 from radar.frames
            where product = %(product)s and acquired_at = %(acquired_at)s
              and status = 'ready'
            """,
            {"product": PRODUCT_KEY, "acquired_at": acquired_at},
        )
        return cur.fetchone() is not None


def record_frame(
    conn: psycopg.Connection[Any],
    *,
    acquired_at: datetime,
    projection: str,
    extent: str,
    raw_path: str,
    web_path: str,
    checksum: str,
) -> None:
    """Enregistre (ou remplace) la frame, prête et datée d'expiration."""
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into radar.frames
              (product, acquired_at, projection, extent, raw_path, web_path,
               status, checksum, expires_at)
            values
              (%(product)s, %(acquired_at)s, %(projection)s, %(extent)s,
               %(raw_path)s, %(web_path)s, 'ready', %(checksum)s, %(expires_at)s)
            on conflict (product, acquired_at) do update set
              projection = excluded.projection,
              extent = excluded.extent,
              raw_path = excluded.raw_path,
              web_path = excluded.web_path,
              status = 'ready',
              checksum = excluded.checksum,
              expires_at = excluded.expires_at
            """,
            {
                "product": PRODUCT_KEY,
                "acquired_at": acquired_at,
                "projection": projection,
                "extent": extent,
                "raw_path": raw_path,
                "web_path": web_path,
                "checksum": checksum,
                "expires_at": acquired_at + FRAME_TTL,
            },
        )


def expire_frames(conn: psycopg.Connection[Any], *, now: datetime) -> int:
    """Marque expirées les frames sorties de la fenêtre — jamais supprimées ici.

    L'expiration automatique du §16.6 est un changement d'état ; la purge des
    objets est un geste distinct (dette de rétention, plan §15).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            update radar.frames
            set status = 'expired'
            where product = %(product)s and status = 'ready' and expires_at < %(now)s
            """,
            {"product": PRODUCT_KEY, "now": now},
        )
        return cur.rowcount


@dataclass(frozen=True)
class TimelineFrame:
    """Ce que la timeline publie d'une frame.

    Pas d'empreinte ici : la colonne `checksum` porte celle du **brut**
    (provenance, comme partout ailleurs), et les PNG portent la leur dans
    leur nom — c'est ce qui rend leurs URL immuables.
    """

    acquired_at: datetime
    web_path: str
    expires_at: datetime


def timeline(conn: psycopg.Connection[Any], limit: int = TIMELINE_LENGTH) -> list[TimelineFrame]:
    """Les frames prêtes les plus récentes, en ordre chronologique."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select acquired_at, web_path, expires_at
            from radar.frames
            where product = %(product)s and status = 'ready'
            order by acquired_at desc
            limit %(limit)s
            """,
            {"product": PRODUCT_KEY, "limit": limit},
        )
        rows = cur.fetchall()
    return [
        TimelineFrame(acquired_at=row[0], web_path=str(row[1]), expires_at=row[2])
        for row in reversed(rows)
    ]


def alias_payload(
    frames: list[TimelineFrame],
    *,
    extent: str,
    published_at: datetime,
) -> dict[str, Any]:
    """Les métadonnées légères de la timeline (§19.1) — ce que le front lit.

    Chaque frame porte son heure d'acquisition (FR-123) et son expiration ;
    les objets sont immuables, l'alias est le seul point mutable — c'est la
    maîtrise d'expiration des URL que demande le §19.3.
    """
    west, south, east, north = (float(part) for part in extent.split(","))
    return {
        "produit": PRODUCT_KEY,
        "zone": "METROPOLE",
        "grandeur": "cumul de lame d'eau sur cinq minutes, affiché en intensité (mm/h)",
        "maille_source": "500 m",
        "conversion": CONVERSION_VERSION,
        "palette": legend(),
        "attribution": ATTRIBUTION,
        "emprise": [west, south, east, north],
        "frames": [
            {
                "acquise_a": frame.acquired_at.isoformat(),
                "objet": frame.web_path.partition("/")[2],
                "expire_a": frame.expires_at.isoformat(),
            }
            for frame in frames
        ],
        "publie_le": published_at.isoformat(),
    }


__all__ = [
    "ATTRIBUTION",
    "CONVERSION_VERSION",
    "FRAME_TTL",
    "MAX_WEB_PIXELS",
    "PRODUCT_KEY",
    "RADAR_PALETTE_VERSION",
    "TIMELINE_LENGTH",
    "WEB_SCALE_M",
    "RadarMosaic",
    "TimelineFrame",
    "WebFrame",
    "alias_name",
    "alias_payload",
    "expire_frames",
    "frame_object_name",
    "has_ready_frame",
    "parse_odim",
    "raw_object_name",
    "record_frame",
    "render_web_frame",
    "timeline",
]
