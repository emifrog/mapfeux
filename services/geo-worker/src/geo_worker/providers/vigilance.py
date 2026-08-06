"""Vigilance météorologique Météo-France, format V6.

Référence : cahier §9.2 et §16.1, stratégie §4.

Deux voies d'accès, et le choix entre elles n'est pas indifférent.

**Temps réel** — `public-api.meteofrance.fr`, avec clé. C'est la voie nominale.

**Dépôt objet data.gouv.fr** — sans clé, sous Licence Ouverte Etalab v2. Elle a
d'abord été retenue pour éviter d'attendre l'ouverture d'un compte, et la mesure
a montré ce qu'elle coûte : le jeu s'appelle `vigilance-meteorologique-archivee`,
et c'est une archive. Sondé le 6 août à 9 h UTC, il s'arrêtait au bulletin du
5 août 4 h — vingt-neuf heures de retard, là où le registre déclare la source
périmée au-delà de vingt. La vigilance affichait donc « Trop ancienne » en
permanence : un signal exact et faux, qui apprend à ignorer l'indicateur.

Le repli reste possible, mais il est **annoncé** : la voie employée est
consignée dans l'`import_run`, et la fraîcheur affichée reste celle du bulletin,
non celle de l'import. Servir sans le dire de la donnée d'hier serait pire que
ne rien servir.

Le cahier §9.2 impose un **adaptateur** parce que le portail de Météo-France est
en migration. L'accès est donc isolé derrière `VigilanceClient`, et l'analyse
derrière des fonctions pures : changer de point d'accès ne doit toucher ni
l'interprétation du format, ni ce qui est écrit en base. C'est ce qui rend ce
basculement local — seule la récupération change, `parse_carte` est intacte, les
deux voies servant le même produit « carte ».

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
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

#: Carte de vigilance en cours, API temps réel. Exige une clé de l'espace
#: développeur Météo-France (application « Bulletin Vigilance »), présentée en
#: en-tête `apikey`. Quota annoncé : 60 requêtes par minute, très au-delà d'une
#: passe horaire.
LIVE_CARTE_URL = "https://public-api.meteofrance.fr/public/DPVigilance/v1/cartevigilance/encours"

TREE_URL = (
    "https://console.object.files.data.gouv.fr/api/v1/buckets/meteofrance/"
    "objects/download?prefix=data/vigilance/vigilance-hexagone-tree.json"
)
BULLETIN_BASE = (
    "https://console.object.files.data.gouv.fr/api/v1/buckets/meteofrance/"
    "objects/download?prefix=data/vigilance/metropole"
)
CARTE_FILE = "CDP_CARTE_EXTERNE.json"

#: Voie effectivement empruntée, consignée dans l'`import_run`. Sans elle, une
#: donnée vieille d'un jour serait indiscernable d'une donnée fraîche.
ACCESS_LIVE = "temps-reel"
ACCESS_ARCHIVE = "archive"

#: Variables portant la clé, par ordre de préférence.
#:
#: Le portail Météo-France délivre une clé **par application** — « Bulletin
#: Vigilance », « Données Publiques Radar », et ainsi de suite. Un nom générique
#: unique deviendrait donc faux dès la seconde application : on ne saurait plus
#: laquelle il porte, et poser la mauvaise produirait un 403 sans motif visible.
#:
#: Le nom générique reste lu en second, pour les environnements qui l'emploient
#: déjà. Il est déprécié, non supprimé : casser une configuration en place au
#: milieu d'une mise en service serait payer cher une cohérence de nommage.
API_KEY_VARIABLES: tuple[str, ...] = (
    "METEOFRANCE_VIGILANCE_API_KEY",
    "METEOFRANCE_API_KEY",
)


def api_key_from(env: Mapping[str, str]) -> str:
    """Clé de l'application « Bulletin Vigilance », ou chaîne vide.

    Un secret non renseigné arrive en chaîne vide chez un ordonnanceur, jamais
    en variable absente : les deux cas se traitent donc de la même façon.
    """
    for name in API_KEY_VARIABLES:
        value = env.get(name, "").strip()
        if value != "":
            return value
    return ""


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


@dataclass(frozen=True)
class Fetched:
    """Un produit « carte » récupéré, et par quelle voie."""

    access: str
    url: str
    body: str
    label: str
    """Nom de la diffusion, pour l'archive.

    C'est l'adaptateur qui le connaît : l'horodatage de la diffusion côté dépôt,
    « encours » côté temps réel, dont l'URL n'expose aucun chemin. Le déduire de
    l'URL a produit des objets nommés `CDP_CARTE_EXTERNE.json.json`, identiques
    d'un bulletin à l'autre — une archive qui ne dit pas ce qu'elle archive.
    """

    @property
    def is_live(self) -> bool:
        return self.access == ACCESS_LIVE


class VigilanceClient:
    """Accès au produit « carte ». Le point d'accès est remplaçable (§9.2).

    Avec une clé, la voie temps réel. Sans clé, le dépôt objet — qui accuse un
    retard d'archive et le fait savoir.
    """

    def __init__(
        self,
        client: httpx.Client,
        api_key: str | None = None,
        tree_url: str = TREE_URL,
        bulletin_base: str = BULLETIN_BASE,
        live_url: str = LIVE_CARTE_URL,
    ) -> None:
        self._client = client
        self._api_key = (api_key or "").strip() or None
        self._tree_url = tree_url
        self._bulletin_base = bulletin_base
        self._live_url = live_url

    @property
    def has_key(self) -> bool:
        return self._api_key is not None

    def fetch_latest(self) -> Fetched:
        """Dernier produit « carte » disponible, par la meilleure voie ouverte.

        Sans clé, on ne tente même pas le temps réel : l'API répondrait 401, et
        transformer une configuration absente en panne réseau brouillerait le
        diagnostic.
        """
        if self._api_key is None:
            reference = latest_reference(self.fetch_tree())
            url = self.bulletin_url(reference)
            return Fetched(
                access=ACCESS_ARCHIVE,
                url=url,
                body=self._get(url).text,
                label=reference.path.replace("/", ""),
            )

        return Fetched(
            access=ACCESS_LIVE,
            url=self._live_url,
            body=self.fetch_live().text,
            label="encours",
        )

    def fetch_live(self) -> httpx.Response:
        """Carte en cours, API temps réel.

        La clé voyage en en-tête `apikey` et jamais dans l'URL : celle-ci
        atterrit dans les journaux des intermédiaires (§22.2), et c'est
        exactement le défaut qu'on a corrigé sur FIRMS le 5 août.
        """
        if self._api_key is None:
            raise VigilanceUnavailableError("Clé Météo-France absente.")

        try:
            response = self._client.get(
                self._live_url,
                headers={"apikey": self._api_key, "accept": "*/*"},
                timeout=60,
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            raise VigilanceUnavailableError(f"Source injoignable ({type(exc).__name__})") from exc

        if response.status_code in (401, 403):
            # Distinguer l'authentification du reste : une clé expirée se règle
            # au portail, pas en relançant la tâche.
            raise VigilanceUnavailableError(
                f"Clé Météo-France refusée (HTTP {response.status_code}). "
                "Vérifier l'application « Bulletin Vigilance » au portail."
            )
        if response.status_code == 429:
            raise VigilanceUnavailableError("Quota Météo-France atteint (HTTP 429).")
        if response.status_code != 200:
            raise VigilanceUnavailableError(f"HTTP {response.status_code}")

        return response

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
    "ACCESS_ARCHIVE",
    "ACCESS_LIVE",
    "API_KEY_VARIABLES",
    "COLOURS",
    "LIVE_CARTE_URL",
    "Bulletin",
    "BulletinRef",
    "Fetched",
    "Level",
    "VigilanceClient",
    "VigilanceError",
    "VigilanceUnavailableError",
    "api_key_from",
    "department_of",
    "highest_colour",
    "latest_reference",
    "parse_carte",
    "parse_timestamp",
]
