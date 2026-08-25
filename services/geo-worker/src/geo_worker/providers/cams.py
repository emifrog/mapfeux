"""Prévisions de qualité de l'air CAMS Europe, via l'Atmosphere Data Store.

Référence : cahier v2.1 §16.5 et §13.17 ; plan J9.

## Accès

Le jeu est `cams-europe-air-quality-forecasts` — celui que le registre des
sources pointe depuis l'origine. L'ADS de Copernicus exige un **jeton
personnel** (gratuit) et l'acceptation de la licence du jeu sur sa page :
sans l'un ou l'autre, l'API répond 401 ou 403. Les variables sont
`COPERNICUS_URL` et `COPERNICUS_KEY`, déclarées dans `.env.example` depuis
le premier jour.

## Ce qu'on demande

Le minimum de FR-120 : PM2,5 et PM10, modèle `ensemble` (la médiane des
onze modèles régionaux — le produit de référence, pas un membre), niveau
sol, sur l'emprise nationale. Un run par jour à 00 UTC, publié en cours de
matinée ; les échéances horaires couvrent jusqu'à 96 h, on n'importe que ce
que l'affichage servira.

## Protocole

L'ADS parle l'API Processes (OGC) : soumission d'une exécution, jobUrl,
attente, puis téléchargement de l'unique fichier produit. Une requête par
polluant : un fichier NetCDF chacun, nommable et vérifiable séparément.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from geo_worker.providers.models import BoundingBox

DATASET = "cams-europe-air-quality-forecasts"
MODEL = "ensemble"
UNIT = "µg/m³"

#: Résolution nominale du produit régional européen.
RESOLUTION = "0.1°"

#: Nom CAMS de chaque polluant servi (FR-120). Une AASQA future passera par
#: un adaptateur distinct (FR-122), jamais par une entrée glissée ici.
POLLUTANTS: dict[str, str] = {
    "pm2_5": "particulate_matter_2.5um",
    "pm10": "particulate_matter_10um",
}

#: Même emprise nationale que l'archivage AROME : réduire plus tard reste
#: possible, élargir rétroactivement non.
EXTENT = BoundingBox(min_lon=-5.8, min_lat=41.0, max_lon=10.2, max_lat=51.5)


class CamsError(RuntimeError):
    """Réponse inexploitable de l'ADS."""


class CamsAuthError(CamsError):
    """Jeton absent, invalide, ou licence du jeu non acceptée."""


@dataclass(frozen=True)
class CamsRequest:
    """Une demande d'extraction : un polluant, un run, des échéances."""

    pollutant: str
    run_at: datetime
    lead_hours: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.pollutant not in POLLUTANTS:
            raise CamsError(f"Polluant inconnu : {self.pollutant!r}")
        if not self.lead_hours:
            raise CamsError("Aucune échéance demandée.")
        if any(lead < 0 or lead > 96 for lead in self.lead_hours):
            raise CamsError("Échéance hors de portée du produit (0-96 h).")
        moment = self.run_at.astimezone(UTC)
        if (moment.hour, moment.minute) != (0, 0):
            raise CamsError("Le produit européen n'a qu'un run quotidien, à 00 UTC.")

    def payload(self) -> dict[str, Any]:
        """Corps de la soumission, dans le dialecte du jeu.

        `area` est [nord, ouest, sud, est] — l'ordre ADS, pas le nôtre.
        """
        day = self.run_at.astimezone(UTC).strftime("%Y-%m-%d")
        return {
            "variable": [POLLUTANTS[self.pollutant]],
            "model": [MODEL],
            "level": ["0"],
            "date": [f"{day}/{day}"],
            "type": ["forecast"],
            "time": ["00:00"],
            "leadtime_hour": [str(lead) for lead in self.lead_hours],
            "data_format": "netcdf_zip",
            "area": [EXTENT.max_lat, EXTENT.min_lon, EXTENT.min_lat, EXTENT.max_lon],
        }

    @property
    def object_path(self) -> str:
        """Chemin de dépôt du brut, daté et lisible."""
        moment = self.run_at.astimezone(UTC)
        first, last = min(self.lead_hours), max(self.lead_hours)
        return (
            f"cams/{moment.strftime('%Y/%m/%d')}/"
            f"cams-europe__{MODEL}__{self.pollutant}__"
            f"{moment.strftime('%Y-%m-%dT000000Z')}__H{first}-H{last}.nc"
        )


def _headers(token: str) -> dict[str, str]:
    # Le jeton se présente en `PRIVATE-TOKEN` sur l'API actuelle ;
    # `Authorization` reste envoyé pour les déploiements qui liraient
    # l'ancien schéma — même prudence que pour Supabase Storage.
    return {"PRIVATE-TOKEN": token, "Authorization": f"Bearer {token}"}


def retrieve(
    http: httpx.Client,
    *,
    base_url: str,
    token: str,
    request: CamsRequest,
    poll_seconds: float = 5.0,
    timeout_seconds: float = 900.0,
) -> bytes:
    """Soumet la demande, attend le résultat, retourne les octets du fichier.

    L'ADS est une file de traitement, pas un serveur de fichiers : la
    latence normale se compte en dizaines de secondes et grimpe aux heures
    de pointe — d'où l'attente bornée mais patiente.
    """
    submit = http.post(
        f"{base_url.rstrip('/')}/retrieve/v1/processes/{DATASET}/execution",
        json={"inputs": request.payload()},
        headers=_headers(token),
        timeout=120,
    )
    if submit.status_code in (401, 403):
        raise CamsAuthError(
            f"ADS {submit.status_code} : jeton invalide ou licence du jeu non "
            f"acceptée — {submit.text[:200]}"
        )
    if submit.status_code not in (200, 201):
        raise CamsError(f"Soumission refusée ({submit.status_code}) : {submit.text[:200]}")

    job = submit.json()
    job_id = job.get("jobID")
    if job_id is None:
        raise CamsError(f"Réponse sans jobID : {str(job)[:200]}")

    deadline = time.monotonic() + timeout_seconds
    status = str(job.get("status", "accepted"))
    while status not in ("successful", "failed"):
        if time.monotonic() > deadline:
            raise CamsError(f"Job {job_id} sans issue après {timeout_seconds:.0f} s.")
        time.sleep(poll_seconds)
        poll = http.get(
            f"{base_url.rstrip('/')}/retrieve/v1/jobs/{job_id}",
            headers=_headers(token),
            timeout=60,
        )
        if poll.status_code != 200:
            raise CamsError(f"Suivi du job impossible ({poll.status_code}).")
        status = str(poll.json().get("status", status))

    if status == "failed":
        raise CamsError(f"Job {job_id} en échec côté ADS.")

    results = http.get(
        f"{base_url.rstrip('/')}/retrieve/v1/jobs/{job_id}/results",
        headers=_headers(token),
        timeout=60,
    )
    if results.status_code != 200:
        raise CamsError(f"Résultats illisibles ({results.status_code}).")
    body = results.json()
    asset = body.get("asset", {}).get("value", {})
    href = asset.get("href")
    if href is None:
        raise CamsError(f"Résultat sans lien de téléchargement : {str(body)[:200]}")

    download = http.get(href, headers=_headers(token), timeout=300, follow_redirects=True)
    if download.status_code != 200:
        raise CamsError(f"Téléchargement refusé ({download.status_code}).")
    return download.content


__all__ = [
    "DATASET",
    "EXTENT",
    "MODEL",
    "POLLUTANTS",
    "RESOLUTION",
    "UNIT",
    "CamsAuthError",
    "CamsError",
    "CamsRequest",
    "retrieve",
]
