"""Capture des publications officielles de la liste blanche.

Référence : cahier v2.1 §9.2, §20.4, FR-141 à FR-143 ; ADR-026 ; plan J4.

La liste blanche vit en base (`app.official_feeds`) : la passe lit les
entrées actives, archive chaque page brute **avant** analyse (§16.1), et
range les publications datées en citations (`app.official_feed_items`).
L'upsert est une liste blanche de champs : le titre et la date suivent ce
que l'autorité publie — c'est **son** contenu, corrigé chez elle —,
`first_seen_at` et le run d'origine ne bougent jamais, et rien ne se
supprime : le masquage passe par `is_public`, geste d'administration.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg

from geo_worker.logging import get_logger
from geo_worker.providers.prefecture import FeedItem

logger = get_logger(__name__)


@dataclass(frozen=True)
class Feed:
    """Une entrée de la liste blanche, telle qu'en base."""

    id: UUID
    organisation: str
    feed_url: str
    kind: str
    department_code: str | None


def active_feeds(conn: psycopg.Connection[Any]) -> list[Feed]:
    """Les entrées actives de la liste blanche, ordre stable."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select id, organisation, feed_url, kind, department_code
            from app.official_feeds
            where is_active
            order by department_code nulls last, feed_url
            """
        )
        return [
            Feed(
                id=UUID(str(row[0])),
                organisation=str(row[1]),
                feed_url=str(row[2]),
                kind=str(row[3]),
                department_code=str(row[4]) if row[4] is not None else None,
            )
            for row in cur.fetchall()
        ]


def normalise_text(text: str) -> str:
    """Minuscules, sans accents, tirets et apostrophes en espaces.

    C'est la normalisation des deux côtés du rapprochement — le titre capté
    et le nom du référentiel — pour que « Sainte-Maxime » rencontre
    « SAINTE MAXIME » sans qu'aucun des deux ne soit réécrit nulle part.
    """
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    # L'apostrophe typographique est voulue : les titres préfectoraux
    # l'emploient (« Mesures d'interdictions » en porte une droite, d'autres
    # la courbe) — les deux valent séparateur.
    return " ".join(re.sub(r"[-'’]", " ", stripped).split())  # noqa: RUF001


def detect_municipalities(title: str, municipalities: Sequence[tuple[str, str]]) -> list[str]:
    """Codes INSEE des communes dont le **nom entier** figure dans le titre.

    Le rapprochement du §2.4 : un appariement de structure, jamais une
    lecture — frontière de mot exigée (« Toulon » ne se trouve pas dans
    « Toulonnais »), nom complet exigé (« Maxime » seul ne désigne pas
    Sainte-Maxime). Les codes sortent triés : le résultat est déterministe.
    """
    haystack = f" {normalise_text(title)} "
    found: set[str] = set()
    for insee, name in municipalities:
        needle = normalise_text(name)
        if needle and f" {needle} " in haystack:
            found.add(insee)
    return sorted(found)


def department_municipalities(
    conn: psycopg.Connection[Any], department_code: str
) -> list[tuple[str, str]]:
    """Le référentiel des communes vivantes d'un département : (INSEE, nom)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select insee_code, name from geo.municipalities
            where department_code = %(code)s and valid_to is null
            """,
            {"code": department_code},
        )
        return [(str(row[0]), str(row[1])) for row in cur.fetchall()]


def raw_object_name(feed: Feed, polled_at: datetime) -> str:
    """`prefectures/83/2026/08/26/actualites-142530.html` — daté, par feed."""
    department = feed.department_code or "xx"
    stamp = polled_at.astimezone(UTC)
    return f"prefectures/{department}/{stamp:%Y/%m/%d}/actualites-{stamp:%H%M%S}.html"


def mark_polled(conn: psycopg.Connection[Any], *, feed_id: UUID, http_status: int) -> None:
    """Consigne la sonde sur l'entrée de liste blanche — panne comprise."""
    with conn.cursor() as cur:
        cur.execute(
            """
            update app.official_feeds
            set last_polled_at = now(), last_http_status = %(status)s
            where id = %(feed_id)s
            """,
            {"feed_id": feed_id, "status": http_status},
        )


@dataclass(frozen=True)
class RecordResult:
    """Ce qu'une page captée a laissé : créations et re-visites."""

    inserted: int
    refreshed: int


def record_items(
    conn: psycopg.Connection[Any],
    *,
    feed_id: UUID,
    items: list[FeedItem],
    import_run_id: str | None,
    municipalities: Sequence[tuple[str, str]] | None = None,
) -> RecordResult:
    """Range les citations — liste blanche de champs, jamais de suppression.

    En conflit sur (feed, URL), le titre, la date et les communes détectées
    suivent l'autorité — elle corrige chez elle, la citation suit — mais
    `first_seen_at`, `is_public` et le run d'origine ne bougent pas : la
    première capture et le masquage administratif survivent aux passes.
    """
    inserted = 0
    refreshed = 0
    with conn.cursor() as cur:
        for item in items:
            codes = detect_municipalities(item.title, municipalities or [])
            cur.execute(
                """
                insert into app.official_feed_items
                  (feed_id, title, url, published_on, municipality_insee_codes,
                   import_run_id)
                values (%(feed_id)s, %(title)s, %(url)s, %(published_on)s,
                        %(codes)s, %(run_id)s)
                on conflict (feed_id, url) do update set
                  title = excluded.title,
                  published_on = excluded.published_on,
                  municipality_insee_codes = excluded.municipality_insee_codes,
                  last_seen_at = now()
                returning (xmax = 0) as inserted
                """,
                {
                    "feed_id": feed_id,
                    "title": item.title,
                    "url": item.url,
                    "published_on": item.published_on,
                    "codes": codes,
                    "run_id": import_run_id,
                },
            )
            row = cur.fetchone()
            if row is not None and bool(row[0]):
                inserted += 1
            else:
                refreshed += 1

    logger.info(
        "official_feeds.recorded",
        feed_id=str(feed_id),
        inserted=inserted,
        refreshed=refreshed,
    )
    return RecordResult(inserted=inserted, refreshed=refreshed)


__all__ = [
    "Feed",
    "RecordResult",
    "active_feeds",
    "department_municipalities",
    "detect_municipalities",
    "mark_polled",
    "normalise_text",
    "raw_object_name",
    "record_items",
]
