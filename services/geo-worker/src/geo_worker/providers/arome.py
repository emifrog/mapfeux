"""Paquets AROME de Météo-France, servis sans clé.

Référence : cahier §9.2 et §16.4, ADR-025 point 4.

## Pourquoi ce module existe avant le panache

ADR-025 fait dépendre l'archivage des champs AROME de la mise en service de
l'ingestion pour le panache. Or le panache a été retiré du MVP et reporté en v2
par la stratégie : le déclencheur pointe vers un jalon supprimé, et le corpus
n'aurait jamais commencé à s'accumuler.

Comme l'argument qui fonde cet archivage est que la donnée est **périssable** —
un jour non capté est perdu définitivement — le déclencheur est découplé. Ce
module ne calcule rien, n'affiche rien et ne dépend d'aucune autre partie du
produit : il capte, et c'est tout.

## Accès

L'API `public-api.meteofrance.fr` exige une clé, absente. Les mêmes paquets sont
publiés sur le dépôt objet de data.gouv.fr sous Licence Ouverte, avec une URL
prédictible. C'est cette voie qu'on emprunte, comme pour la vigilance.

## Ce qu'on archive, et pourquoi pas le paquet

Un paquet de surface pèse **environ 56 Mo par tranche de six heures**, mesuré.
En conserver un par jour ferait vingt gigaoctets par an — ADR-025 annonce un
coût « quasi gratuit », ce qui ne tient pas à cette échelle.

Le calcul FWI n'a besoin que de quatre champs, à une échéance par jour : c'est
un indice défini sur les observations de la mi-journée. On télécharge donc le
paquet, on en extrait ces quatre champs sur l'emprise voulue, et on ne conserve
que l'extrait — de l'ordre de deux ordres de grandeur en moins. Le paquet brut
n'est pas conservé : la règle « archiver le brut avant analyse » vaut pour ce
qu'on ne peut pas retrouver, or Météo-France republie ses paquets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from geo_worker.providers.models import BoundingBox

BASE_URL = "https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net/pnt"

#: Résolution retenue. 0,025° vaut environ 2,5 km, largement suffisant pour un
#: indice agrégé ensuite par massif ou par commune ; 0,01° quadruplerait le
#: volume pour une précision que l'agrégation effacerait.
RESOLUTION = "0025"

#: Paquet de surface : température, humidité, vent à 10 m et précipitations.
SURFACE_PACKAGE = "SP1"

#: Champs conservés, nommés comme cfgrib les expose.
FWI_FIELDS = ("t2m", "r2", "u10", "v10", "tp")

#: Emprise de l'extrait conservé : France métropolitaine et Corse.
#:
#: Le pilote ne couvre que deux départements, et s'y limiter coûterait presque
#: rien. Mais cette économie-là ne se rattrape pas : restreindre l'emprise
#: aujourd'hui, c'est décider que les saisons à venir n'existeront pas pour le
#: reste du pays. L'écart se compte en gigaoctets, donc en quelques euros par
#: an, contre des années de corpus perdues — le calcul n'est pas serré.
#:
#: Réduire l'emprise plus tard reste possible ; l'élargir rétroactivement, non.
ARCHIVE_EXTENT = BoundingBox(min_lon=-5.8, min_lat=41.0, max_lon=10.2, max_lat=51.5)

#: Météo-France diffuse un run toutes les trois heures.
RUN_HOURS = (0, 3, 6, 9, 12, 15, 18, 21)

#: Tranches d'échéances, telles que nommées dans les fichiers.
SPANS = ("00H06H", "07H12H", "13H18H", "19H24H", "25H30H", "31H36H", "37H42H", "43H48H")


class AromeError(RuntimeError):
    """Paquet absent, ou non exploitable."""


class PackageUnavailableError(AromeError):
    """Le dépôt répond 404 : paquet pas encore publié, ou déjà retiré.

    Distinguée pour permettre le repli sur un run précédent — les autres
    échecs (paquet corrompu, champs absents) ne se contournent pas en
    changeant de run et doivent rester des erreurs franches.
    """


@dataclass(frozen=True)
class PackageRef:
    """Désigne un fichier du dépôt."""

    run: datetime
    span: str
    package: str = SURFACE_PACKAGE
    resolution: str = RESOLUTION

    @property
    def run_key(self) -> str:
        """Horodatage du run tel qu'il apparaît dans les chemins."""
        return self.run.strftime("%Y-%m-%dT%H:00:00Z")

    @property
    def filename(self) -> str:
        return f"arome__{self.resolution}__{self.package}__{self.span}__{self.run_key}.grib2"

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.run_key}/arome/{self.resolution}/{self.package}/{self.filename}"


