"""Palette et légende versionnées de la lame d'eau radar.

Référence : cahier v2.1 §19.1 (« palette et légende versionnées ») et
FR-123 ; plan J9.

Le produit est un **cumul sur cinq minutes** en millimètres ; l'intensité
affichée est sa conversion en mm/h (x 12), la grandeur que le public lit
sur toutes les cartes de pluie. Les seuils suivent les classes usuelles
d'intensité (pluie faible < 3 mm/h, modérée < 7, forte au-delà), détaillées
en six bandes pour que l'animation reste lisible ; ce découpage est un
choix éditorial de MapFeux, versionné comme tel — il n'existe pas d'échelle
réglementaire des couleurs radar.

Même contrat que la palette de qualité de l'air : borne supérieure incluse,
version gravée dans chaque actif, changer un seuil impose une nouvelle
version.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RADAR_PALETTE_VERSION = "radar-lame-v1"

RADAR_PALETTE_SOURCE = (
    "Classes usuelles d'intensité de précipitation (mm/h), converties du cumul "
    "radar sur cinq minutes — découpage éditorial MapFeux, versionné"
)


@dataclass(frozen=True, slots=True)
class RadarBand:
    """Une bande d'intensité : borne supérieure incluse en mm/h, couleur, nom."""

    upper: float | None  # mm/h, incluse ; None pour la bande ouverte
    color: str  # sRGB « #rrggbb »
    label: str


#: Sous ce cumul, rien n'est dessiné : le bruit de mesure ferait scintiller
#: toute la carte. La valeur reste servie par la donnée brute archivée.
DRAWN_FROM_MM_H = 0.4

BANDS: tuple[RadarBand, ...] = (
    RadarBand(upper=1.0, color="#87c9ff", label="très faible"),
    RadarBand(upper=3.0, color="#3a86e0", label="faible"),
    RadarBand(upper=7.0, color="#1d4ed8", label="modérée"),
    RadarBand(upper=12.0, color="#f0e641", label="forte"),
    RadarBand(upper=30.0, color="#ff8c00", label="très forte"),
    RadarBand(upper=None, color="#d61f69", label="extrême"),
)


def thresholds() -> tuple[float, ...]:
    """Les bornes supérieures finies, dans l'ordre — pour `numpy.digitize`."""
    return tuple(band.upper for band in BANDS if band.upper is not None)


def band_for(intensity_mm_h: float) -> RadarBand:
    """La bande d'une intensité ; borne supérieure **incluse**."""
    for band in BANDS:
        if band.upper is None or intensity_mm_h <= band.upper:
            return band
    raise AssertionError("La dernière bande est ouverte : inatteignable.")


def color_rgb(band: RadarBand) -> tuple[int, int, int]:
    """Composantes entières d'une couleur « #rrggbb »."""
    raw = band.color.lstrip("#")
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def legend() -> dict[str, Any]:
    """La légende sérialisable — versionnée et sourcée, pour l'alias JSON."""
    return {
        "version": RADAR_PALETTE_VERSION,
        "source": RADAR_PALETTE_SOURCE,
        "unite": "mm/h",
        "seuil_trace": DRAWN_FROM_MM_H,
        "bandes": [
            {"jusqu_a": band.upper, "couleur": band.color, "libelle": band.label} for band in BANDS
        ],
    }


__all__ = [
    "BANDS",
    "DRAWN_FROM_MM_H",
    "RADAR_PALETTE_SOURCE",
    "RADAR_PALETTE_VERSION",
    "RadarBand",
    "band_for",
    "color_rgb",
    "legend",
    "thresholds",
]
