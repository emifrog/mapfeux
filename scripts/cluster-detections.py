"""Regroupe les détections thermiques en événements.

Usage :
    micromamba run -n mapfeux-geo python scripts/cluster-detections.py
    micromamba run -n mapfeux-geo python scripts/cluster-detections.py --reset
    micromamba run -n mapfeux-geo python scripts/cluster-detections.py --reset --calibration

Référence : cahier §17.2.

`--reset` détache et supprime les événements produits par l'algorithme, puis
recommence. C'est l'outil de calibration et le test du critère de sortie du
jalon : deux exécutions successives doivent donner le même résultat.

`--calibration` vise la base de calibration — `CALIBRATION_DATABASE_URL`, avec
le garde-fou qui refuse la production. Sans l'option, l'outil vise la base que
le site public lit : c'est l'usage de reprise manuelle, aux paramètres de
référence uniquement, et la cible est affichée avant d'agir. C'était le seul
outil de regroupement resté sans bascule.

Il refuse de toucher aux événements portant une correction manuelle, un statut
officiel ou un masquage : ceux-là sont des décisions humaines, que la machine
n'a pas à défaire (§17.7).
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import DsnError, calibration_dsn, dsn_from_env_file, dsn_target
from geo_worker.pipelines.clustering import (
    ClusteringParams,
    cluster_detections,
)

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"


def read_dsn(argv: list[str]) -> str:
    try:
        if "--calibration" in argv:
            return calibration_dsn(ENV_FILE)
        return dsn_from_env_file(ENV_FILE)
    except DsnError as exc:
        sys.exit(str(exc))


def reset(conn: psycopg.Connection[Any], version: str) -> int:
    """Supprime les événements issus de l'algorithme, et eux seuls."""
    with conn.cursor() as cur:
        cur.execute(
            """
            delete from fire.events e
            where e.algorithm_version = %(version)s
              and e.official_control_status is null
              and e.verification_status in ('satellite_detection', 'probable_event')
              and e.freshness_status <> 'hidden'
              and e.manual_state = '{}'::jsonb
            """,
            {"version": version},
        )
        deleted = cur.rowcount
    conn.commit()
    return deleted


def main(argv: list[str]) -> int:
    params = ClusteringParams()

    dsn = read_dsn(argv)
    host, port, database = dsn_target(dsn)
    kind = "calibration" if "--calibration" in argv else "PRODUCTION"
    print(f"cible : {host}:{port}/{database} ({kind})\n", flush=True)

    with psycopg.connect(dsn, connect_timeout=30) as conn:
        if "--reset" in argv:
            deleted = reset(conn, params.version)
            print(f"{deleted} événement(s) supprimé(s) avant recalcul.\n")

        # Outil de recalcul manuel : il doit vider la file, pas en prendre la
        # tête. Le plafond appartient au traitement périodique.
        result = cluster_detections(conn, params=params, limit=None)
        conn.commit()

        print(
            f"\n{result.created} événement(s) créé(s), "
            f"{result.attached} détection(s) rattachée(s) à un événement existant."
        )

        with conn.cursor() as cur:
            cur.execute("""
                select count(*) filter (where detection_count = 1),
                       count(*) filter (where detection_count between 2 and 5),
                       count(*) filter (where detection_count > 5),
                       count(*)
                from fire.events
            """)
            row = cur.fetchone()
            if row is not None:
                isoles, petits, gros, total = row
                print(
                    f"\n{total} événement(s) : {isoles} à une seule détection, "
                    f"{petits} de 2 à 5, {gros} de plus de 5."
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
