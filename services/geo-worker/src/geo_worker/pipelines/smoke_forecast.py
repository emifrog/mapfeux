"""Panache de fumée indicatif — cahier v2.1 §18 ; plan J8.

Le MVP ne vise pas un modèle atmosphérique : il produit une **enveloppe
géographique indicative** de la direction probable de transport (§18.1). Le
relief, la convection, les brises locales et l'injection verticale ne sont pas
modélisés — et le résultat ne doit jamais être présenté autrement que comme
indicatif (§22.5, formulation à valider métier avant toute publication).

L'algorithme est celui du §18.3, pas à pas : le vent est relu **au point
courant** à chaque pas — le centre bouge, un panache calculé sur le seul vent
du point d'origine tournerait avec lui au lieu de suivre l'écoulement. La
géométrie se construit en projection azimutale équidistante centrée sur
l'événement : les mètres y sont des mètres, et l'erreur de projection reste
négligeable à l'échelle des garde-fous de distance.

Les coefficients sont des paramètres versionnés (§18.6), **non calibrés** en
v1 : chaque prévision porte le drapeau qui le dit, et la calibration sur cas
connus du corpus est une marche ultérieure du plan. Rien de ce module ne
publie : `is_current` reste faux tant que la formulation §22.5 n'est pas
validée.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import numpy as np
import psycopg
import xarray as xr
from pyproj import Geod, Transformer
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union

from geo_worker.logging import get_logger
from geo_worker.pipelines.wind_samples import (
    MAX_CELL_DISTANCE_M,
    cell_distance_m,
    meteo_direction_deg,
    wind_speed_ms,
)

logger = get_logger(__name__)

ALGORITHM_VERSION = "plume-v1"

#: Drapeaux permanents de la v1 : ce que le calcul ne sait pas encore faire
#: doit se lire sur chaque prévision, pas dans la tête de l'auteur.
PERMANENT_FLAGS = ("coefficients_non_calibres", "relief_non_evalue")


class PlumeError(RuntimeError):
    """Entrée corrompue ou aberration — le calcul s'arrête, franc."""


@dataclass(frozen=True)
class PlumeParameters:
    """Coefficients du §18.2, versionnés avec chaque prévision (§18.6).

    Les valeurs par défaut sont des ordres de grandeur assumés, non calibrés :
    l'advection à 0,9 dit qu'un panache de basse couche suit presque le vent à
    10 m ; l'angle de dispersion à 20° donne l'élargissement du cône ; les
    bornes de distance et de surface sont les garde-fous du §18.5, très au-delà
    desquels une enveloppe ne décrit plus un panache mais une région.
    """

    horizon_minutes: int = 360
    step_minutes: int = 15
    advection_coefficient: float = 0.9
    initial_width_m: float = 500.0
    dispersion_angle_deg: float = 20.0
    max_distance_km: float = 60.0
    max_area_km2: float = 1500.0
    min_speed_ms: float = 0.5
    max_speed_ms: float = 40.0
    simplify_tolerance_m: float = 50.0

    def __post_init__(self) -> None:
        if not 0 < self.horizon_minutes <= 720:
            raise PlumeError(f"Horizon hors du cadre §18.2 : {self.horizon_minutes} min")
        if self.step_minutes <= 0 or self.horizon_minutes % self.step_minutes != 0:
            raise PlumeError(f"Pas invalide : {self.step_minutes} min")


@dataclass(frozen=True)
class PlumeStep:
    """Un pas temporel du panache (§13.15)."""

    step_index: int
    valid_at: datetime
    center_lon: float
    center_lat: float
    footprint_wkt: str
    speed_ms: float
    direction_deg: float
    width_m: float
    distance_m: float
    quality_flags: tuple[str, ...]


@dataclass(frozen=True)
class PlumeResult:
    """Une prévision complète, prête à écrire (§13.14)."""

    valid_from: datetime
    valid_to: datetime
    envelope_wkt: str
    centerline_wkt: str
    area_km2: float
    steps: list[PlumeStep]
    confidence_level: str
    quality_flags: tuple[str, ...]
    confidence_factors: dict[str, bool] = field(default_factory=dict)


def downwind_bearing_deg(meteo_direction: float) -> float:
    """Cap aval : la fumée part à l'opposé d'où vient le vent."""
    return (meteo_direction + 180.0) % 360.0


def plume_width_m(initial_width_m: float, distance_m: float, dispersion_angle_deg: float) -> float:
    """Élargissement du §18.3 : largeur(d) = initiale + d * tan(angle / 2)."""
    return initial_width_m + distance_m * math.tan(math.radians(dispersion_angle_deg) / 2.0)


