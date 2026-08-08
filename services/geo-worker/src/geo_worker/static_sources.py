"""Dérivation du registre des sources thermiques statiques.

Référence : cahier §13.11, FR-035 et FR-036 ; plan J10.

Le corpus standard porte quatorze ans de vérité terrain : 165 629 détections
`type = 2` — sources statiques terrestres. Le flux NRT, lui, n'a pas cette
colonne : le masque ne peut donc pas être un filtre, il doit être un **registre
spatial** appliqué par proximité (`mark_known_thermal_sources`). Ce module
construit ce registre.

Règles, versionnées comme celles du regroupement :

- **G1** — les détections `type = 2` sont projetées sur une grille d'environ
  400 m ; les cellules occupées voisines (8-connexité) fusionnent en zones.
  Une torchère est détectée à quelques centaines de mètres près d'un passage à
  l'autre : la grille absorbe ce jitter sans chaîner des sites distincts.
- **G2** — une zone ne devient une source que si elle est **récurrente** :
  au moins 20 détections réparties sur au moins 6 mois distincts. Un brûlage
  agricole d'une saison ou un vrai feu n'y suffisent pas — un site industriel,
  si.
- **G3** — le rayon de correspondance couvre la zone observée plus un demi-
  pixel VIIRS, borné aux limites de la table (500 m à 5 000 m).
- **G4** — la clé de source est déterministe (cellule d'ancrage de la zone) :
  rejouer la dérivation met à jour, ne duplique jamais.
- **G5** — la catégorie naît `other` : le corpus prouve la récurrence, pas la
  nature du site. Nommer « torchère » ou « usine » est un acte éditorial
  (FR-035), jamais une déduction.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

MASK_VERSION = "sources-statiques-v1"

#: Pas de grille en degrés (~440 m en latitude, ~310 m en longitude à 45° N).
GRID_DEG = 0.004

MIN_DETECTIONS = 20
MIN_MONTHS = 6

#: Bornes du rayon de correspondance, celles de la contrainte en base.
RADIUS_FLOOR_M = 500
RADIUS_CEILING_M = 5000

#: Demi-diagonale d'un pixel VIIRS au nadir, marge ajoutée au rayon observé.
VIIRS_HALF_PIXEL_M = 265

STATIC_SOURCE_TYPE = 2


class StaticSourceError(ValueError):
    """Le corpus fourni ne permet pas la dérivation."""


@dataclass(frozen=True, slots=True)
class StaticSource:
    """Une zone récurrente prête pour `fire.known_thermal_sources`."""

    source_key: str
    name: str
    latitude: float
    longitude: float
    match_radius_m: int
    detection_count: int
    month_count: int
    first_seen: str
    last_seen: str


def _cells(frame: pd.DataFrame) -> pd.DataFrame:
    d = frame.copy()
    d["cell_x"] = (d["longitude"] / GRID_DEG).apply(math.floor)
    d["cell_y"] = (d["latitude"] / GRID_DEG).apply(math.floor)
    return d


def _components(cells: set[tuple[int, int]]) -> dict[tuple[int, int], int]:
    """Composantes connexes (8-connexité) des cellules occupées.

    Parcours en profondeur itératif : les zones industrielles s'étendent sur
    des dizaines de cellules, pas des milliers — la pile reste courte.
    """
    label: dict[tuple[int, int], int] = {}
    current = 0
    for start in sorted(cells):
        if start in label:
            continue
        stack = [start]
        while stack:
            cell = stack.pop()
            if cell in label:
                continue
            label[cell] = current
            x, y = cell
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    neighbour = (x + dx, y + dy)
                    if neighbour in cells and neighbour not in label:
                        stack.append(neighbour)
        current += 1
    return label


def _distance_m(lat1: float, lon1: float, lat2: pd.Series, lon2: pd.Series) -> pd.Series:
    """Distance équirectangulaire en mètres — largement suffisante sous 10 km."""
    k_lat = 111_320.0
    k_lon = 111_320.0 * math.cos(math.radians(lat1))
    return (((lat2 - lat1) * k_lat) ** 2 + ((lon2 - lon1) * k_lon) ** 2) ** 0.5


def derive_static_sources(
    frame: pd.DataFrame,
) -> tuple[list[StaticSource], dict[str, Any]]:
    """Applique G1 à G5 au corpus complet et rend le registre avec son bilan."""
    required = {"latitude", "longitude", "type", "detected_at"}
    missing = required - set(frame.columns)
    if missing:
        raise StaticSourceError(f"Colonnes absentes : {', '.join(sorted(missing))}")

    static = frame[frame["type"] == STATIC_SOURCE_TYPE].copy()
    if static.empty:
        raise StaticSourceError("Aucune détection type = 2 : corpus inattendu.")

    static = _cells(static)
    static["month"] = static["detected_at"].dt.strftime("%Y-%m")

    occupied = set(zip(static["cell_x"], static["cell_y"], strict=True))
    labels = _components(occupied)
    static["zone"] = [labels[cell] for cell in zip(static["cell_x"], static["cell_y"], strict=True)]

    sources: list[StaticSource] = []
    covered = 0

    for _, zone in static.groupby("zone"):
        months = zone["month"].nunique()
        count = len(zone)
        if count < MIN_DETECTIONS or months < MIN_MONTHS:
            continue

        lat = float(zone["latitude"].mean())
        lon = float(zone["longitude"].mean())
        spread = float(_distance_m(lat, lon, zone["latitude"], zone["longitude"]).max())
        radius = int(
            min(RADIUS_CEILING_M, max(RADIUS_FLOOR_M, math.ceil(spread + VIIRS_HALF_PIXEL_M)))
        )

        # G4 — la cellule d'ancrage est la plus petite de la zone : stable tant
        # que la zone existe, indépendante de l'ordre de lecture.
        anchor = min(zip(zone["cell_x"], zone["cell_y"], strict=True))
        source_key = f"{MASK_VERSION}:{anchor[0]}:{anchor[1]}"

        covered += count
        sources.append(
            StaticSource(
                source_key=source_key,
                name=f"Source statique {lat:.3f} ; {lon:.3f}",
                latitude=lat,
                longitude=lon,
                match_radius_m=radius,
                detection_count=count,
                month_count=months,
                first_seen=str(zone["detected_at"].min().date()),
                last_seen=str(zone["detected_at"].max().date()),
            )
        )

    sources.sort(key=lambda s: s.source_key)

    payload = "\n".join(
        f"{s.source_key},{s.latitude:.6f},{s.longitude:.6f},{s.match_radius_m}" for s in sources
    )
    stats: dict[str, Any] = {
        "version": MASK_VERSION,
        "detections_type2": len(static),
        "zones_candidates": static["zone"].nunique(),
        "sources_retenues": len(sources),
        "detections_couvertes": covered,
        "couverture_pct": round(100 * covered / len(static), 1),
        "empreinte": hashlib.blake2b(payload.encode("utf-8"), digest_size=8).hexdigest(),
        "parametres": {
            "grille_deg": GRID_DEG,
            "min_detections": MIN_DETECTIONS,
            "min_mois": MIN_MONTHS,
        },
    }
    return sources, stats


__all__ = [
    "GRID_DEG",
    "MASK_VERSION",
    "MIN_DETECTIONS",
    "MIN_MONTHS",
    "StaticSource",
    "StaticSourceError",
    "derive_static_sources",
]
