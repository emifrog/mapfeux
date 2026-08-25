"""Conversion des périmètres GeoJSON.

Une erreur ici enregistre une surface fausse sous le nom d'une source réelle
— l'affirmation non sourcée du §2.4, en géométrie.
"""

from __future__ import annotations

import pytest
from shapely import wkt as shapely_wkt

from geo_worker.pipelines.perimeters import PerimeterError, geojson_to_multipolygon_wkt

CARRE = [[[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]]


class TestGeojsonToMultipolygon:
    def test_un_polygone_nu_devient_multi(self) -> None:
        result = geojson_to_multipolygon_wkt({"type": "Polygon", "coordinates": CARRE})
        geometry = shapely_wkt.loads(result)
        assert geometry.geom_type == "MultiPolygon"
        assert geometry.area == pytest.approx(1.0)

    def test_une_feature_est_depliee(self) -> None:
        result = geojson_to_multipolygon_wkt(
            {
                "type": "Feature",
                "properties": {"nom": "essai"},
                "geometry": {"type": "Polygon", "coordinates": CARRE},
            }
        )
        assert shapely_wkt.loads(result).geom_type == "MultiPolygon"

    def test_une_collection_fusionne_ses_membres(self) -> None:
        decale = [[[2.0, 0.0], [2.0, 1.0], [3.0, 1.0], [3.0, 0.0], [2.0, 0.0]]]
        result = geojson_to_multipolygon_wkt(
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": CARRE}},
                    {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": decale}},
                ],
            }
        )
        geometry = shapely_wkt.loads(result)
        assert len(geometry.geoms) == 2
        assert geometry.area == pytest.approx(2.0)

    def test_un_anneau_auto_intersecte_est_repare(self) -> None:
        # Le nœud papillon, défaut d'export classique : make_valid le scinde
        # en deux triangles au lieu de perdre le périmètre.
        papillon = [[[0.0, 0.0], [1.0, 1.0], [1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]]
        result = geojson_to_multipolygon_wkt({"type": "Polygon", "coordinates": papillon})
        geometry = shapely_wkt.loads(result)
        assert geometry.is_valid
        assert geometry.area == pytest.approx(0.5)

    def test_le_non_surfacique_est_refuse(self) -> None:
        with pytest.raises(PerimeterError, match="polygone"):
            geojson_to_multipolygon_wkt({"type": "Point", "coordinates": [1.0, 2.0]})

    def test_une_collection_vide_est_refusee(self) -> None:
        with pytest.raises(PerimeterError, match="polygone"):
            geojson_to_multipolygon_wkt({"type": "FeatureCollection", "features": []})

    def test_les_points_egares_sont_ecartes_pas_le_reste(self) -> None:
        result = geojson_to_multipolygon_wkt(
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [9.0, 9.0]}},
                    {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": CARRE}},
                ],
            }
        )
        assert shapely_wkt.loads(result).area == pytest.approx(1.0)
