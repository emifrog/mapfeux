"""Tests de l'arithmétique des tuiles et du plan PMTiles — cahier §21.3.

Le découpage des géométries appartient à PostGIS et ne se teste qu'avec une
base ; ici se vérifie ce qui garantit la validité du format : des bandes sans
recouvrement — deux couches homonymes concaténées feraient un MVT invalide —
et un plan conforme à la stratégie de zoom du cahier.
"""

from __future__ import annotations

import pytest

from geo_worker.pipelines.admin_tiles import tileset_metadata
from geo_worker.tiles import (
    PLAN,
    column_bands,
    e7,
    lonlat_to_tile,
    tile_range,
)


class TestLonLatToTile:
    def test_valeurs_connues(self) -> None:
        # Greenwich/équateur : la tuile centrale de la grille.
        assert lonlat_to_tile(0.0, 0.0, 1) == (1, 1)
        # Nice (7.26 E, 43.70 N) au zoom 10 — vérifié contre la formule slippy.
        assert lonlat_to_tile(7.26, 43.70, 10) == (532, 373)

    def test_bornes_de_grille(self) -> None:
        n = 1 << 5
        x, y = lonlat_to_tile(180.0, -85.06, 5)
        assert x == n - 1 and y == n - 1
        assert lonlat_to_tile(-180.0, 85.06, 5) == (0, 0)


class TestTileRange:
    def test_emprise_france_croissante_avec_le_zoom(self) -> None:
        previous = 0
        for zoom in (4, 8, 10, 12):
            x0, y0, x1, y1 = tile_range(zoom)
            count = (x1 - x0 + 1) * (y1 - y0 + 1)
            assert x0 <= x1 and y0 <= y1
            assert count > previous
            previous = count

    def test_zoom_11_reste_borne(self) -> None:
        x0, y0, x1, y1 = tile_range(11)
        # ~6 800 enveloppes : l'ordre de grandeur qui justifie les bandes.
        assert 4_000 < (x1 - x0 + 1) * (y1 - y0 + 1) < 12_000


class TestColumnBands:
    def test_partition_sans_trou_ni_recouvrement(self) -> None:
        bands = column_bands(10, 47, 4)
        covered: list[int] = []
        for start, end in bands:
            assert start <= end
            covered.extend(range(start, end + 1))
        assert covered == list(range(10, 48))

    def test_plus_de_bandes_que_de_colonnes(self) -> None:
        assert column_bands(3, 5, 10) == [(3, 3), (4, 4), (5, 5)]

    def test_bande_unique(self) -> None:
        assert column_bands(0, 99, 1) == [(0, 99)]

    def test_bornes_inversees_refusees(self) -> None:
        with pytest.raises(ValueError):
            column_bands(5, 3, 2)


class TestPlan:
    def test_zooms_stricts_et_couches_connues(self) -> None:
        zooms = [plan.zoom for plan in PLAN]
        assert zooms == sorted(zooms)
        assert len(set(zooms)) == len(zooms)
        for plan in PLAN:
            assert plan.bands >= 1
            assert plan.layers
            assert set(plan.layers) <= {"regions", "departements", "communes"}

    def test_communes_jamais_sous_le_zoom_10(self) -> None:
        # §8.3 : les limites communales ne se chargent qu'à un zoom pertinent.
        for plan in PLAN:
            if "communes" in plan.layers:
                assert plan.zoom >= 10


class TestMetadata:
    def test_couches_derivees_du_plan(self) -> None:
        metadata = tileset_metadata("etalab-geo-api:2026-08-07")
        layers = {layer["id"]: layer for layer in metadata["vector_layers"]}
        assert set(layers) == {"regions", "departements", "communes"}
        assert layers["communes"]["minzoom"] == 10
        # Zoom 11 au plafond : la limite d'envoi du plan gratuit, documentée
        # sur le PLAN — le sur-zoom MapLibre couvre au-delà.
        assert layers["communes"]["maxzoom"] == 11
        assert layers["regions"]["minzoom"] == 4
        assert metadata["format"] == "pbf"
        assert "IGN" in metadata["attribution"]


def test_e7() -> None:
    assert e7(2.55) == 25_500_000
    assert e7(-5.6) == -56_000_000
