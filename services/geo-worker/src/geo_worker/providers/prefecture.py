"""Pages d'actualités préfectorales — capture en liste blanche.

Référence : cahier v2.1 §9.2 et §20.4, FR-141 à FR-143 ; ADR-026 ; plan J4.

Les sites préfectoraux nouvelle génération (`*.gouv.fr`, gabarit commun de
l'État) n'exposent plus de flux RSS — sondé le 26 août sur le Var et les
Alpes-Maritimes : les chemins historiques rendent du HTML ou du 404. La
capture lit donc la page « Actualités » elle-même : des cartes DSFR dont
seules les **datées** (« Publié le jj/mm/aaaa ») sont des publications —
les cartes sans date sont la navigation des rubriques, et se filtrent par
ce seul critère, constaté sur les deux sites pilotes.

Ce que la capture rend est une **citation** : titre verbatim (seuls les
blancs de mise en page sont repliés), URL absolue, date annoncée par
l'autorité — au jour, aucune heure n'est inventée. Un lien qui sortirait
du domaine de l'autorité est rejeté et compté : la liste blanche ne
republie jamais ce qu'elle n'a pas vu chez l'autorité elle-même (ADR-026).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin, urlparse

#: « Publié le 20/08/2026 » — la seule forme observée sur le gabarit commun.
PUBLISHED = re.compile(r"Publié le\s+(\d{2})/(\d{2})/(\d{4})")


@dataclass(frozen=True)
class FeedItem:
    """Une publication captée : la citation, rien d'autre."""

    title: str
    url: str
    published_on: date


def parse_actualites(html: str, *, base_url: str) -> tuple[list[FeedItem], list[str]]:
    """Extrait les publications datées d'une page d'actualités DSFR.

    Une anomalie est **rejetée et comptée**, jamais silencieuse : une page
    restructurée doit se voir sur `/statut`, pas republier du bruit sous le
    nom d'une préfecture (ADR-026).
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    authority_host = urlparse(base_url).netloc

    items: list[FeedItem] = []
    rejections: list[str] = []
    seen: set[str] = set()

    for card in soup.select("div.fr-card"):
        detail = card.select_one(".fr-card__detail")
        if detail is None:
            # Carte de rubrique : de la navigation, pas une publication.
            continue

        detail_text = " ".join(detail.get_text().split())
        stamp = PUBLISHED.search(detail_text)
        if stamp is None:
            rejections.append(f"carte datée illisible : {detail_text[:60]!r}")
            continue

        link = card.select_one(".fr-card__title a")
        href = link.get("href") if link is not None else None
        if link is None or not isinstance(href, str) or href.strip() == "":
            rejections.append(f"carte sans lien de titre ({detail_text[:40]!r})")
            continue

        url = urljoin(base_url, href.strip())
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != authority_host:
            rejections.append(f"lien hors du domaine de l'autorité : {url}")
            continue

        title = " ".join(link.get_text().split())
        if title == "":
            rejections.append(f"carte sans titre : {url}")
            continue

        day, month, year = (int(group) for group in stamp.groups())
        try:
            published_on = date(year, month, day)
        except ValueError:
            rejections.append(f"date invalide : {stamp.group(0)!r} ({url})")
            continue

        if url in seen:
            continue
        seen.add(url)
        items.append(FeedItem(title=title, url=url, published_on=published_on))

    return items, rejections


__all__ = ["PUBLISHED", "FeedItem", "parse_actualites"]
