"""Palette et légende versionnées de la qualité de l'air modélisée.

Référence : cahier v2.1 §19.1 (« palette et légende versionnées ») et
FR-121 ; plan J9.

Les seuils sont ceux de l'indice ATMO (arrêté du 10 juillet 2020), alignés
sur l'indice européen de qualité de l'air de l'AEE, appliqués polluant par
polluant en µg/m³. La palette classe une **concentration modélisée** dans une
bande ; elle ne calcule pas l'indice ATMO lui-même — qui agrège plusieurs
polluants mesurés — et n'énonce aucune recommandation sanitaire (§9.4).

La version est gravée dans chaque actif produit : métadonnées des archives
de tuiles, alias JSON, registre `air.grid_assets`. Changer un seuil ou une
couleur impose une **nouvelle version**, jamais une modification silencieuse
— une carte archivée doit rester lisible avec la légende de son époque.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PALETTE_VERSION = "aq-atmo-v1"

PALETTE_SOURCE = (
    "Seuils de l'indice ATMO (arrêté du 10 juillet 2020), "
    "alignés sur l'indice européen de qualité de l'air de l'AEE"
)


@dataclass(frozen=True, slots=True)
class PaletteBand:
    """Une bande de concentration : borne supérieure incluse, couleur, nom."""

    upper: float | None  # µg/m³, incluse ; None pour la bande ouverte
    color: str  # sRGB « #rrggbb »
    label: str  # qualificatif officiel de la bande


#: Couleurs et qualificatifs officiels des six bandes, communs aux polluants ;
#: seuls les seuils diffèrent d'un polluant à l'autre.
_COLORS = ("#50f0e6", "#50ccaa", "#f0e641", "#ff5050", "#960032", "#7d2181")
_LABELS = ("bon", "moyen", "dégradé", "mauvais", "très mauvais", "extrêmement mauvais")


def _bands(*uppers: float) -> tuple[PaletteBand, ...]:
    bounds: tuple[float | None, ...] = (*uppers, None)
    return tuple(
        PaletteBand(upper=upper, color=color, label=label)
        for upper, color, label in zip(bounds, _COLORS, _LABELS, strict=True)
    )


#: Bandes par polluant, en µg/m³. Les clés sont celles du registre
#: `air.grid_assets` et du connecteur CAMS (`POLLUTANTS`).
BANDS: dict[str, tuple[PaletteBand, ...]] = {
    "pm2_5": _bands(10.0, 20.0, 25.0, 50.0, 75.0),
    "pm10": _bands(20.0, 40.0, 50.0, 100.0, 150.0),
}


def thresholds(pollutant: str) -> tuple[float, ...]:
    """Les bornes supérieures finies, dans l'ordre — pour `numpy.digitize`."""
    return tuple(band.upper for band in BANDS[pollutant] if band.upper is not None)


def band_for(pollutant: str, value: float) -> PaletteBand:
    """La bande d'une concentration ; borne supérieure **incluse**."""
    for band in BANDS[pollutant]:
        if band.upper is None or value <= band.upper:
            return band
    raise AssertionError("La dernière bande est ouverte : inatteignable.")


def color_rgb(band: PaletteBand) -> tuple[int, int, int]:
    """Composantes entières d'une couleur « #rrggbb »."""
    raw = band.color.lstrip("#")
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def legend(pollutant: str) -> dict[str, Any]:
    """La légende sérialisable d'un polluant — versionnée et sourcée.

    C'est elle qui part dans l'alias JSON des tuiles (§19.1) : le front la
    lit au lieu de recopier des seuils qui deviendraient faux à la première
    révision.
    """
    return {
        "version": PALETTE_VERSION,
        "source": PALETTE_SOURCE,
        "unite": "µg/m³",
        "bandes": [
            {"jusqu_a": band.upper, "couleur": band.color, "libelle": band.label}
            for band in BANDS[pollutant]
        ],
    }


__all__ = [
    "BANDS",
    "PALETTE_SOURCE",
    "PALETTE_VERSION",
    "PaletteBand",
    "band_for",
    "color_rgb",
    "legend",
    "thresholds",
]
