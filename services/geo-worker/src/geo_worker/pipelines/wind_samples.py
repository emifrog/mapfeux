"""Vent AROME interpolé aux points des événements — `meteo.wind_samples`.

Référence : cahier v2.1 §13.13 et §16.4 ; plan J8.

La grille complète reste dans le stockage objet (§13.13) : ce module en tire
des **échantillons** aux points où le produit en a besoin — le point
représentatif d'un événement — et les consigne avec ce qui permet de les
juger : la méthode d'interpolation employée et la distance du point à la
cellule la plus proche, dont l'incertitude du panache dépendra (§18.4).

Deux méthodes, comme le §16.4 le demande : bilinéaire et plus proche voisin.
Le choix « selon validation » se mesure — le script d'extraction calcule les
deux et imprime leurs écarts sur données réelles avant d'en consigner une.

La direction stockée est **météorologique** : d'où vient le vent, en degrés
depuis le nord. C'est la convention des bulletins et des roses des vents ;
`atan2` sur U/V donne l'inverse (vers où il va), d'où la normalisation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import numpy as np
import psycopg
import xarray as xr
from pyproj import Geod

from geo_worker.logging import get_logger

logger = get_logger(__name__)

#: Niveau des champs `u10`/`v10` du paquet de surface.
WIND_LEVEL = "10m"

#: Garde-fou du §16.4. Un vent **moyen** à 10 m au-delà de cette borne n'existe
#: pas dans un AROME sain — les records métropolitains en rafale approchent
#: 60 m/s. Une valeur au-delà est un fichier corrompu, et un fichier corrompu
#: doit arrêter l'extraction, pas produire un panache plausible et faux.
MAX_COMPONENT_MS = 75.0

#: Sur la grille à 0,025°, aucun point intérieur n'est à plus de ~2 km d'un
#: nœud. Au-delà de cette borne, le point est hors de l'emprise — et le
#: « plus proche voisin » se rabattrait en silence sur le nœud de bord, un
#: vent qui ne décrit rien. La distance est le garde-fou commun aux deux
#: méthodes ; le NaN de la bilinéaire n'est qu'un second filet.
MAX_CELL_DISTANCE_M = 3_000.0

_GEOD = Geod(ellps="WGS84")


class WindExtractionError(RuntimeError):
    """Grille inexploitable au point demandé — hors emprise, ou aberrante."""


@dataclass(frozen=True)
class WindSample:
    """Un échantillon de vent, tel qu'il sera écrit en base (§13.13)."""

    valid_at: datetime
    u_ms: float
    v_ms: float
    speed_ms: float
    direction_deg: float
    interpolation: str
    cell_distance_m: float
    level: str = WIND_LEVEL


def wind_speed_ms(u: float, v: float) -> float:
    """Vitesse du vent depuis ses composantes, en m/s."""
    return math.hypot(u, v)


def meteo_direction_deg(u: float, v: float) -> float:
    """Direction météorologique : d'où vient le vent, degrés depuis le nord.

    `atan2(v, u)` donne le cap **vers lequel** l'air se déplace, en convention
    mathématique (est = 0°, antihoraire). La convention météorologique est
    l'opposée deux fois : origine au nord, sens horaire, et l'on nomme la
    provenance. D'où `270 - atan2`, replié sur [0, 360).
    """
    return (270.0 - math.degrees(math.atan2(v, u))) % 360.0


def _nearest_node(values: xr.DataArray, longitude: float, latitude: float) -> tuple[float, float]:
    """Nœud de grille le plus proche du point, en (longitude, latitude)."""
    node = values.sel(longitude=longitude, latitude=latitude, method="nearest")
    return float(node["longitude"]), float(node["latitude"])


def cell_distance_m(dataset: xr.Dataset, longitude: float, latitude: float) -> float:
    """Distance géodésique du point au nœud de grille le plus proche.

    C'est la grandeur que le §18.4 fait peser sur la confiance : un point à
    deux kilomètres d'un nœud sur une grille à 0,025° est normal, un point à
    vingt kilomètres est hors emprise et son « vent » ne décrit rien.
    """
    node_lon, node_lat = _nearest_node(dataset["u10"], longitude, latitude)
    _, _, distance = _GEOD.inv(longitude, latitude, node_lon, node_lat)
    return float(distance)


