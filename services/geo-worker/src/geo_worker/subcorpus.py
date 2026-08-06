"""Sous-corpus stratifié pour le balayage de calibration.

Référence : cahier §17.2 et §24.8 ; plan de développement §2.

Sur le corpus complet, un jeu de paramètres coûte plus de dix minutes : les 112
combinaisons du balayage croisé demanderaient une vingtaine d'heures. Le
sous-corpus réduit ce coût d'un ordre de grandeur en ne conservant que les
situations qui **départagent** les réglages. Il sert à écarter les mauvais
jeux ; les finalistes sont rejoués une fois sur les quatorze saisons — le
classement se fait ici, la validation se fait là-bas.

Chaque strate correspond à un cas de la recette métier (§24.8) et à un mode
d'échec connu du regroupement :

- un **grand feu de plaine** multi-jours — le chaînage et la fragmentation s'y
  voient à grande échelle ;
- un **grand feu en relief littoral** — la géométrie des vallées éprouve la
  fenêtre spatiale autrement que la plaine ;
- une **zone industrielle sur une année** — des torchères détectées toute
  l'année ne doivent pas devenir un « événement » de plusieurs semaines ;
- la **saison pilote 06/83** — continuité avec l'événement de référence
  (Pontevès) et avec le flux NRT réel, qui ne porte pas la colonne `type` ;
- un **été épars** — la longue traîne d'observations isolées, majoritaire en
  nombre d'événements.

La sélection est une politique versionnée, comme les paramètres du
regroupement : mêmes strates, même corpus d'entrée, même sous-corpus — empreinte
comprise. Les bornes sont des demi-intervalles ``[début, fin[`` en UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from geo_worker.corpus import CorpusError, canonical_order, content_fingerprint, summarise

#: Version de la politique de sélection. Toute modification des strates change
#: la version : deux CSV de banc établis sur des sous-corpus différents ne se
#: comparent pas.
SUBCORPUS_VERSION = "sous-corpus-v1"

#: Colonnes sans lesquelles la sélection ou son compte rendu n'ont pas de sens.
#: Les trois premières portent la sélection ; les autres servent l'ordre
#: canonique, l'empreinte et la synthèse — le sous-corpus est le corpus complet
#: restreint, pas un format allégé.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "corpus",
    "detected_at",
    "latitude",
    "longitude",
    "satellite",
    "type",
)


@dataclass(frozen=True)
class Stratum:
    """Une fenêtre spatiale et temporelle du corpus, avec son motif.

    Le motif fait partie de la définition : une strate dont on ne peut plus
    dire ce qu'elle départage est une strate à supprimer, pas à conserver.
    """

    key: str
    reason: str
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float
    start: str
    end: str


#: Strates de la v1. Les effectifs mesurés à la constitution (6 août 2026)
#: figurent dans le compte rendu écrit à côté du Parquet, pas ici : le corpus
#: d'entrée peut être rafraîchi, les strates ne bougent qu'avec la version.
STRATA: tuple[Stratum, ...] = (
    Stratum(
        key="grand-feu-gironde-2022",
        reason=(
            "Grands feux de La Teste-de-Buch, Landiras et Saumos : le cas "
            "« grand feu avec multiples détections » de la recette (§24.8). "
            "Un réglage serré le fragmente, un réglage lâche y chaîne des "
            "foyers distincts — les deux fautes s'y mesurent."
        ),
        lon_min=-1.45,
        lon_max=0.10,
        lat_min=44.10,
        lat_max=45.65,
        start="2022-06-01",
        end="2022-10-01",
    ),
    Stratum(
        key="relief-var-2021",
        reason=(
            "Feu de Gonfaron (août 2021) : zone montagneuse et littorale de la "
            "recette. Le relief resserre les distances au sol que la fenêtre "
            "spatiale mesure à vol d'oiseau."
        ),
        lon_min=5.55,
        lon_max=7.80,
        lat_min=42.90,
        lat_max=44.45,
        start="2021-06-01",
        end="2021-10-01",
    ),
    Stratum(
        key="industriel-berre-2023",
        reason=(
            "Étang de Berre et Fos-sur-Mer sur une année pleine, très "
            "majoritairement type 2 : le faux positif industriel récurrent de "
            "la recette. Des torchères détectées toute l'année ne doivent pas "
            "être chaînées en événement de plusieurs semaines."
        ),
        lon_min=4.70,
        lon_max=5.25,
        lat_min=43.30,
        lat_max=43.60,
        start="2023-01-01",
        end="2024-01-01",
    ),
    Stratum(
        key="pilote-0683-2026",
        reason=(
            "Saison courante des territoires pilotes, dont l'événement de "
            "référence de Pontevès. Données NRT sans colonne type, comme le "
            "flux que l'ingestion lit toutes les dix minutes."
        ),
        lon_min=5.55,
        lon_max=7.80,
        lat_min=42.90,
        lat_max=44.45,
        start="2026-05-01",
        end="2026-08-03",
    ),
    Stratum(
        key="fond-epars-0683-2018",
        reason=(
            "Été calme sur les mêmes territoires : la longue traîne des "
            "observations isolées, majoritaire en nombre d'événements. Un "
            "réglage ne doit pas la faire disparaître en l'absorbant."
        ),
        lon_min=5.55,
        lon_max=7.80,
        lat_min=42.90,
        lat_max=44.45,
        start="2018-06-01",
        end="2018-10-01",
    ),
)


def stratum_mask(frame: pd.DataFrame, stratum: Stratum) -> pd.Series[bool]:
    """Lignes du corpus appartenant à la strate."""
    start = pd.Timestamp(stratum.start, tz="UTC")
    end = pd.Timestamp(stratum.end, tz="UTC")
    return (
        frame["longitude"].between(stratum.lon_min, stratum.lon_max)
        & frame["latitude"].between(stratum.lat_min, stratum.lat_max)
        & (frame["detected_at"] >= start)
        & (frame["detected_at"] < end)
    )


def extract(
    frame: pd.DataFrame, strata: tuple[Stratum, ...] = STRATA
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Extrait le sous-corpus : union des strates, chaque ligne une fois.

    Toutes les colonnes du corpus sont conservées telles quelles : le
    sous-corpus se charge par le même importeur, et une observation y porte la
    même clé d'idempotence que dans le corpus complet.

    Une strate vide arrête l'extraction. Une fenêtre qui ne sélectionne rien
    est une définition morte — corpus d'entrée tronqué ou strate mal bornée —
    et un sous-corpus auquel il manque une situation entière mesurerait autre
    chose que ce qu'annonce sa version.
    """
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise CorpusError(f"Colonnes absentes du corpus : {', '.join(sorted(missing))}")

    keys = [stratum.key for stratum in strata]
    if len(set(keys)) != len(keys):
        raise CorpusError("Deux strates portent la même clé.")

    union = pd.Series(False, index=frame.index)
    per_stratum: dict[str, dict[str, Any]] = {}
    total_per_stratum = 0

    for stratum in strata:
        mask = stratum_mask(frame, stratum)
        count = int(mask.sum())
        if count == 0:
            raise CorpusError(
                f"Strate {stratum.key} : aucune ligne sélectionnée. "
                "Corpus d'entrée incomplet ou strate mal bornée."
            )
        total_per_stratum += count
        union = union | mask
        per_stratum[stratum.key] = {
            "lignes": count,
            "motif": stratum.reason,
            "bbox": [stratum.lon_min, stratum.lat_min, stratum.lon_max, stratum.lat_max],
            "periode": [stratum.start, stratum.end],
        }

    selection = canonical_order(frame[union])

    stats: dict[str, Any] = {
        "version": SUBCORPUS_VERSION,
        "lignes": len(selection),
        "lignes_corpus": len(frame),
        "part_du_corpus_pct": (
            0.0 if len(frame) == 0 else round(100 * len(selection) / len(frame), 1)
        ),
        # Lignes comptées par plusieurs strates : présentes une seule fois dans
        # la sélection, mais le chiffre dit si deux fenêtres se recouvrent.
        "recouvrement_strates": total_per_stratum - len(selection),
        "empreinte_contenu": content_fingerprint(selection),
        "strates": per_stratum,
        "synthese": summarise(selection),
    }
    return selection, stats


__all__ = [
    "REQUIRED_COLUMNS",
    "STRATA",
    "SUBCORPUS_VERSION",
    "Stratum",
    "extract",
    "stratum_mask",
]
