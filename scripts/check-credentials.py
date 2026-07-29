"""Contrôle les identifiants de l'ingestion sans jamais les afficher.

Usage :
    micromamba run -n mapfeux-geo python scripts/check-credentials.py

Référence : cahier §25.2, README « Ingestion planifiée ».

À faire **avant** de brancher un ordonnanceur. Une tâche planifiée qui échoue
sur un identifiant invalide échoue en silence toutes les dix minutes : personne
ne regarde un onglet Actions, et le site continue d'afficher un âge de donnée
qui grandit sans que rien ne le signale.

Deux identifiants, deux contrôles :

- `FIRMS_MAP_KEY` — interrogé sur le point d'état de la NASA, qui retourne aussi
  le quota consommé. Une clé invalide se reconnaît à la réponse, pas au code
  HTTP : FIRMS répond 200 avec un corps en texte brut, ce qui ferait passer une
  clé morte pour une clé valide.
- `INGESTION_DATABASE_URL`, à défaut `DATABASE_URL` — connexion réelle, puis
  relevé du rôle, de son attribut de contournement RLS et du mode de connexion.
  Le mode compte : derrière un pooler en mode transaction, le verrou
  d'exécution serait pris sur une connexion et le travail fait sur une autre.

**Aucune valeur n'est imprimée**, ni en cas de succès ni en cas d'échec. Un
fragment de mot de passe apparu dans une trace d'erreur, c'est un mot de passe à
changer.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any
from urllib.parse import urlsplit

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import load_env, normalise_dsn

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
STATUS_URL = "https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/"


def check_firms(map_key: str) -> bool:
    if map_key.strip() == "":
        print("  ✗ FIRMS_MAP_KEY absente")
        return False

    try:
        response = httpx.get(STATUS_URL, params={"MAP_KEY": map_key}, timeout=30)
    except httpx.HTTPError as exc:
        print(f"  ✗ point d'état injoignable : {type(exc).__name__}")
        return False

    if response.status_code != 200:
        print(f"  ✗ point d'état : HTTP {response.status_code}")
        return False

    try:
        payload = response.json()
    except ValueError:
        # FIRMS répond 200 avec du texte brut quand la clé est refusée.
        print("  ✗ clé refusée (réponse non JSON)")
        return False

    if "current_transactions" not in payload:
        print(f"  ✗ réponse inattendue : {sorted(payload)[:4]}")
        return False

    used = payload["current_transactions"]
    limit = payload.get("transaction_limit", "?")
    print(f"  ✓ clé valide — {used}/{limit} requêtes sur la fenêtre courante")
    return True


def describe_target(dsn: str) -> str:
    """Hôte et port, sans identifiants."""
    parts = urlsplit(dsn)
    return f"{parts.hostname}:{parts.port or 5432}"


def check_database(dsn: str, label: str) -> bool:
    target = describe_target(dsn)
    print(f"  cible : {target}")

    try:
        conn = psycopg.connect(dsn, connect_timeout=30)
    except psycopg.Error as exc:
        # Le message de psycopg peut contenir la chaîne complète.
        print(f"  ✗ connexion refusée ({type(exc).__name__})")
        print(f"    vérifier {label} — aucune valeur n'est affichée ici")
        return False

    ok = True
    with conn, conn.cursor() as cur:
        cur.execute(
            "select current_user, (select rolbypassrls from pg_roles where rolname = current_user)"
        )
        row = cur.fetchone()
        if row is None:
            print("  ✗ la base n'a pas répondu")
            return False
        role, bypass = str(row[0]), bool(row[1])
        print(f"  ✓ connecté en tant que {role}")

        if not bypass:
            print("  ✗ ce rôle ne contourne pas RLS : il ne verrait aucune ligne")
            ok = False

        # Un verrou de session doit survivre à une validation. Derrière un
        # pooler en mode transaction, ce n'est pas garanti.
        cur.execute("select pg_try_advisory_lock(%s)", (424242,))
        taken = cur.fetchone()
        held_before = bool(taken[0]) if taken else False
        conn.commit()
        cur.execute(
            "select count(*) from pg_locks where locktype = 'advisory' and pid = pg_backend_pid()"
        )
        after = cur.fetchone()
        held_after = bool(after[0]) if after else False
        cur.execute("select pg_advisory_unlock(%s)", (424242,))
        conn.commit()

        if held_before and held_after:
            print("  ✓ verrou de session conservé après validation")
        else:
            print("  ✗ verrou de session perdu — pooler en mode transaction ?")
            print("    prendre le pooler en mode session, port 5432")
            ok = False

        cur.execute("select count(*) from fire.detections")
        seen = cur.fetchone()
        count = int(seen[0]) if seen else 0
        if count > 0:
            print(f"  ✓ {count} détection(s) lisibles")
        else:
            print("  ✗ aucune détection lisible — droits ou RLS")
            ok = False

    return ok


def main() -> int:
    env: dict[str, Any] = load_env(ENV_FILE)
    failures = 0

    print("FIRMS_MAP_KEY")
    if not check_firms(str(env.get("FIRMS_MAP_KEY", ""))):
        failures += 1

    # `INGESTION_DATABASE_URL` est le nom du secret côté ordonnanceur. La poser
    # localement permet d'éprouver exactement ce que la tâche planifiée
    # utilisera, sans attendre son premier déclenchement.
    label = "INGESTION_DATABASE_URL"
    raw = str(env.get(label, ""))
    if raw == "":
        label = "DATABASE_URL"
        raw = str(env.get(label, ""))

    print(f"\n{label}")
    if raw == "":
        print("  ✗ absente du fichier et de l'environnement")
        failures += 1
    elif not check_database(normalise_dsn(raw), label):
        failures += 1

    if label == "DATABASE_URL":
        print(
            "\nNote : INGESTION_DATABASE_URL n'est pas définie, le contrôle a porté\n"
            "sur la connexion de développement. Pour éprouver ce que la tâche\n"
            "planifiée utilisera, ajouter la chaîne du pooler en mode session sous\n"
            "ce nom dans services/geo-worker/.env, qui n'est jamais versionné."
        )

    print("\nÉCHEC" if failures else "\nLes identifiants sont exploitables.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