def latest_run(now: datetime, publication_delay_hours: float = 3.5) -> datetime:
    """Dernier run vraisemblablement publié à l'instant donné.

    Un run n'est pas disponible à son heure nominale : Météo-France l'intègre
    puis le diffuse par tranches, et le délai constaté approche trois heures et
    demie. Demander le run de l'heure courante retournerait donc un 404 la
    plupart du temps — le retrait est appliqué avant l'arrondi, pas après.
    """
    reference = now.astimezone(UTC) - timedelta(hours=publication_delay_hours)
    hour = max(h for h in RUN_HOURS if h <= reference.hour)
    return reference.replace(hour=hour, minute=0, second=0, microsecond=0)


def span_for_lead_time(lead_hours: int) -> str:
    """Tranche contenant l'échéance demandée.

    Les tranches sont nommées par leurs bornes incluses, la première couvrant
    de zéro à six heures et les suivantes six heures chacune à partir de sept.
    """
    if lead_hours < 0:
        raise AromeError(f"Échéance négative : {lead_hours}")
    if lead_hours <= 6:
        return SPANS[0]

    index = (lead_hours - 7) // 6 + 1
    if index >= len(SPANS):
        raise AromeError(f"Échéance hors de portée du modèle : {lead_hours} h")
    return SPANS[index]


def noon_lead_time(run: datetime, target_day: datetime, noon_hour_utc: int = 11) -> int:
    """Échéance, en heures, atteignant la mi-journée du jour visé.

    L'indice forêt météo se calcule sur les conditions de milieu de journée.
    Onze heures UTC vaut treize heures légales en été métropolitain, ce qui
    approche l'heure solaire retenue par la définition canadienne.
    """
    target = target_day.astimezone(UTC).replace(
        hour=noon_hour_utc, minute=0, second=0, microsecond=0
    )
    lead = round((target - run.astimezone(UTC)).total_seconds() / 3600)
    if lead < 0:
        raise AromeError("La mi-journée visée précède le run.")
    return lead


def runs_reaching_noon(noon: datetime, *, latest: datetime, limit: int = 4) -> tuple[datetime, ...]:
    """Runs candidats pour atteindre une mi-journée, du plus frais au plus vieux.

    Leçon des 8 et 9 août 2026 : le run le plus récent n'est pas toujours
    publié quand on le demande — le délai de diffusion approche trois heures
    et demie et fluctue, si bien qu'un déclenchement ponctuel tombe des deux
    côtés de la limite selon l'humeur du planificateur. Or la même mi-journée
    reste prévue par les runs précédents, à échéance croissante : plutôt que
    d'échouer sur un 404, on recule de run en run.

    La liste s'arrête quand l'échéance sort de la portée du modèle (48 h) ou
    que `limit` candidats ont été produits. Elle peut être vide : une
    mi-journée trop ancienne n'est plus atteignable par aucun run publiable.
    """
    if limit < 1:
        raise AromeError(f"Limite de candidats invalide : {limit}")

    moment = noon.astimezone(UTC)
    # Dernier run de la grille qui précède ou égale la mi-journée : un run
    # postérieur ne la prévoit plus, il l'a vécue.
    hour = max(h for h in RUN_HOURS if h <= moment.hour)
    candidate = min(
        moment.replace(hour=hour, minute=0, second=0, microsecond=0),
        latest.astimezone(UTC),
    )

    runs: list[datetime] = []
    while len(runs) < limit:
        lead = round((moment - candidate).total_seconds() / 3600)
        if lead > 48:
            break
        runs.append(candidate)
        candidate -= timedelta(hours=3)
    return tuple(runs)


def next_reachable_noon(run: datetime, noon_hour_utc: int = 11) -> datetime:
    """Prochaine mi-journée que ce run peut encore atteindre.

    Un run de quinze heures ne prévoit plus la mi-journée du jour même : elle
    est passée. Viser le jour courant sans le vérifier fait échouer toute
    exécution d'après-midi — c'est-à-dire la moitié des créneaux — sur une
    donnée qui ne se rattrape pas le lendemain.
    """
    moment = run.astimezone(UTC)
    noon = moment.replace(hour=noon_hour_utc, minute=0, second=0, microsecond=0)
    if noon < moment:
        noon += timedelta(days=1)
    return noon


__all__ = [
    "ARCHIVE_EXTENT",
    "BASE_URL",
    "FWI_FIELDS",
    "RESOLUTION",
    "RUN_HOURS",
    "SPANS",
    "SURFACE_PACKAGE",
    "AromeError",
    "PackageRef",
    "PackageUnavailableError",
    "latest_run",
    "next_reachable_noon",
    "noon_lead_time",
    "runs_reaching_noon",
    "span_for_lead_time",
]
