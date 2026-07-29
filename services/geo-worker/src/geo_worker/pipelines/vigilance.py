"""Enregistrement des bulletins de vigilance.

Référence : cahier §16.1, stratégie §4.

L'insertion est idempotente sur `(domain_id, published_at)` : Météo-France
diffuse au moins deux fois par jour et davantage si la situation l'exige, alors
que l'ingestion interroge plus souvent. La plupart des passages retrouvent donc
un bulletin déjà connu, et cela n'est ni une erreur ni un rejet — c'est le
fonctionnement normal, que /statut doit présenter comme tel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg

from geo_worker.logging import get_logger
from geo_worker.providers.vigilance import Bulletin, Level

logger = get_logger(__name__)


@dataclass
class StoreResult:
    bulletin_id: str | None = None
    already_known: bool = False
    levels_inserted: int = 0


def store_bulletin(
    conn: psycopg.Connection[Any],
    *,
    bulletin: Bulletin,
    levels: list[Level],
    source_url: str,
    checksum: str,
    raw: str,
    import_run_id: str | None = None,
) -> StoreResult:
    """Écrit un bulletin et ses niveaux. L'appelant gère la transaction."""
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into meteo.vigilance_bulletins (
              domain_id, vigilance_version, format_version, published_at,
              snapshot_id, source_url, checksum, raw, import_run_id
            )
            values (
              %(domain)s, %(vigilance)s, %(format)s, %(published)s,
              %(snapshot)s, %(url)s, %(checksum)s, %(raw)s::jsonb, %(run)s
            )
            on conflict (domain_id, published_at) do nothing
            returning id
            """,
            {
                "domain": bulletin.domain_id,
                "vigilance": bulletin.vigilance_version,
                "format": bulletin.format_version,
                "published": bulletin.published_at,
                "snapshot": bulletin.snapshot_id,
                "url": source_url,
                "checksum": checksum,
                "raw": raw,
                "run": import_run_id,
            },
        )
        row = cur.fetchone()

        if row is None:
            logger.info(
                "vigilance.already_known",
                domain=bulletin.domain_id,
                published_at=bulletin.published_at.isoformat(),
            )
            return StoreResult(already_known=True)

        bulletin_id = str(row[0])

        # Les niveaux sont écrits en un seul aller-retour : mille deux cents
        # lignes en autant de requêtes coûterait plus que tout le reste.
        cur.execute(
            """
            insert into meteo.vigilance_levels (
              bulletin_id, domain_id, department_code, is_coastal,
              echeance, phenomenon_id, colour, begin_at, end_at
            )
            select
              %(bulletin)s, t.domain_id, t.department_code, t.is_coastal,
              t.echeance, t.phenomenon_id, t.colour::meteo.vigilance_colour,
              t.begin_at, t.end_at
            from unnest(
              %(domains)s::text[], %(departments)s::text[], %(coastal)s::boolean[],
              %(echeances)s::text[], %(phenomena)s::smallint[], %(colours)s::text[],
              %(begins)s::timestamptz[], %(ends)s::timestamptz[]
            ) as t(
              domain_id, department_code, is_coastal,
              echeance, phenomenon_id, colour, begin_at, end_at
            )
            """,
            {
                "bulletin": bulletin_id,
                "domains": [level.domain_id for level in levels],
                "departments": [level.department_code for level in levels],
                "coastal": [level.is_coastal for level in levels],
                "echeances": [level.echeance for level in levels],
                "phenomena": [level.phenomenon_id for level in levels],
                "colours": [level.colour for level in levels],
                "begins": [level.begin_at for level in levels],
                "ends": [level.end_at for level in levels],
            },
        )

    logger.info(
        "vigilance.stored",
        bulletin_id=bulletin_id,
        published_at=bulletin.published_at.isoformat(),
        levels=len(levels),
    )
    return StoreResult(bulletin_id=bulletin_id, levels_inserted=len(levels))


__all__ = ["StoreResult", "store_bulletin"]
