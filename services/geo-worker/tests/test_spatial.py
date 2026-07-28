"""L'index de voisinage doit trouver exactement ce qu'une recherche exhaustive
trouverait. C'est la condition pour qu'il remplace la requête spatiale sans
changer les rattachements.
"""

from __future__ import annotations

import pytest
from pyproj import Geod

from geo_worker.spatial import NeighbourIndex, geodesic_distance_m

_GEOD = Geod(ellps="WGS84")


def brute_force(
    lons: list[float], lats: list[float], lon: float, lat: float, radius_m: float
) -> set[int]:
    return {
        index
        for index, (point_lon, point_lat) in enumerate(zip(lons, lats, strict=True))
        if geodesic_distance_m(lon, lat, point_lon, point_lat) <= radius_m
    }


class TestDistance:
    def test_mesure_une_distance_connue(self) -> None:
        # Un degré de latitude vaut environ 111 km, partout sur le globe.
        distance = geodesic_distance_m(6.0, 43.0, 6.0, 44.0)
        assert 110_500 < distance < 111_500

    def test_est_symetrique(self) -> None:
        aller = geodesic_distance_m(6.1, 43.4, 6.3, 43.5)
        retour = geodesic_distance_m(6.3, 43.5, 6.1, 43.4)
        assert aller == pytest.approx(retour, abs=1e-6)

    def test_un_point_est_a_zero_de_lui_meme(self) -> None:
        assert geodesic_distance_m(6.0, 43.0, 6.0, 43.0) == pytest.approx(0.0, abs=1e-6)


class TestNeighbourIndex:
    def test_un_index_vide_ne_trouve_rien(self) -> None:
        assert NeighbourIndex([], []).within(6.0, 43.0, 10_000) == []
        assert len(NeighbourIndex([], [])) == 0

    def test_refuse_des_tableaux_de_tailles_differentes(self) -> None:
        with pytest.raises(ValueError):
            NeighbourIndex([6.0, 6.1], [43.0])

    def test_trouve_le_point_confondu(self) -> None:
        index = NeighbourIndex([6.0], [43.0])
        found = index.within(6.0, 43.0, 1_000)
        assert len(found) == 1
        assert found[0][0] == 0
        assert found[0][1] == pytest.approx(0.0, abs=1e-6)

    def test_ecarte_ce_qui_depasse_le_rayon(self) -> None:
        # Deux points séparés d'environ 111 km.
        index = NeighbourIndex([6.0, 6.0], [43.0, 44.0])
        assert [i for i, _ in index.within(6.0, 43.0, 12_000)] == [0]

    def test_la_distance_retournee_est_la_distance_geodesique(self) -> None:
        index = NeighbourIndex([6.05], [43.0])
        found = index.within(6.0, 43.0, 10_000)
        expected = geodesic_distance_m(6.0, 43.0, 6.05, 43.0)
        assert found[0][1] == pytest.approx(expected, abs=1e-6)

    def test_coincide_avec_une_recherche_exhaustive(self) -> None:
        # Grille régulière autour du Var, au pas d'environ 800 m.
        lons: list[float] = []
        lats: list[float] = []
        for i in range(24):
            for j in range(24):
                lons.append(6.0 + i * 0.01)
                lats.append(43.4 + j * 0.0072)

        index = NeighbourIndex(lons, lats)

        for radius in (500, 2_500, 12_000):
            for lon, lat in ((6.0, 43.4), (6.115, 43.483), (6.23, 43.57)):
                found = {i for i, _ in index.within(lon, lat, radius)}
                assert found == brute_force(lons, lats, lon, lat, radius), (
                    f"rayon {radius} m depuis {lon},{lat}"
                )

    def test_ne_manque_pas_un_voisin_juste_sous_la_limite(self) -> None:
        """La marge de présélection doit couvrir l'écart sphère/ellipsoïde.

        Une présélection trop serrée écarterait un point réellement dans le
        rayon, et le rattachement serait perdu sans trace. Les points sont donc
        placés à une distance *exacte* par la géodésique directe, et non par une
        approximation qui reproduirait le défaut qu'on cherche à exclure.

        L'écart entre les deux modèles varie avec la latitude et l'azimut : le
        balayage couvre l'emprise française et les quatre directions.
        """
        radius = 12_000.0
        for latitude in (41.0, 45.0, 51.5):
            for azimuth in (0.0, 90.0, 180.0, 270.0):
                inside_lon, inside_lat, _ = _GEOD.fwd(6.0, latitude, azimuth, radius * 0.9999)
                index = NeighbourIndex([inside_lon], [inside_lat])
                assert len(index.within(6.0, latitude, radius)) == 1, (
                    f"voisin manqué à {latitude}° vers {azimuth}°"
                )

    def test_ecarte_ce_qui_est_juste_au_dela_de_la_limite(self) -> None:
        """La présélection est large, mais la distance exacte tranche."""
        radius = 12_000.0
        for azimuth in (0.0, 90.0, 180.0, 270.0):
            outside_lon, outside_lat, _ = _GEOD.fwd(6.0, 43.4, azimuth, radius * 1.0001)
            index = NeighbourIndex([outside_lon], [outside_lat])
            assert index.within(6.0, 43.4, radius) == [], f"voisin retenu à tort vers {azimuth}°"

    def test_les_indices_correspondent_a_l_ordre_de_construction(self) -> None:
        index = NeighbourIndex([6.0, 6.001, 6.002], [43.0, 43.0, 43.0])
        found = dict(index.within(6.002, 43.0, 1_000))
        assert set(found) == {0, 1, 2}
        assert found[2] < found[1] < found[0]