def sample_wind(
    dataset: xr.Dataset,
    *,
    run_at: datetime,
    longitude: float,
    latitude: float,
    at: datetime,
) -> tuple[float, float] | None:
    """U/V au point et à l'instant demandés, ou `None` hors couverture.

    Spatialement bilinéaire — la méthode validée le 18 août — et linéaire en
    temps entre les deux échéances qui encadrent l'instant : le pas du panache
    (15 min) est plus fin que celui du modèle (1 h), et prendre l'échéance la
    plus proche ferait sauter le vent d'un quart d'heure à l'autre.
    """
    steps_ns = dataset["step"].values
    offsets = [int(s / np.timedelta64(1, "s")) for s in steps_ns]
    wanted = (at - run_at).total_seconds()
    if wanted < offsets[0] or wanted > offsets[-1]:
        return None

    point = dataset[["u10", "v10"]].interp(longitude=longitude, latitude=latitude, method="linear")
    u_series = point["u10"].values.astype(float)
    v_series = point["v10"].values.astype(float)
    u = float(np.interp(wanted, offsets, u_series))
    v = float(np.interp(wanted, offsets, v_series))
    if math.isnan(u) or math.isnan(v):
        return None
    return u, v


def _local_transformers(longitude: float, latitude: float) -> tuple[Transformer, Transformer]:
    """Aller-retour entre WGS84 et une projection locale métrique.

    Azimutale équidistante centrée sur l'événement : les distances depuis le
    centre y sont exactes, et la déformation reste insignifiante à l'échelle
    du garde-fou de distance (60 km).
    """
    local = f"+proj=aeqd +lat_0={latitude} +lon_0={longitude} +datum=WGS84 +units=m"
    forward = Transformer.from_crs("EPSG:4326", local, always_xy=True)
    backward = Transformer.from_crs(local, "EPSG:4326", always_xy=True)
    return forward, backward