def extract_samples(
    dataset: xr.Dataset,
    *,
    run_at: datetime,
    longitude: float,
    latitude: float,
    method: str = "bilinear",
) -> list[WindSample]:
    """Échantillonne `u10`/`v10` au point, à chaque pas de l'extrait.

    L'extrait ne porte que `step` — l'horodatage du run vit au registre, pas
    dans le fichier — d'où `run_at` en paramètre : `valid_at = run + step`.

    Les latitudes AROME sont décroissantes ; `interp` et `sel` d'xarray
    acceptent une coordonnée monotone dans les deux sens, c'est vérifié par
    le test sur grille synthétique décroissante.
    """
    if method not in ("bilinear", "nearest"):
        raise WindExtractionError(f"Méthode inconnue : {method!r}")

    if method == "bilinear":
        point = dataset[["u10", "v10"]].interp(
            longitude=longitude, latitude=latitude, method="linear"
        )
    else:
        point = dataset[["u10", "v10"]].sel(
            longitude=longitude, latitude=latitude, method="nearest"
        )

    distance = cell_distance_m(dataset, longitude, latitude)
    if distance > MAX_CELL_DISTANCE_M:
        raise WindExtractionError(
            f"Point à {distance / 1000:.1f} km du nœud le plus proche : "
            "hors de l'emprise de la grille."
        )

    samples: list[WindSample] = []
    for step in point["step"].values:
        u = float(point["u10"].sel(step=step))
        v = float(point["v10"].sel(step=step))

        if math.isnan(u) or math.isnan(v):
            # En bilinéaire, un NaN signifie un coin manquant : le point est
            # au bord ou hors de l'emprise. Les champs AROME étant denses,
            # ce n'est jamais un état normal à l'intérieur de la grille.
            raise WindExtractionError(
                f"Vent indéfini à ({latitude:.4f}, {longitude:.4f}) : "
                "point hors de l'emprise de l'extrait."
            )
        if abs(u) > MAX_COMPONENT_MS or abs(v) > MAX_COMPONENT_MS:
            raise WindExtractionError(
                f"Composante aberrante ({u:.1f}, {v:.1f}) m/s : extrait corrompu."
            )

        lead_seconds = int(step / np.timedelta64(1, "s"))
        samples.append(
            WindSample(
                valid_at=run_at + timedelta(seconds=lead_seconds),
                u_ms=round(u, 2),
                v_ms=round(v, 2),
                speed_ms=round(wind_speed_ms(u, v), 2),
                direction_deg=round(meteo_direction_deg(u, v), 1),
                interpolation=method,
                cell_distance_m=round(distance, 1),
            )
        )
    return samples


def store_samples(
    conn: psycopg.Connection[Any],
    *,
    model_run_id: UUID,
    longitude: float,
    latitude: float,
    samples: list[WindSample],
) -> int:
    """Écrit les échantillons — rejouer rafraîchit, ne duplique pas.

    La clé d'upsert (run, niveau, échéance, point) est posée par la migration
    `20260818100000` : le même point du même run à la même échéance est une
    seule vérité, quelle que soit la passe qui l'écrit.
    """
    with conn.cursor() as cur:
        for sample in samples:
            cur.execute(
                """
                insert into meteo.wind_samples
                  (model_run_id, location, level, valid_at, u_ms, v_ms,
                   speed_ms, direction_deg, interpolation, cell_distance_m)
                values
                  (%(run_id)s,
                   extensions.st_setsrid(extensions.st_makepoint(%(lon)s, %(lat)s), 4326),
                   %(level)s, %(valid_at)s, %(u)s, %(v)s, %(speed)s,
                   %(direction)s, %(interpolation)s, %(distance)s)
                on conflict (model_run_id, level, valid_at, location) do update set
                  u_ms = excluded.u_ms,
                  v_ms = excluded.v_ms,
                  speed_ms = excluded.speed_ms,
                  direction_deg = excluded.direction_deg,
                  interpolation = excluded.interpolation,
                  cell_distance_m = excluded.cell_distance_m
                """,
                {
                    "run_id": model_run_id,
                    "lon": longitude,
                    "lat": latitude,
                    "level": sample.level,
                    "valid_at": sample.valid_at,
                    "u": sample.u_ms,
                    "v": sample.v_ms,
                    "speed": sample.speed_ms,
                    "direction": sample.direction_deg,
                    "interpolation": sample.interpolation,
                    "distance": sample.cell_distance_m,
                },
            )
    return len(samples)


__all__ = [
    "MAX_CELL_DISTANCE_M",
    "MAX_COMPONENT_MS",
    "WIND_LEVEL",
    "WindExtractionError",
    "WindSample",
    "cell_distance_m",
    "extract_samples",
    "meteo_direction_deg",
    "store_samples",
    "wind_speed_ms",
]
