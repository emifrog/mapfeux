"""Tests du connecteur radar et de la conversion contrôlée — cahier §16.6.

L'ODIM synthétique reproduit le produit réel du 25 août : projection
stéréographique polaire avec ses faux décalages, coin bas-gauche à
l'origine, y vers le nord, `ACRR` en centièmes de millimètre. Les coins
géographiques sont **recalculés** depuis la projection — comme le fichier
réel les porte — si bien que le garde-fou de convention s'exerce sur la
même géométrie que celle qu'il vérifiera en production.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

import numpy as np
import pytest

from geo_worker.pipelines.radar_frames import (
    TimelineFrame,
    alias_name,
    alias_payload,
    frame_object_name,
    parse_odim,
    raw_object_name,
    render_web_frame,
)
from geo_worker.providers.radar import (
    api_key_from,
    parse_filename_stamp,
    parse_title_stamp,
)
from geo_worker.radar_palette import RADAR_PALETTE_VERSION

#: Le projdef du produit réel (mosaïque métropole SERVAL).
PROJDEF = (
    "+proj=stere +lat_0=90 +lon_0=0 +lat_ts=45 +ellps=WGS84 "
    "+x_0=619652.07 +y_0=5262818.34 +datum=WGS84"
)

XSIZE = 64
YSIZE = 64
SCALE = 500.0


def corner_lonlat(x: float, y: float) -> tuple[float, float]:
    from pyproj import Transformer

    lon, lat = Transformer.from_crs(PROJDEF, "EPSG:4326", always_xy=True).transform(x, y)
    return float(lon), float(lat)


def synthetic_odim(
    values: np.ndarray | None = None,
    *,
    quantity: bytes = b"ACRR",
    endtime: bytes = b"181000",
    starttime: bytes = b"180500",
    ul_shift_deg: float = 0.0,
) -> bytes:
    import h5py

    if values is None:
        values = np.zeros((YSIZE, XSIZE), dtype=np.uint16)
    ul_lon, ul_lat = corner_lonlat(0.0, YSIZE * SCALE)

    buffer = io.BytesIO()
    with h5py.File(buffer, "w") as f:
        what = f.create_group("what")
        what.attrs["object"] = b"COMP"
        what.attrs["date"] = b"20260825"
        what.attrs["time"] = endtime
        what.attrs["source"] = b"CMT:test"
        where = f.create_group("where")
        where.attrs["projdef"] = PROJDEF.encode()
        where.attrs["xsize"] = np.int64(XSIZE)
        where.attrs["ysize"] = np.int64(YSIZE)
        where.attrs["xscale"] = SCALE
        where.attrs["yscale"] = SCALE
        where.attrs["UL_lon"] = ul_lon
        where.attrs["UL_lat"] = ul_lat + ul_shift_deg
        dataset = f.create_group("dataset1")
        window = dataset.create_group("what")
        window.attrs["startdate"] = b"20260825"
        window.attrs["starttime"] = starttime
        window.attrs["enddate"] = b"20260825"
        window.attrs["endtime"] = endtime
        data = dataset.create_group("data1")
        data.create_dataset("data", data=values)
        data_what = data.create_group("what")
        data_what.attrs["quantity"] = quantity
        data_what.attrs["gain"] = 0.01
        data_what.attrs["offset"] = 0.0
        data_what.attrs["nodata"] = 65535.0
        data_what.attrs["undetect"] = 65534.0
    return buffer.getvalue()


class TestApiKey:
    def test_variable_dediee_seule(self) -> None:
        assert api_key_from({"METEOFRANCE_RADAR_API_KEY": " k "}) == "k"
        # La clé de la vigilance ne doit JAMAIS être ramassée par erreur :
        # même portail, application différente, 403 garanti.
        assert api_key_from({"METEOFRANCE_VIGILANCE_API_KEY": "v"}) == ""


class TestStamps:
    def test_horodatage_du_document_de_liens(self) -> None:
        document = {
            "links": [
                {"title": "Ce document"},
                {
                    "title": (
                        "Mosaïque radar de LAME_D_EAU pour la zone METROPOLE "
                        "et à la maille 500 du 2026-08-25T18:10:00Z"
                    )
                },
            ]
        }
        assert parse_title_stamp(document) == datetime(2026, 8, 25, 18, 10, tzinfo=UTC)

    def test_document_sans_horodatage(self) -> None:
        assert parse_title_stamp({"links": [{"title": "rien ici"}]}) is None

    def test_horodatage_du_nom_de_fichier(self) -> None:
        disposition = 'attachment; filename="T_IPRN20_C_LFPW_20260825181000.h5"'
        assert parse_filename_stamp(disposition) == datetime(2026, 8, 25, 18, 10, tzinfo=UTC)


class TestParseOdim:
    def test_lit_le_produit(self) -> None:
        mosaic = parse_odim(synthetic_odim())
        assert mosaic.acquired_at == datetime(2026, 8, 25, 18, 10, tzinfo=UTC)
        assert mosaic.accumulation_seconds == 300.0
        assert (mosaic.width, mosaic.height) == (XSIZE, YSIZE)
        assert mosaic.gain == 0.01
        assert mosaic.projdef == PROJDEF

    def test_refuse_une_autre_grandeur(self) -> None:
        with pytest.raises(ValueError, match="ACRR"):
            parse_odim(synthetic_odim(quantity=b"DBZH"))

    def test_refuse_une_fenetre_invraisemblable(self) -> None:
        with pytest.raises(ValueError, match="cumul"):
            parse_odim(synthetic_odim(starttime=b"120000"))


class TestRenderWebFrame:
    def test_cellule_pluvieuse_coloree_a_sa_position(self) -> None:
        from PIL import Image
        from pyproj import Transformer

        values = np.zeros((YSIZE, XSIZE), dtype=np.uint16)
        row, col = 10, 20
        values[row, col] = 50  # 0,50 mm / 5 min = 6 mm/h → « modérée »
        frame = render_web_frame(parse_odim(synthetic_odim(values)), scale_m=250.0)

        # Position Mercator du centre de la cellule, via la projection source.
        to_mercator = Transformer.from_crs(PROJDEF, "EPSG:3857", always_xy=True)
        cell_x, cell_y = to_mercator.transform((col + 0.5) * SCALE, (YSIZE - row - 0.5) * SCALE)
        lonlat_to_mercator = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        x_min, _ = lonlat_to_mercator.transform(frame.west, frame.south)
        _, y_max = lonlat_to_mercator.transform(frame.east, frame.north)

        image = Image.open(io.BytesIO(frame.png)).convert("RGBA")
        px = int((cell_x - x_min) / 250.0)
        py = int((y_max - cell_y) / 250.0)
        assert image.getpixel((px, py)) == (0x1D, 0x4E, 0xD8, 255)
        # Loin de la cellule : transparent — le sec ne se dessine pas.
        corner = image.getpixel((0, 0))
        assert isinstance(corner, tuple) and corner[3] == 0

    def test_nodata_et_undetect_transparents(self) -> None:
        from PIL import Image

        values = np.full((YSIZE, XSIZE), 65535, dtype=np.uint16)
        values[:32] = 65534
        frame = render_web_frame(parse_odim(synthetic_odim(values)), scale_m=500.0)
        image = Image.open(io.BytesIO(frame.png)).convert("RGBA")
        alpha = np.asarray(image)[:, :, 3]
        assert int(alpha.max()) == 0

    def test_refuse_une_convention_de_grille_deviee(self) -> None:
        with pytest.raises(ValueError, match="Convention"):
            render_web_frame(parse_odim(synthetic_odim(ul_shift_deg=0.5)))


class TestNamesAndAlias:
    def test_chemins_dates_et_lisibles(self) -> None:
        mosaic = parse_odim(synthetic_odim())
        assert raw_object_name(mosaic, "T_IPRN20_C_LFPW_20260825181000.h5") == (
            "radar/2026/08/25/T_IPRN20_C_LFPW_20260825181000.h5"
        )
        assert raw_object_name(mosaic, None) == ("radar/2026/08/25/lame-d-eau-20260825181000.h5")
        checksum = "deadbeefcafe" + "0" * 52
        assert frame_object_name(mosaic.acquired_at, checksum) == (
            "radar/lame-d-eau/20260825/1810-deadbeefcafe.png"
        )
        assert alias_name() == "radar-lame-d-eau.json"

    def test_alias_timeline_du_19_3(self) -> None:
        acquired = datetime(2026, 8, 25, 18, 10, tzinfo=UTC)
        frames = [
            TimelineFrame(
                acquired_at=acquired,
                web_path="tiles/radar/lame-d-eau/20260825/1810-deadbeefcafe.png",
                expires_at=datetime(2026, 8, 25, 20, 10, tzinfo=UTC),
            )
        ]
        alias = alias_payload(frames, extent="-9.9,37.4,17.6,53.7", published_at=acquired)
        assert alias["produit"] == "lame_d_eau"
        assert alias["palette"]["version"] == RADAR_PALETTE_VERSION
        assert alias["emprise"] == [-9.9, 37.4, 17.6, 53.7]
        entry = alias["frames"][0]
        assert entry["acquise_a"] == "2026-08-25T18:10:00+00:00"
        assert entry["objet"] == "radar/lame-d-eau/20260825/1810-deadbeefcafe.png"
        assert entry["expire_a"] == "2026-08-25T20:10:00+00:00"