def compute_plume(
    dataset: xr.Dataset,
    *,
    run_at: datetime,
    longitude: float,
    latitude: float,
    started_at: datetime,
    parameters: PlumeParameters | None = None,
) -> PlumeResult | None:
    """Déroule l'algorithme du §18.3 depuis la dernière observation.

    Retourne `None` si les entrées sont insuffisantes — aucun pas de vent
    disponible sur l'horizon (§18.5 : résultat vide plutôt qu'inventé). Un
    horizon partiellement couvert produit une prévision **tronquée et
    drapeautée**, jamais complétée en silence.
    """
    params = parameters or PlumeParameters()
    geod = Geod(ellps="WGS84")
    to_local, to_wgs84 = _local_transformers(longitude, latitude)

    dt_seconds = params.step_minutes * 60
    step_count = params.horizon_minutes // params.step_minutes
    origin_distance = cell_distance_m(dataset, longitude, latitude)
    if origin_distance > MAX_CELL_DISTANCE_M:
        raise PlumeError(
            f"Événement à {origin_distance / 1000:.1f} km du nœud de grille le "
            "plus proche : hors de l'emprise de l'extrait."
        )

    flags: set[str] = set(PERMANENT_FLAGS)
    steps: list[PlumeStep] = []
    polygons: list[Polygon] = []
    centers_local: list[tuple[float, float]] = [(0.0, 0.0)]
    directions: list[float] = []
    speeds: list[float] = []

    lon, lat = longitude, latitude
    distance_cum = 0.0

    for index in range(step_count):
        at = started_at + timedelta(seconds=index * dt_seconds)
        wind = sample_wind(dataset, run_at=run_at, longitude=lon, latitude=lat, at=at)
        if wind is None:
            if index == 0:
                return None
            flags.add("horizon_tronque")
            break

        u, v = wind
        speed = wind_speed_ms(u, v)
        direction = meteo_direction_deg(u, v)
        step_flags: set[str] = set()

        if speed > params.max_speed_ms:
            raise PlumeError(f"Vitesse aberrante ({speed:.1f} m/s) : extrait suspect.")
        if speed < params.min_speed_ms:
            # Un vent quasi nul n'advecte rien de fiable : le pas est calculé
            # — l'immobilité est une information — mais il le dit (§18.4).
            step_flags.add("vent_faible")
            flags.add("vent_faible")

        advance = speed * dt_seconds * params.advection_coefficient
        end_lon, end_lat, _ = geod.fwd(lon, lat, downwind_bearing_deg(direction), advance)
        distance_cum += advance

        if distance_cum > params.max_distance_km * 1000.0:
            flags.add("distance_maximale_atteinte")
            break

        width = plume_width_m(params.initial_width_m, distance_cum, params.dispersion_angle_deg)
        start_local = to_local.transform(lon, lat)
        end_local = to_local.transform(end_lon, end_lat)
        corridor = LineString([start_local, end_local]).buffer(width / 2.0)
        polygons.append(corridor)

        area_km2 = float(unary_union(polygons).area) / 1e6
        if area_km2 > params.max_area_km2:
            flags.add("surface_maximale_atteinte")
            polygons.pop()
            break

        centers_local.append(end_local)
        directions.append(direction)
        speeds.append(speed)
        steps.append(
            PlumeStep(
                step_index=index,
                valid_at=at + timedelta(seconds=dt_seconds),
                center_lon=end_lon,
                center_lat=end_lat,
                footprint_wkt=shapely_transform(to_wgs84.transform, corridor).wkt,
                speed_ms=round(speed, 2),
                direction_deg=round(direction, 1),
                width_m=round(width, 1),
                distance_m=round(distance_cum, 1),
                quality_flags=tuple(sorted(step_flags)),
            )
        )
        lon, lat = end_lon, end_lat

    if not steps:
        return None

    envelope_local = unary_union(polygons).simplify(params.simplify_tolerance_m)
    if not envelope_local.is_valid:
        # §18.5 : ST_IsValid obligatoire. `buffer(0)` répare les rares
        # auto-intersections nées de la simplification ; si même cela échoue,
        # le résultat est rejeté, pas rafistolé.
        envelope_local = envelope_local.buffer(0)
        if not envelope_local.is_valid:
            raise PlumeError("Enveloppe invalide après réparation : résultat rejeté.")

    envelope = shapely_transform(to_wgs84.transform, envelope_local)
    if isinstance(envelope, Polygon):
        envelope = MultiPolygon([envelope])
    centerline_local = (
        LineString(centers_local)
        if len(centers_local) > 1
        else LineString([centers_local[0], centers_local[0]])
    )
    centerline = shapely_transform(to_wgs84.transform, centerline_local)

    generated_at = datetime.now(UTC)
    last_valid = steps[-1].valid_at
    if last_valid < generated_at:
        flags.add("rejeu_historique")

    factors = {
        "modele_ancien": (generated_at - run_at) > timedelta(hours=12),
        "observation_ancienne": (generated_at - started_at) > timedelta(hours=24),
        "vent_faible": (sum(speeds) / len(speeds)) < 2.0,
        "direction_instable": _angular_spread_deg(directions) > 60.0,
        "cellule_eloignee": origin_distance > 1_500.0,
    }
    if factors["direction_instable"]:
        flags.add("direction_instable")
    degradations = sum(factors.values())
    confidence = "high" if degradations == 0 else ("medium" if degradations <= 2 else "low")

    return PlumeResult(
        valid_from=started_at,
        valid_to=last_valid,
        envelope_wkt=envelope.wkt,
        centerline_wkt=centerline.wkt,
        area_km2=round(float(envelope_local.area) / 1e6, 2),
        steps=steps,
        confidence_level=confidence,
        quality_flags=tuple(sorted(flags)),
        confidence_factors=factors,
    )


def _angular_spread_deg(directions: list[float]) -> float:
    """Étendue angulaire des directions, insensible au passage par le nord."""
    if len(directions) < 2:
        return 0.0
    radians = np.radians(directions)
    mean = math.atan2(float(np.mean(np.sin(radians))), float(np.mean(np.cos(radians))))
    deviations = [abs((math.degrees(r - mean) + 180.0) % 360.0 - 180.0) for r in radians]
    return 2.0 * max(deviations)


