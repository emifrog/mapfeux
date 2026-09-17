"""Veille exterieure : les passes d'ingestion arrivent-elles encore ?

Plan §15, audit du 15 septembre 2026, constat 2 : le poste Windows qui porte
le declencheur n'a tourne qu'un tiers du temps, et rien ne le signalait — un
site qui repond sert des observations vieillissantes sans que personne ne le
sache, sauf a lire /statut. La cadence se mesure depuis la base
(`mesure-cadence.py`) ; l'alerte, elle, doit venir de l'exterieur, d'une
machine qui n'est pas celle qui peut s'endormir.

GitHub Actions est cet exterieur : un runner lit l'etat public du site toutes
les heures et **echoue** quand une source automatique en service est « trop
ancienne » — l'age au-dela duquel la chaine ne peut plus rien promettre, celui
que le registre declare (`stale_after`) — ou n'a jamais rien livre, ou quand le
site lui-meme ne repond pas. Un workflow planifie qui echoue, c'est un courriel
de GitHub : aucun service de plus, aucun secret, la meme information que
/statut, lue par quelqu'un qui n'est pas endormi.

« En retard » n'alerte pas : c'est l'echeance attendue qui a glisse, pas la
chaine qui a manque — la borne suivante tranche. Les sources lues a la main,
a venir ou en maintenance ne sont pas veillees : elles n'ont pas de passe a
manquer.

Sans dependance hors bibliotheque standard : le runner n'a que Python.

Usage :
    python scripts/veille-passes.py --site https://mapfeux.vercel.app
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

# « Trop ancienne » et « jamais livre » : la chaine a manque, on alerte.
ALERTE = frozenset({"stale", "unavailable"})
# « En retard » : signale dans le compte rendu, sans echec — l'echeance
# suivante dit si c'est une passe manquee.
SIGNALE = frozenset({"delayed"})
# Rien a attendre de ces sources : pas de passe, donc pas d'absence.
HORS_VEILLE = frozenset({"manual", "upcoming", "maintenance"})

LIBELLES = {
    "fresh": "a jour",
    "delayed": "en retard",
    "stale": "trop ancienne",
    "unavailable": "jamais livree",
    "manual": "import manuel",
    "upcoming": "a venir",
    "maintenance": "maintenance",
}


@dataclass(frozen=True)
class Ligne:
    """Une source telle que le site la decrit, avec l'age de sa derniere donnee."""

    key: str
    status: str
    age: str


@dataclass(frozen=True)
class Verdict:
    alertes: tuple[str, ...]
    signalements: tuple[str, ...]
    lignes: tuple[Ligne, ...]

    @property
    def echoue(self) -> bool:
        return len(self.alertes) > 0


