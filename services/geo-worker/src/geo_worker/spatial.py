"""Index de voisinage géodésique en mémoire.

Référence : cahier §17.2.

Le regroupement interrogeait la base une fois par détection pour trouver les
événements proches. Sur 931 détections, cela faisait près de trois mille
allers-retours et deux minutes de traitement, dont l'essentiel en attente
réseau : le calcul lui-même est négligeable. Charger les points une fois et
chercher les voisins en mémoire supprime ce coût.

Deux étapes, pour la vitesse **et** l'exactitude :

1. Un arbre k-d sur les coordonnées cartésiennes de la sphère unité écarte
   grossièrement les points hors de portée. La corde entre deux points croît
   avec l'angle au centre, donc une requête par rayon de corde ne peut pas
   manquer un voisin — à condition de majorer le rayon, ce que fait la marge.
2. La distance retenue est ensuite calculée sur l'ellipsoïde WGS84, la même
   grandeur que `ST_Distance` sur le type `geography` de PostGIS. L'approximation
   sphérique ne sert qu'à présélectionner ; elle n'entre jamais dans le résultat.

Cette séparation est ce qui permet de déplacer la recherche hors de la base sans
changer les rattachements : le critère de sortie du jalon exige que l'empreinte
du partitionnement reste identique.
"""

from __future__ import annotations

import numpy as np
from pyproj import Geod
from scipy.spatial import cKDTree

# Rayon polaire : le plus petit des deux. L'utiliser pour convertir un rayon en
# mètres vers un angle donne l'angle le plus grand, donc une sélection plus
# large. Se tromper par excès est sans conséquence — la distance exacte tranche
# ensuite — alors que se tromper par défaut perdrait des voisins.
_MIN_EARTH_RADIUS_M = 6_356_752.314245

# L'écart entre distance sphérique et distance géodésique reste sous 0,5 %.
_SAFETY_MARGIN = 1.02

_GEOD = Geod(ellps="WGS84")


class NeighbourIndex:
    """Voisins d'un point dans un rayon donné, sur un jeu de positions fixe.

    Les positions ne changent jamais : une détection est acquise à un endroit et
    y reste. L'arbre est donc construit une fois, alors que l'appartenance aux
    événements, elle, évolue pendant le regroupement. C'est cette dissociation
    qui rend l'index utilisable dans une boucle séquentielle.
    """

    def __init__(self, lons: list[float], lats: list[float]) -> None:
        if len(lons) != len(lats):
            raise ValueError("Longitudes et latitudes de tailles différentes.")

        self._lons = np.asarray(lons, dtype=float)
        self._lats = np.asarray(lats, dtype=float)
        self._size = len(lons)

        if self._size == 0:
            # `cKDTree` refuse un tableau vide ; l'index reste utilisable et
            # répond simplement qu'il n'y a aucun voisin.
            self._tree: cKDTree | None = None
            return

        self._tree = cKDTree(_to_unit_sphere(self._lons, self._lats))

    def __len__(self) -> int:
        return self._size

    def within(self, lon: float, lat: float, radius_m: float) -> list[tuple[int, float]]:
        """Indices et distances géodésiques des points à moins de `radius_m`.

        Le résultat n'est pas trié : l'appelant applique son propre ordre, qui
        n'est pas seulement celui des distances.
        """
        if self._tree is None or radius_m <= 0:
            return []

        angle = (radius_m * _SAFETY_MARGIN) / _MIN_EARTH_RADIUS_M
        chord = 2.0 * np.sin(min(angle, np.pi) / 2.0)

        query = _to_unit_sphere(np.array([lon]), np.array([lat]))[0]
        rough = self._tree.query_ball_point(query, chord)
        if not rough:
            return []

        indices = np.asarray(rough, dtype=int)
        _, _, distances = _GEOD.inv(
            np.full(indices.size, lon),
            np.full(indices.size, lat),
            self._lons[indices],
            self._lats[indices],
        )

        keep = distances <= radius_m
        return [(int(i), float(d)) for i, d in zip(indices[keep], distances[keep], strict=True)]


def _to_unit_sphere(lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    lon_rad = np.radians(lons)
    lat_rad = np.radians(lats)
    cos_lat = np.cos(lat_rad)
    return np.column_stack((cos_lat * np.cos(lon_rad), cos_lat * np.sin(lon_rad), np.sin(lat_rad)))


def geodesic_distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Distance sur l'ellipsoïde WGS84, en mètres."""
    _, _, distance = _GEOD.inv(lon1, lat1, lon2, lat2)
    return float(distance)


__all__ = ["NeighbourIndex", "geodesic_distance_m"]
