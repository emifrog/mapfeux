"""Interrupteurs de fonctions, côté worker — FR-106 et FR-155.

Lecture seule : couper est un geste humain (`scripts/toggle-feature.py`),
avec motif et journal d'audit. La résolution vit dans
`app.is_feature_enabled` — une seule définition pour le calcul, l'affichage
et l'API — et ce module se contente de la poser comme question.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg

#: Le panache indicatif (§18). Premier inscrit au registre, pas le dernier.
FEATURE_SMOKE_FORECAST = "smoke_forecast"


def feature_enabled(
    conn: psycopg.Connection[Any],
    feature: str,
    territory_id: UUID | None = None,
) -> bool:
    """Vrai si rien ne coupe la fonction pour cette portée."""
    row = conn.execute(
        "select app.is_feature_enabled(%(feature)s, %(territory)s)",
        {"feature": feature, "territory": territory_id},
    ).fetchone()
    return row is not None and bool(row[0])


def disabling_reasons(
    conn: psycopg.Connection[Any],
    feature: str,
    territory_id: UUID | None = None,
) -> list[str]:
    """Motifs des interrupteurs qui coupent, portée globale d'abord.

    Un refus sans motif apprendrait à contourner l'interrupteur ; le motif
    est ce qui le rend acceptable — et il est obligatoire à l'écriture.
    """
    rows = conn.execute(
        """
        select s.reason
        from app.feature_switches s
        where s.feature = %(feature)s
          and not s.is_enabled
          and (s.territory_id is null or s.territory_id = %(territory)s)
        order by s.territory_id is not null, s.updated_at desc
        """,
        {"feature": feature, "territory": territory_id},
    ).fetchall()
    return [str(row[0]) for row in rows]


__all__ = ["FEATURE_SMOKE_FORECAST", "disabling_reasons", "feature_enabled"]