def inputs_checksum(
    *,
    extract_checksum: str | None,
    public_id: str,
    started_at: datetime,
    longitude: float,
    latitude: float,
    parameters: PlumeParameters,
) -> str:
    """Empreinte des entrées principales (§18.6) : mêmes entrées, même empreinte."""
    material = json.dumps(
        {
            "extract": extract_checksum,
            "event": public_id,
            "started_at": started_at.isoformat(),
            "point": [round(longitude, 6), round(latitude, 6)],
            "parameters": asdict(parameters),
        },
        sort_keys=True,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def store_forecast(
    conn: psycopg.Connection[Any],
    *,
    event_id: UUID,
    model_run_id: UUID,
    result: PlumeResult,
    parameters: PlumeParameters,
    provenance: dict[str, Any],
) -> UUID:
    """Écrit la prévision, ses pas et ses communes — `is_current` reste faux.

    Les prévisions précédentes du même événement et de la même version
    d'algorithme, non publiées, sont remplacées : l'exercice répété ne doit
    pas empiler des brouillons. Une prévision publiée (`is_current`) ne serait
    jamais touchée par ce chemin.
    """
    payload = {
        "algorithm_version": ALGORITHM_VERSION,
        "parameters": asdict(parameters),
        "confidence_factors": result.confidence_factors,
        **provenance,
    }

    with conn.cursor() as cur:
        cur.execute(
            """
            delete from meteo.smoke_forecasts
            where event_id = %(event_id)s
              and algorithm_version = %(version)s
              and not is_current
            """,
            {"event_id": event_id, "version": ALGORITHM_VERSION},
        )
        cur.execute(
            """
            insert into meteo.smoke_forecasts
              (event_id, model_run_id, algorithm_version, valid_from, valid_to,
               geometry, centerline, confidence_level, parameters, quality_flags,
               is_current)
            values
              (%(event_id)s, %(model_run_id)s, %(version)s, %(valid_from)s,
               %(valid_to)s,
               extensions.st_geomfromtext(%(envelope)s, 4326),
               extensions.st_geomfromtext(%(centerline)s, 4326),
               %(confidence)s, %(parameters)s, %(flags)s, false)
            returning id
            """,
            {
                "event_id": event_id,
                "model_run_id": model_run_id,
                "version": ALGORITHM_VERSION,
                "valid_from": result.valid_from,
                "valid_to": result.valid_to,
                "envelope": result.envelope_wkt,
                "centerline": result.centerline_wkt,
                "confidence": result.confidence_level,
                "parameters": json.dumps(payload, ensure_ascii=False, default=str),
                "flags": list(result.quality_flags),
            },
        )
        row = cur.fetchone()
        assert row is not None  # returning sur insert : toujours une ligne
        forecast_id = UUID(str(row[0]))

        for step in result.steps:
            cur.execute(
                """
                insert into meteo.smoke_steps
                  (forecast_id, step_index, valid_at, center, footprint,
                   speed_ms, direction_deg, width_m, distance_m, quality_flags)
                values
                  (%(forecast_id)s, %(index)s, %(valid_at)s,
                   extensions.st_setsrid(
                     extensions.st_makepoint(%(lon)s, %(lat)s), 4326),
                   extensions.st_geomfromtext(%(footprint)s, 4326),
                   %(speed)s, %(direction)s, %(width)s, %(distance)s, %(flags)s)
                """,
                {
                    "forecast_id": forecast_id,
                    "index": step.step_index,
                    "valid_at": step.valid_at,
                    "lon": step.center_lon,
                    "lat": step.center_lat,
                    "footprint": step.footprint_wkt,
                    "speed": step.speed_ms,
                    "direction": step.direction_deg,
                    "width": step.width_m,
                    "distance": step.distance_m,
                    "flags": list(step.quality_flags),
                },
            )

        # §18.3 étape 9 et §13.16 : l'intersection par pas donne la fenêtre
        # temporelle, l'enveloppe donne la surface. Le rang suit FR-072 —
        # heure d'arrivée estimée, puis niveau d'exposition.
        cur.execute(
            """
            insert into meteo.affected_municipalities
              (forecast_id, insee_code, first_intersection_at,
               last_intersection_at, overlap_area_km2, overlap_ratio,
               exposure_rank, confidence_level)
            select
              f.id,
              m.insee_code,
              min(s.valid_at),
              max(s.valid_at),
              round((extensions.st_area(
                extensions.st_intersection(m.geometry, f.geometry)::extensions.geography
              ) / 1e6)::numeric, 2),
              round(least(1.0, extensions.st_area(
                  extensions.st_intersection(m.geometry, f.geometry)::extensions.geography
                ) / nullif(extensions.st_area(m.geometry::extensions.geography), 0)
              )::numeric, 4),
              row_number() over (
                order by min(s.valid_at),
                extensions.st_area(
                  extensions.st_intersection(m.geometry, f.geometry)::extensions.geography
                ) desc
              ),
              f.confidence_level
            from meteo.smoke_forecasts f
            join meteo.smoke_steps s on s.forecast_id = f.id
            join geo.municipalities m
              on m.valid_to is null
             and extensions.st_intersects(m.geometry, s.footprint)
            where f.id = %(forecast_id)s
            group by f.id, m.insee_code, f.confidence_level
            """,
            {"forecast_id": forecast_id},
        )

    logger.info(
        "plume.stored",
        forecast_id=str(forecast_id),
        steps=len(result.steps),
        confidence=result.confidence_level,
        flags=list(result.quality_flags),
    )
    return forecast_id


__all__ = [
    "ALGORITHM_VERSION",
    "PERMANENT_FLAGS",
    "PlumeError",
    "PlumeParameters",
    "PlumeResult",
    "PlumeStep",
    "compute_plume",
    "downwind_bearing_deg",
    "inputs_checksum",
    "plume_width_m",
    "sample_wind",
    "store_forecast",
]
