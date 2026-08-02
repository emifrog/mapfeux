"""Vigilance météorologique Météo-France, format V6.

Référence : cahier §9.2 et §16.1, stratégie §4.

L'API temps réel de `public-api.meteofrance.fr` exige une clé. Les mêmes
produits sont publiés sans clé sur le dépôt objet de data.gouv.fr, sous Licence
Ouverte Etalab v2 : c'est cette voie qu'on emprunte, ce qui évite d'attendre
l'ouverture d'un compte.

Le cahier §9.2 impose un **adaptateur** parce que le portail de Météo-France est
en migration. L'accès est donc isolé derrière `VigilanceClient`, et l'analyse
derrière des fonctions pures : changer de point d'accès ne doit toucher ni
l'interprétation du format, ni ce qui est écrit en base.

## Ce que le format impose

Les correspondances de codes viennent du « Descriptif technique des informations
Vigilance METROPOLE », pas de la mémoire :

- `color_id` : 1 vert, 2 jaune, 3 orange, 4 rouge ;
- `domain_id` : « FRA » pour la France, « dd » pour un département, « dd10 »
  pour son pourtour littoral, « ZDF_xxx » pour une zone de défense ;
- avant six heures locales, le produit ne comporte pas d'échéance « J1 ».

Un piège explicite du descriptif : **pour les crues, les tableaux de chronologie
sont vides**. Un analyseur qui lirait `timelaps_items` perdrait silencieusement
toute vigilance crue. On lit donc `phenomenon_max_color_id`, qui est renseigné
dans tous les cas et qui est de toute façon la grandeur affichée.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

TREE_URL = (
    "https://console.object.files.data.gouv.fr/api/v1/buckets/meteofrance/"
    "objects/download?prefix=data/vigilance/vigilance-hexagone-tree.json"
)
BULLETIN_BASE = (
    "https://console.object.files.data.gouv.fr/api/v1/buckets/meteofrance/"
    "objects/download?prefix=data/vigilance/metropole"
)
CARTE_FILE = "CDP_CARTE_EXTERNE.json"

#: Diffusions inspectées avant d'abandonner. La carte paraît au moins deux fois
#: par jour : n'en trouver aucune sur une vingtaine de diffusions signale une
#: panne de la source, pas un bulletin de suivi isolé.
MAX_LOOKBACK = 20

COLOURS: dict[int, str] = {1: "vert", 2: "jaune", 3: "orange", 4: "rouge"}

# « 06 » ou « 2A » ; « 0610 » désigne le pourtour littoral du même département.
DEPARTMENT = re.compile(r"^(\d{2}|2A|2B)$")
COASTAL = re.compile(r"^(\d{2}|2A|2B)10$")


class VigilanceError(RuntimeError):
    """Le fournisseur n'a pas servi un bulletin exploitable."""


class VigilanceUnavailableError(VigilanceError):
    """Source injoignable ou réponse inutilisable."""


@dataclass(frozen=True)
class BulletinRef:
    """Emplacement d'un bulletin dans l'arborescence publiée."""

    year: str
    month: str
    day: str
    stamp: str

    @property
    def path(self) -> str:
        return f"{self.year}/{self.month}/{self.day}/{self.stamp}"


@dataclass(frozen=True)
class Bulletin:
    """Métadonnées d'une diffusion."""

    domain_id: str
    vigilance_version: str
    format_version: str
    published_at: datetime
    snapshot_id: str | None


@dataclass(frozen=True)
class Level:
    """Couleur maximale d'un phénomène, sur un domaine et une échéance."""

    domain_id: str
    department_code: str | None
    is_coastal: bool
    echeance: str
    phenomenon_id: int
    colour: str
    begin_at: datetime
    end_at: datetime


def parse_timestamp(raw: str) -> datetime:
    """Les horodatages du format sont en UTC, suffixés Z ou +00:00."""
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def latest_reference(tree: dict[str, Any]) -> BulletinRef:
    """Dernier bulletin de l'arborescence : année, mois, jour, heure maximaux.

    L'arborescence est un dictionnaire imbriqué dont les clés sont des chaînes
    numériques à largeur fixe ; leur ordre lexicographique est donc leur ordre
    chronologique.
    """
    if not tree:
        raise VigilanceUnavailableError("Arborescence vigilance vide.")

    # Toutes les diffusions ne portent pas la carte : le produit « textes » est
    # émis seul lorsque la situation l'exige, et il apparaît alors dans
    # l'arborescence comme n'importe quel autre bulletin. Exiger la carte dans
    # la diffusion la plus récente ferait échouer l'import à chaque bulletin de
    # suivi, alors que la carte précédente reste la dernière valide.
    inspected = 0
    for year in sorted(tree, reverse=True):
        for month in sorted(tree[year], reverse=True):
            for day in sorted(tree[year][month], reverse=True):
                for stamp in sorted(tree[year][month][day], reverse=True):
                    if CARTE_FILE in tree[year][month][day][stamp]:
                        return BulletinRef(year=year, month=month, day=day, stamp=stamp)
                    inspected += 1
                    if inspected >= MAX_LOOKBACK:
                        raise VigilanceUnavailableError(
                            f"Aucune carte parmi les {inspected} dernières diffusions."
                        )

    raise VigilanceUnavailableError("Aucune carte dans l'arborescence.")


def department_of(domain_id: str) -> tuple[str | None, bool]:
    """Département désigné par un domaine, et s'il s'agit du littoral.

    « FRA » et les zones de défense ne désignent aucun département : forcer une
    valeur y inventerait un rattachement.
    """
    if DEPARTMENT.match(domain_id):
        return domain_id, False
    coastal = COASTAL.match(domain_id)
    if coastal:
        return coastal.group(1), True
    return None, False


