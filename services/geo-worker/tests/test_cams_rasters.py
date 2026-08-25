"""Tests de la stratégie raster CAMS — cahier §19.1, plan J9.

Le NetCDF synthétique reproduit les deux pièges du produit réel constatés
sur le run du 25 août : longitudes en 0-360 **avec enroulement au
méridien**, et coordonnées float32 dont le bruit remonterait dans le
géoréférencement sans arrondi des bords. Les valeurs encodent la longitude
de leur cellule : tout défaut d'enroulement déplacerait la France entière,
et c'est précisément ce que les assertions verraient.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from geo_worker.air_palette import PALETTE_VERSION
from geo_worker.pipelines.cams_rasters import (
    TILE_ZOOMS,
    PollutantGrid,
    RasterAsset,
    alias_name,
    alias_payload,
    cog_bytes,
    cog_object_name,
    load_grid,
    render_tiles,
    tiles_object_name,
    tileset_metadata,
    write_air_pmtiles,
)

RUN_AT = datetime(2026, 8, 25, 0, tzinfo=UTC)
CHECKSUM = "a" * 64

#: Coordonnées du produit réel, en float32 comme lui : centres de cellules,
#: latitudes décroissantes, longitudes 0-360 enroulées au méridien.
LATITUDES = (51.45 - 0.1 * np.arange(105)).astype(np.float32)
LONGITUDES = np.concatenate([354.25 + 0.1 * np.arange(58), 0.05 + 0.1 * np.arange(102)]).astype(
    np.float32
)


def product_netcdf(
    tmp_path: Path,
    values: np.ndarray | None = None,
    *,
    variable: str = "pm10_conc",
    latitudes: np.ndarray = LATITUDES,
) -> Path:
    if values is None:
        # Chaque cellule porte la longitude signée de son centre : la seule
        # donnée qui rende un défaut d'enroulement visible partout.
        signed = np.where(LONGITUDES > 180.0, LONGITUDES - 360.0, LONGITUDES)
        values = np.broadcast_to(
            signed.astype(np.float32), (2, 1, latitudes.size, LONGITUDES.size)
        ).copy()
    dataset = xr.Dataset(
        {variable: (("time", "level", "latitude", "longitude"), values)},
        coords={
            "time": np.array([0.0, 1.0], dtype=np.float32),
            "level": np.array([0.0], dtype=np.float32),
            "latitude": latitudes,
            "longitude": LONGITUDES,
        },
    )
    path = tmp_path / "produit.nc"
    dataset.to_netcdf(path)
    return path


def loaded_grid(tmp_path: Path, **kwargs: object) -> PollutantGrid:
    path = product_netcdf(tmp_path, **kwargs)  # type: ignore[arg-type]
    return load_grid(path, pollutant="pm10", run_at=RUN_AT, source_checksum=CHECKSUM)


class TestLoadGrid:
    def test_enroulement_et_bords_de_grille(self, tmp_path: Path) -> None:
        grid = loaded_grid(tmp_path)
        # Bords exacts malgré le float32 : l'arrondi à 4 décimales gomme le
        # millionième de degré du produit sans toucher à la grille.
        assert (grid.west, grid.north, grid.east, grid.south) == (-5.8, 51.5, 10.2, 41.0)
        assert grid.step == pytest.approx(0.1, abs=1e-4)
        # Les colonnes sont en ordre géographique : la valeur de chaque
        # cellule est la longitude de son centre.
        centres = grid.west + grid.step / 2 + grid.step * np.arange(grid.width)
        assert np.allclose(grid.values[0, 0, :], centres, atol=1e-3)

    def test_echeances_et_heures_de_validite(self, tmp_path: Path) -> None:
        grid = loaded_grid(tmp_path)
        assert grid.lead_hours == (0, 1)
        assert grid.valid_at(1) == RUN_AT + timedelta(hours=1)

    def test_refuse_latitudes_croissantes(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="décroissantes"):
            loaded_grid(tmp_path, latitudes=LATITUDES[::-1].copy())

    def test_refuse_une_variable_absente(self, tmp_path: Path) -> None:
        path = product_netcdf(tmp_path, variable="autre_chose")
        with pytest.raises(ValueError, match="absente"):
            load_grid(path, pollutant="pm10", run_at=RUN_AT, source_checksum=CHECKSUM)

    def test_refuse_une_grille_sans_valeur_finie(self, tmp_path: Path) -> None:
        empty = np.full((2, 1, 105, 160), np.nan, dtype=np.float32)
        with pytest.raises(ValueError, match="finie"):
            loaded_grid(tmp_path, values=empty)

    def test_refuse_une_emprise_inattendue(self, tmp_path: Path) -> None:
        # Une grille amputée signale un changement de produit chez l'ADS :
        # erreur franche plutôt qu'un raster juste-mais-décalé.
        with pytest.raises(ValueError, match="Emprise"):
            loaded_grid(tmp_path, latitudes=LATITUDES[:50].copy())

    def test_refuse_un_polluant_inconnu(self, tmp_path: Path) -> None:
        path = product_netcdf(tmp_path)
        with pytest.raises(ValueError, match="inconnu"):
            load_grid(path, pollutant="o3", run_at=RUN_AT, source_checksum=CHECKSUM)


class TestCog:
    def test_relu_identique_et_georeference(self, tmp_path: Path) -> None:
        import rasterio
        from rasterio.io import MemoryFile

        grid = loaded_grid(tmp_path)
        payload = cog_bytes(grid, 0)
        with MemoryFile(payload) as memory, memory.open() as src:
            assert src.crs == rasterio.CRS.from_epsg(4326)
            assert src.transform.c == pytest.approx(-5.8)
            assert src.transform.f == pytest.approx(51.5)
            assert np.allclose(src.read(1), grid.values[0], equal_nan=True)

    def test_echantillon_ponctuel_du_19_2(self, tmp_path: Path) -> None:
        # Le contrat de la consultation ponctuelle : la cellule relue du COG
        # à une position donnée est celle de la grille source. Pontevès.
        from rasterio.io import MemoryFile

        grid = loaded_grid(tmp_path)
        payload = cog_bytes(grid, 0)
        with MemoryFile(payload) as memory, memory.open() as src:
            row, col = src.index(6.05, 43.55)
            assert float(src.read(1)[row, col]) == pytest.approx(6.05, abs=1e-3)


class TestRenderTiles:
    def test_couleur_de_la_bande_atmo(self, tmp_path: Path) -> None:
        from PIL import Image

        # 30 µg/m³ de PM10 partout : bande « moyen », #50ccaa.
        values = np.full((2, 1, 105, 160), 30.0, dtype=np.float32)
        grid = loaded_grid(tmp_path, values=values)
        tiles = render_tiles(grid, 0)
        # La tuile z6 32/22 est entièrement en France : centre opaque.
        image = Image.open(io.BytesIO(tiles[(6, 32, 22)])).convert("RGBA")
        assert image.size == (256, 256)
        assert image.getpixel((128, 128)) == (0x50, 0xCC, 0xAA, 255)

    def test_transparent_hors_grille(self, tmp_path: Path) -> None:
        from PIL import Image

        grid = loaded_grid(tmp_path)
        tiles = render_tiles(grid, 0)
        # La tuile z2 couvrant l'Europe déborde largement la grille : ses
        # coins sont transparents, son intérieur France opaque.
        image = Image.open(io.BytesIO(tiles[(2, 2, 1)])).convert("RGBA")
        corner = image.getpixel((0, 0))
        assert isinstance(corner, tuple) and corner[3] == 0

    def test_une_tuile_sans_donnee_est_omise(self, tmp_path: Path) -> None:
        # Une seule cellule finie, à l'est : les tuiles de l'ouest n'existent
        # pas — une tuile vide coûte du stockage pour ne rien montrer.
        values = np.full((2, 1, 105, 160), np.nan, dtype=np.float32)
        values[:, :, 30, 155] = 12.0
        grid = loaded_grid(tmp_path, values=values)
        tiles = render_tiles(grid, 0)
        zoom6 = [key for key in tiles if key[0] == 6]
        assert len(zoom6) == 1

    def test_toutes_les_tuiles_aux_zooms_du_plan(self, tmp_path: Path) -> None:
        grid = loaded_grid(tmp_path)
        tiles = render_tiles(grid, 0)
        assert {key[0] for key in tiles} == set(TILE_ZOOMS)


class TestPmtiles:
    def test_archive_png_sans_compression_interne(self, tmp_path: Path) -> None:
        from pmtiles.reader import MmapSource, Reader
        from pmtiles.tile import Compression, TileType

        grid = loaded_grid(tmp_path)
        tiles = render_tiles(grid, 0)
        target = tmp_path / "essai.pmtiles"
        with target.open("wb") as handle:
            written = write_air_pmtiles(handle, tiles, tileset_metadata(grid, 0), grid)
        assert written == len(tiles)

        with target.open("rb") as handle:
            reader = Reader(MmapSource(handle))  # type: ignore[no-untyped-call]
            header = reader.header()  # type: ignore[no-untyped-call]
            assert header["tile_type"] == TileType.PNG
            assert header["tile_compression"] == Compression.NONE
            zoom, x, y = next(iter(sorted(tiles)))
            assert reader.get(zoom, x, y) == tiles[(zoom, x, y)]  # type: ignore[no-untyped-call]

    def test_archive_vide_refusee(self, tmp_path: Path) -> None:
        grid = loaded_grid(tmp_path)
        with pytest.raises(ValueError, match="Aucune tuile"):
            write_air_pmtiles(io.BytesIO(), {}, tileset_metadata(grid, 0), grid)


class TestNamesAndAlias:
    def test_chemins_dates_et_lisibles(self, tmp_path: Path) -> None:
        grid = loaded_grid(tmp_path)
        checksum = "deadbeefcafe" + "0" * 52
        assert cog_object_name(grid, 1, checksum) == ("cams/pm10/20260825/cog-h01-deadbeefcafe.tif")
        assert tiles_object_name(grid, 1, checksum) == (
            "cams/pm10/20260825/tuiles-h01-deadbeefcafe.pmtiles"
        )
        assert alias_name("pm2_5") == "cams-pm2_5.json"

    def test_alias_metadonnees_legeres_du_19_1(self, tmp_path: Path) -> None:
        grid = loaded_grid(tmp_path)
        asset = RasterAsset(
            pollutant="pm10",
            kind="tile",
            lead_hours=1,
            valid_at=RUN_AT + timedelta(hours=1),
            object_name="cams/pm10/20260825/tuiles-h01-deadbeefcafe.pmtiles",
            checksum="deadbeefcafe" + "0" * 52,
            size_bytes=1234,
            tile_count=27,
        )
        alias = alias_payload(grid, [asset], published_at=RUN_AT + timedelta(hours=9))
        assert alias["polluant"] == "pm10"
        assert alias["unite"] == "µg/m³"
        assert alias["resolution"] == "0.1°"
        assert alias["palette"]["version"] == PALETTE_VERSION
        assert alias["emprise"] == [-5.8, 41.0, 10.2, 51.5]
        assert alias["echeances"][0]["echeance"] == 1
        assert alias["echeances"][0]["objet"].endswith(".pmtiles")
        assert alias["echeances"][0]["tuiles"] == 27
