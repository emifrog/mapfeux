"""Vérifie ce que le rôle d'ingestion peut, et surtout ce qu'il ne peut pas.

Usage :
    micromamba run -n mapfeux-geo python scripts/verify-ingestion-role.py

Référence : cahier §25.2, migration `20260728160000_ingestion_role.sql`.

La chaîne de connexion de l'ordonnanceur vit chez un tiers. Ce qu'elle donne à
qui la lirait n'est pas une question qu'on tranche une fois : un `grant` ajouté
pour dépanner, une table créée sans y penser, et le périmètre s'élargit sans que
personne le remarque. Ce contrôle est donc rejouable.

Trois familles de sondes :

- **lectures** — doivent retourner des lignes. Vérifier l'absence d'erreur ne
  suffirait pas : sans contournement de RLS, `select count(*)` retourne zéro
  sans rien signaler, et un rôle aveugle passerait pour valide ;
- **écritures** — doivent porter sur des lignes réelles, pour la même raison :
  RLS n'évalue sa clause qu'en présence de lignes ;
- **interdits** — doivent être refusés.

Tout se passe dans une transaction annulée. Si le rôle n'existe pas encore, la
migration est appliquée le temps du contrôle : la sonde répond donc avant même
que la migration soit poussée.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import psycopg
from psycopg import sql

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
MIGRATION = ROOT / "supabase" / "migrations" / "20260728160000_ingestion_role.sql"
ROLE = "mapfeux_ingest"

READS = [
    ("registre des sources", "select count(*) from ingest.data_sources"),
    ("détections", "select count(*) from fire.detections"),
    ("événements", "select count(*) from fire.events"),
    ("rattachements", "select count(*) from fire.event_detections"),
    ("communes", "select count(*) from geo.municipalities"),
    ("chronologie", "select count(*) from fire.event_timeline_entries"),
    ("exécutions d'import", "select count(*) from ingest.import_runs"),
]

WRITES = [
    (
        "insérer un événement",
        """
        insert into fire.events (
          first_detected_at, last_detected_at, representative_point, algorithm_version
        ) values (
          now(), now(),
          extensions.st_setsrid(extensions.st_makepoint(6.0, 43.0), 4326),
          'sonde'
        )
        """,
    ),
    (
        "modifier un événement",
        "update fire.events set updated_at = now() where algorithm_version = 'grouping-v1'",
    ),
    (
        "modifier une détection",
        "update fire.detections set known_source_id = known_source_id",
    ),
    (
        "ouvrir une exécution d'import",
        """
        insert into ingest.import_runs (source_id, job_name, status)
        select id, 'sonde', 'running' from ingest.data_sources limit 1
        """,
    ),
]

FUNCTIONS = [
    "fire.generate_public_id(text)",
    "fire.ensure_detection_partition(date)",
    "fire.recompute_event_aggregates(uuid)",
    "fire.refresh_event_snapshot(uuid)",
]

FORBIDDEN = [
    ("profils d'administration", "select count(*) from admin.profiles"),
    ("journal d'audit", "select count(*) from audit.entries"),
    ("messages officiels", "select count(*) from app.official_messages"),
    ("historique des événements", "select count(*) from fire.event_history"),
    (
        "effacer un événement",
        "delete from fire.events where algorithm_version = 'grouping-v1'",
    ),
    ("effacer une détection", "delete from fire.detections where is_public"),
    ("modifier le schéma", "create table fire.sonde_interdite (x int)"),
    ("lire les instantanés publics", "select count(*) from fire.event_snapshots"),
]


def probe(conn: psycopg.Connection[Any], query: str) -> tuple[bool, object]:
    """Exécute la requête sous le rôle d'ingestion, sans rien laisser derrière."""
    with conn.cursor() as cur:
        cur.execute("savepoint sonde")
        cur.execute(f"set local role {ROLE}")
        try:
            cur.execute(query)
            value: object = cur.fetchone()[0] if cur.description else cur.rowcount  # type: ignore[index]
            outcome = (True, value)
        except psycopg.Error as exc:
            outcome = (False, str(exc).splitlines()[0])
        cur.execute("rollback to savepoint sonde")
    return outcome


def prepare(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute("select count(*) from pg_roles where rolname = %s", (ROLE,))
        row = cur.fetchone()
        if row is not None and row[0] == 0:
            print(f"{ROLE} absent : migration appliquée le temps du contrôle.\n")
            cur.execute(MIGRATION.read_text(encoding="utf-8"))

        # Depuis PostgreSQL 16, CREATEROLE donne l'administration d'un rôle créé
        # mais pas le droit de l'endosser. Accordé ici seulement, et annulé avec
        # la transaction : la migration n'en a pas besoin.
        #
        # Le nom est résolu puis interpolé. `grant ... to current_user` fait
        # tomber le backend sur PostgreSQL 17.6, de façon reproductible.
        cur.execute("select current_user")
        current = cur.fetchone()
        if current is None:
            raise RuntimeError("Rôle courant introuvable.")
        cur.execute(
            sql.SQL("grant {} to {} with set true").format(
                sql.Identifier(ROLE), sql.Identifier(str(current[0]))
            )
        )


def main() -> int:
    failures = 0

    with psycopg.connect(dsn_from_env_file(ENV_FILE), connect_timeout=30) as conn:
        prepare(conn)

        print("LECTURES — doivent retourner des lignes")
        for label, query in READS:
            ok, value = probe(conn, query)
            passed = ok and isinstance(value, int) and value > 0
            failures += 0 if passed else 1
            print(f"  {'  ' if passed else '✗ '}{label:<30} {value}")

        print("\nÉCRITURES — doivent porter sur des lignes réelles")
        for label, query in WRITES:
            ok, value = probe(conn, query)
            passed = ok and isinstance(value, int) and value > 0
            failures += 0 if passed else 1
            print(f"  {'  ' if passed else '✗ '}{label:<30} {value} ligne(s)")

        print("\nFONCTIONS — doivent être exécutables")
        for signature in FUNCTIONS:
            ok, value = probe(
                conn,
                f"select has_function_privilege('{ROLE}', '{signature}', 'execute')",
            )
            passed = ok and value is True
            failures += 0 if passed else 1
            print(f"  {'  ' if passed else '✗ '}{signature:<44} {value}")

        print("\nINTERDITS — doivent être refusés")
        for label, query in FORBIDDEN:
            ok, _ = probe(conn, query)
            failures += 1 if ok else 0
            print(f"  {'✗ ' if ok else '  '}{label:<30} {'PASSÉ' if ok else 'refusé'}")

        conn.rollback()

    print("\ntransaction annulée : la base est inchangée.")
    if failures:
        print(f"ÉCHEC : {failures} contrôle(s) hors attendu.")
        return 1
    print("Le périmètre du rôle est conforme.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
