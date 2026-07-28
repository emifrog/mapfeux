"""Règles de regroupement des détections en événements.

Référence : cahier §17.2 et §17.3.

Ce module ne contient que des fonctions pures : c'est le seul moyen de tenir le
critère de sortie du jalon, « deux exécutions successives donnent le même
résultat ». Un algorithme dont les seuils vivent dans une requête SQL ne se
calibre pas et ne se teste pas.

Les paramètres sont versionnés et enregistrés avec chaque rattachement. Changer
un seuil sans changer la version rendrait un ancien résultat inexplicable.
"""

from __future__ import annotations

from dataclasses import dataclass

# Fenêtre spatiale : un feu s'étend, donc la tolérance croît avec le temps
# écoulé depuis la dernière observation de l'événement. Les valeurs de départ
# sont celles du cahier §17.2, à calibrer sur corpus historique.
DEFAULT_BASE_RADIUS_M = 2_500.0
DEFAULT_GROWTH_M_PER_HOUR = 500.0
DEFAULT_MAX_RADIUS_M = 12_000.0
DEFAULT_ATTACH_WINDOW_HOURS = 24.0
DEFAULT_MIN_SCORE = 0.35


@dataclass(frozen=True, slots=True)
class ClusteringParams:
    """Paramètres versionnés du rattachement."""

    version: str = "grouping-v1"
    base_radius_m: float = DEFAULT_BASE_RADIUS_M
    growth_m_per_hour: float = DEFAULT_GROWTH_M_PER_HOUR
    max_radius_m: float = DEFAULT_MAX_RADIUS_M
    attach_window_hours: float = DEFAULT_ATTACH_WINDOW_HOURS
    min_score: float = DEFAULT_MIN_SCORE

    def __post_init__(self) -> None:
        if self.base_radius_m <= 0 or self.max_radius_m < self.base_radius_m:
            raise ValueError("Rayons incohérents.")
        if self.attach_window_hours <= 0:
            raise ValueError("Fenêtre de rattachement nulle ou négative.")
        if not 0 < self.min_score <= 1:
            raise ValueError("Seuil de rattachement hors de ]0, 1].")


def spatial_window_m(hours_elapsed: float, params: ClusteringParams) -> float:
    """Rayon de tolérance pour un délai donné, plafonné.

    Le plafond n'est pas décoratif : sans lui, un événement inactif depuis
    vingt heures happerait toute détection dans un rayon de douze kilomètres,
    et deux feux distincts d'une même vallée finiraient confondus.
    """
    if hours_elapsed < 0:
        raise ValueError("Délai négatif : les détections sont traitées chronologiquement.")

    radius = params.base_radius_m + params.growth_m_per_hour * hours_elapsed
    return min(radius, params.max_radius_m)


def attachment_score(
    *,
    distance_m: float,
    hours_elapsed: float,
    params: ClusteringParams,
) -> float:
    """Score de rattachement d'une détection à un événement, dans [0, 1].

    Deux composantes, multipliées plutôt qu'additionnées : une détection très
    proche mais très ancienne ne doit pas être rattachée sur la seule force de
    sa proximité. Une somme pondérée le permettrait, un produit non.
    """
    if distance_m < 0:
        raise ValueError("Distance négative.")

    window = spatial_window_m(hours_elapsed, params)
    if distance_m > window or hours_elapsed > params.attach_window_hours:
        return 0.0

    proximity = 1.0 - (distance_m / window)
    recency = 1.0 - (hours_elapsed / params.attach_window_hours)

    return round(proximity * recency, 6)


def confidence_score(
    *,
    detection_count: int,
    sensor_count: int,
    mean_provider_confidence: float | None,
    known_source_count: int,
    span_hours: float,
) -> float:
    """Fiabilité interne d'un événement, dans [0, 1]. Cahier §17.3.

    Composantes retenues : confiance fournisseur moyenne, répétition sur
    plusieurs passages, présence de plusieurs capteurs, persistance temporelle,
    et pénalité de proximité d'une source thermique connue.

    Ce score n'est **jamais** affiché tel quel : il est publié sous forme de
    trois niveaux, et ne qualifie ni la gravité ni la surface (FR-049).
    """
    if detection_count <= 0:
        return 0.0

    # Confiance fournisseur, valeur neutre lorsqu'elle est inconnue plutôt que
    # zéro : une confiance absente n'est pas une confiance nulle.
    base = 0.5 if mean_provider_confidence is None else mean_provider_confidence

    # Répétition : une détection isolée reste faible, le gain sature vite.
    repetition = min(detection_count / 6.0, 1.0)

    # Plusieurs capteurs indépendants observent le même phénomène : c'est le
    # signal le plus fort contre un artefact.
    multi_sensor = 1.0 if sensor_count >= 2 else 0.0

    # Persistance : un phénomène vu sur plusieurs heures n'est pas un reflet.
    persistence = min(span_hours / 6.0, 1.0)

    score = 0.40 * base + 0.25 * repetition + 0.20 * multi_sensor + 0.15 * persistence

    # Une majorité de détections sur source thermique connue rend l'événement
    # douteux en tant que feu. On ne le supprime pas — la classification n'est
    # pas une suppression (§17.7) — on abaisse sa fiabilité.
    if known_source_count > 0:
        known_ratio = min(known_source_count / detection_count, 1.0)
        score *= 1.0 - 0.6 * known_ratio

    return round(max(0.0, min(1.0, score)), 4)


def confidence_level(score: float) -> str:
    """Traduit le score interne en niveau publiable. Seuils versionnés (§17.3)."""
    if score >= 0.70:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"