def parse_carte(payload: dict[str, Any]) -> tuple[Bulletin, list[Level], list[str]]:
    """Analyse le produit « carte ». Retourne le bulletin, ses niveaux, les rejets.

    Une anomalie sur un domaine est **rejetée et comptée**, jamais silencieuse :
    un bulletin partiellement lisible vaut mieux qu'un import perdu, à condition
    que /statut montre ce qui a été écarté (§16.2).
    """
    product = payload.get("product")
    if not isinstance(product, dict):
        raise VigilanceError("Bloc « product » absent.")

    if product.get("warning_type") != "vigilance":
        raise VigilanceError(f"Produit inattendu : {product.get('warning_type')!r}")

    try:
        bulletin = Bulletin(
            domain_id=str(product["domain_id"]),
            vigilance_version=str(product["version_vigilance"]),
            format_version=str(product["version_cdp"]),
            published_at=parse_timestamp(str(product["update_time"])),
            snapshot_id=_snapshot_id(payload),
        )
    except KeyError as exc:
        raise VigilanceError(f"Champ obligatoire absent : {exc.args[0]}") from exc

    levels: list[Level] = []
    rejections: list[str] = []

    for period in product.get("periods", []):
        echeance = str(period.get("echeance", ""))
        if echeance not in ("J", "J1"):
            rejections.append(f"échéance inconnue : {echeance!r}")
            continue

        try:
            begin_at = parse_timestamp(str(period["begin_validity_time"]))
            end_at = parse_timestamp(str(period["end_validity_time"]))
        except (KeyError, ValueError) as exc:
            rejections.append(f"échéance {echeance} sans validité exploitable : {exc}")
            continue

        if end_at <= begin_at:
            rejections.append(f"échéance {echeance} de durée nulle ou négative")
            continue

        for domain in period.get("timelaps", {}).get("domain_ids", []):
            domain_id = str(domain.get("domain_id", ""))
            if domain_id == "":
                rejections.append("domaine sans identifiant")
                continue

            department_code, is_coastal = department_of(domain_id)

            for item in domain.get("phenomenon_items", []):
                try:
                    phenomenon_id = int(item["phenomenon_id"])
                    colour_id = int(item["phenomenon_max_color_id"])
                except (KeyError, TypeError, ValueError) as exc:
                    rejections.append(f"{domain_id} {echeance} : phénomène illisible ({exc})")
                    continue

                colour = COLOURS.get(colour_id)
                if colour is None:
                    rejections.append(f"{domain_id} {echeance} : couleur inconnue {colour_id}")
                    continue

                levels.append(
                    Level(
                        domain_id=domain_id,
                        department_code=department_code,
                        is_coastal=is_coastal,
                        echeance=echeance,
                        phenomenon_id=phenomenon_id,
                        colour=colour,
                        begin_at=begin_at,
                        end_at=end_at,
                    )
                )

    if not levels:
        raise VigilanceError("Bulletin sans aucun niveau exploitable.")

    return bulletin, levels, rejections


def _snapshot_id(payload: dict[str, Any]) -> str | None:
    meta = payload.get("meta")
    if isinstance(meta, dict) and meta.get("snapshot_id") is not None:
        return str(meta["snapshot_id"])
    return None


def highest_colour(levels: list[Level]) -> str:
    """Couleur la plus élevée d'un ensemble, dans l'ordre officiel."""
    order = {name: value for value, name in COLOURS.items()}
    return max(levels, key=lambda level: order[level.colour]).colour if levels else "vert"


class VigilanceClient:
    """Accès au dépôt public. Le point d'accès est remplaçable (§9.2)."""

    def __init__(
        self,
        client: httpx.Client,
        tree_url: str = TREE_URL,
        bulletin_base: str = BULLETIN_BASE,
    ) -> None:
        self._client = client
        self._tree_url = tree_url
        self._bulletin_base = bulletin_base

    def fetch_tree(self) -> dict[str, Any]:
        return self._json(self._tree_url)

    def bulletin_url(self, reference: BulletinRef) -> str:
        return f"{self._bulletin_base}/{reference.path}/{CARTE_FILE}"

    def fetch_carte(self, reference: BulletinRef) -> tuple[str, str]:
        """Retourne l'URL et le corps brut, non analysé.

        Le corps est rendu tel quel pour être archivé avant toute
        interprétation : un changement de format se diagnostique sur la donnée
        reçue, pas sur ce qu'on en a compris.
        """
        url = self.bulletin_url(reference)
        response = self._get(url)
        return url, response.text

    def _json(self, url: str) -> dict[str, Any]:
        payload = self._get(url).json()
        if not isinstance(payload, dict):
            raise VigilanceUnavailableError(f"Réponse JSON inattendue : {type(payload).__name__}")
        return payload

    def _get(self, url: str) -> httpx.Response:
        try:
            response = self._client.get(url, timeout=60, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise VigilanceUnavailableError(f"Source injoignable ({type(exc).__name__})") from exc

        if response.status_code != 200:
            raise VigilanceUnavailableError(f"HTTP {response.status_code}")
        return response


__all__ = [
    "COLOURS",
    "Bulletin",
    "BulletinRef",
    "Level",
    "VigilanceClient",
    "VigilanceError",
    "VigilanceUnavailableError",
    "department_of",
    "highest_colour",
    "latest_reference",
    "parse_carte",
    "parse_timestamp",
]