def age_lisible(data_at: str | None, now: datetime) -> str:
    """« il y a 4 h 37 min », ou un tiret quand la source n'a jamais date sa donnee."""
    if data_at is None:
        return "—"
    try:
        instant = datetime.fromisoformat(data_at.replace("Z", "+00:00"))
    except ValueError:
        return "date illisible"
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    minutes = max(0, int((now - instant).total_seconds() // 60))
    if minutes < 60:
        return f"il y a {minutes} min"
    heures, reste = divmod(minutes, 60)
    if heures < 48:
        return f"il y a {heures} h {reste:02d} min"
    return f"il y a {heures // 24} j {heures % 24} h"


def evaluer(sources: dict[str, Any], now: datetime) -> Verdict:
    """Classe chaque source du registre : alerte, signalement, ou rien."""
    alertes: list[str] = []
    signalements: list[str] = []
    lignes: list[Ligne] = []
    for key in sorted(sources):
        entree = sources[key]
        status = str(entree.get("status", "inconnu"))
        data_at = entree.get("dataAt")
        lignes.append(Ligne(key, status, age_lisible(data_at, now)))
        if status in HORS_VEILLE:
            continue
        if status in ALERTE:
            alertes.append(key)
        elif status in SIGNALE:
            signalements.append(key)
        elif status != "fresh":
            # Un etat que ce script ne connait pas n'est pas « a jour ».
            alertes.append(key)
    return Verdict(tuple(alertes), tuple(signalements), tuple(lignes))


def lire_etat(site: str, timeout: float) -> dict[str, Any]:
    """L'enveloppe de GET /api/v1/status, telle que le site la sert."""
    url = f"{site.rstrip('/')}/api/v1/status"
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"site sans schema http(s) : {site}")
    # S310 : le schema est verifie juste au-dessus — http(s) seulement.
    requete = urllib.request.Request(url, headers={"User-Agent": "mapfeux-veille/1"})  # noqa: S310
    reponse = urllib.request.urlopen(requete, timeout=timeout)  # noqa: S310
    with reponse:
        charge = json.loads(reponse.read().decode("utf-8"))
    if not isinstance(charge, dict):
        raise ValueError("reponse inattendue : pas un objet JSON")
    return charge


def compte_rendu(verdict: Verdict, site: str, now: datetime, statut_global: str) -> str:
    """Le tableau Markdown du resume de tache — et de la sortie standard."""
    lignes = [
        f"## Veille des passes — {now.strftime('%Y-%m-%d %H:%M')} UTC",
        "",
        f"Site : {site} — etat global annonce : **{statut_global}**",
        "",
        "| Source | Etat | Derniere donnee |",
        "|---|---|---|",
    ]
    for ligne in verdict.lignes:
        libelle = LIBELLES.get(ligne.status, ligne.status)
        if ligne.key in verdict.alertes:
            marque = "🔴 "
        elif ligne.key in verdict.signalements:
            marque = "🟠 "
        else:
            marque = ""
        lignes.append(f"| `{ligne.key}` | {marque}{libelle} | {ligne.age} |")
    lignes.append("")
    if verdict.echoue:
        lignes.append(
            "**Alerte** : "
            + ", ".join(f"`{k}`" for k in verdict.alertes)
            + " — la chaine d'ingestion a manque au-dela de ce que le registre promet."
        )
    elif verdict.signalements:
        lignes.append(
            "En retard, sans alerte : "
            + ", ".join(f"`{k}`" for k in verdict.signalements)
            + " — l'echeance suivante tranchera."
        )
    else:
        lignes.append("Toutes les sources veillees sont a jour.")
    return "\n".join(lignes)


def ecrire_resume(texte: str) -> None:
    """Dans le resume de tache GitHub quand il existe, sur la sortie standard toujours."""
    print(texte)
    chemin = os.environ.get("GITHUB_STEP_SUMMARY")
    if chemin:
        with open(chemin, "a", encoding="utf-8") as fichier:
            fichier.write(texte + "\n")


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parseur.add_argument("--site", default="https://mapfeux.vercel.app")
    parseur.add_argument("--timeout", type=float, default=30.0, help="secondes")
    args = parseur.parse_args(argv)
    now = datetime.now(UTC)

    try:
        charge = lire_etat(args.site, args.timeout)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as erreur:
        ecrire_resume(
            f"## Veille des passes — {now.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
            f"**Alerte** : le site {args.site} ne repond pas ({erreur}). "
            "Ni les passes ni leur absence ne peuvent etre constatees."
        )
        return 1

    statut_global = str(charge.get("data", {}).get("status", "inconnu"))
    sources = charge.get("meta", {}).get("sources", {})
    verdict = evaluer(sources if isinstance(sources, dict) else {}, now)
    if statut_global == "unknown" or not verdict.lignes:
        # Le site n'a pas pu lire son propre registre : on ne sait rien, et ne
        # rien savoir n'est pas aller bien.
        verdict = Verdict(("registre illisible",), verdict.signalements, verdict.lignes)
    ecrire_resume(compte_rendu(verdict, args.site, now, statut_global))
    return 1 if verdict.echoue else 0


if __name__ == "__main__":
    sys.exit(main())
