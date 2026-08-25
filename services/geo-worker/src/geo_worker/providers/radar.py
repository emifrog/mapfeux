"""Mosaïque radar Météo-France — API « Données Publiques Radar » (DPRadar).

Référence : cahier §9.3 et §16.6 ; plan J9.

L'API est un arbre de liens à la mode OGC : `/mosaiques` liste les zones,
`/mosaiques/{zone}/observations` les produits, et le document d'un produit
pointe vers `produit?maille=...` — **seule la dernière production existe**,
il n'y a pas d'historique : la timeline se construit chez nous, une frame à
la fois, au rythme du produit (cinq minutes).

Deux mailles pour la lame d'eau : 1000 m en BUFR gzippé, 500 m en **HDF5
ODIM** — c'est celle-ci qu'on lit, le format est auto-descriptif (grille,
projection, gains) là où le BUFR exigerait des tables. Constaté sur pièce
le 25 août : `T_IPRN20_C_LFPW_<horodatage>.h5`, 1,8 Mo.

Même portail que la vigilance, mêmes règles : une clé **par application**
(« Données Publiques Radar » — celle de la vigilance produirait un 403 sans
motif), présentée en en-tête `apikey`, jamais dans l'URL (§22.2).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

BASE_URL = "https://public-api.meteofrance.fr/public/DPRadar/v1"

ZONE = "METROPOLE"
OBSERVATION = "LAME_D_EAU"

#: Maille demandée, en mètres. 500 sert le HDF5 ODIM ; 1000 sert du BUFR.
MAILLE = 500

#: Variable portant la clé. Une clé par application au portail : un nom
#: générique redeviendrait ambigu dès la seconde application (voir
#: `providers/vigilance.py`, même doctrine).
API_KEY_VARIABLES: tuple[str, ...] = ("METEOFRANCE_RADAR_API_KEY",)

#: Horodatage ISO dans les titres de liens du document produit —
#: « … du 2026-08-25T18:10:00Z ».
_TITLE_STAMP = re.compile(r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z\b")

#: Nom de fichier du produit, dans `content-disposition` —
#: « T_IPRN20_C_LFPW_20260825181000.h5 ».
_FILENAME_STAMP = re.compile(r"_(\d{14})\.h5")


class RadarError(RuntimeError):
    """Le fournisseur n'a pas servi un produit exploitable."""


class RadarAuthError(RadarError):
    """Clé refusée : se règle au portail, pas en relançant la tâche."""


def api_key_from(env: Mapping[str, str]) -> str:
    """Clé de l'application « Données Publiques Radar », ou chaîne vide."""
    for name in API_KEY_VARIABLES:
        value = env.get(name, "").strip()
        if value != "":
            return value
    return ""


def parse_title_stamp(document: dict[str, Any]) -> datetime | None:
    """L'horodatage du produit annoncé par le document de liens, s'il s'y lit.

    C'est une **optimisation**, pas un contrat : elle évite de retélécharger
    1,8 Mo toutes les cinq minutes quand la frame est déjà en base. Si le
    titre change de forme, on retélécharge — l'horodatage qui fait foi est
    celui du fichier lui-même (`what.date` + `what.time`).
    """
    for link in document.get("links", []):
        match = _TITLE_STAMP.search(str(link.get("title", "")))
        if match:
            return datetime.fromisoformat(match.group(1)).replace(tzinfo=UTC)
    return None


def parse_filename_stamp(content_disposition: str) -> datetime | None:
    """L'horodatage du nom de fichier servi, à défaut d'autre chose."""
    match = _FILENAME_STAMP.search(content_disposition)
    if match is None:
        return None
    return datetime.strptime(match.group(1), "%Y%m%d%H%M%S").replace(tzinfo=UTC)


@dataclass(frozen=True)
class RadarProduct:
    """Un produit téléchargé : les octets et ce que la réponse en disait."""

    payload: bytes
    filename: str | None
    announced_at: datetime | None


class RadarClient:
    """Accès au produit mosaïque. Le point d'accès est remplaçable (§9.2)."""

    def __init__(
        self,
        client: httpx.Client,
        api_key: str,
        base_url: str = BASE_URL,
        zone: str = ZONE,
        observation: str = OBSERVATION,
    ) -> None:
        if api_key.strip() == "":
            raise RadarAuthError("Clé « Données Publiques Radar » absente.")
        self._client = client
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._zone = zone
        self._observation = observation

    @property
    def _product_document_url(self) -> str:
        return f"{self._base_url}/mosaiques/{self._zone}/observations/{self._observation}"

    def announced_at(self) -> datetime | None:
        """L'horodatage de la dernière production, sans la télécharger."""
        response = self._get(self._product_document_url, accept="application/json")
        payload = response.json()
        if not isinstance(payload, dict):
            raise RadarError(f"Document de produit inattendu : {type(payload).__name__}.")
        return parse_title_stamp(payload)

    def fetch_product(self, maille: int = MAILLE) -> RadarProduct:
        """Télécharge la dernière mosaïque à la maille demandée."""
        response = self._get(
            f"{self._product_document_url}/produit",
            accept="*/*",
            params={"maille": maille},
        )
        disposition = response.headers.get("content-disposition", "")
        filename_match = re.search(r'filename="([^"]+)"', disposition)
        return RadarProduct(
            payload=response.content,
            filename=filename_match.group(1) if filename_match else None,
            announced_at=parse_filename_stamp(disposition),
        )

    def _get(
        self, url: str, *, accept: str, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        try:
            response = self._client.get(
                url,
                params=params,
                headers={"apikey": self._api_key, "accept": accept},
                timeout=120,
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            raise RadarError(f"Source injoignable ({type(exc).__name__}).") from exc

        if response.status_code in (401, 403):
            raise RadarAuthError(
                f"Clé Météo-France refusée (HTTP {response.status_code}). Vérifier "
                "l'application « Données Publiques Radar » au portail — la clé "
                "d'une autre application produit exactement ce refus."
            )
        if response.status_code == 429:
            raise RadarError("Quota Météo-France atteint (HTTP 429).")
        if response.status_code != 200:
            raise RadarError(f"HTTP {response.status_code} sur {url.split('?')[0]}.")
        return response


__all__ = [
    "API_KEY_VARIABLES",
    "BASE_URL",
    "MAILLE",
    "OBSERVATION",
    "ZONE",
    "RadarAuthError",
    "RadarClient",
    "RadarError",
    "RadarProduct",
    "api_key_from",
    "parse_filename_stamp",
    "parse_title_stamp",
]
