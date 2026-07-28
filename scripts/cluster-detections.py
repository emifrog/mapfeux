"""Regroupe les détections thermiques en événements.

Usage :
    micromamba run -n mapfeux-geo python scripts/cluster-detections.py
    micromamba run -n mapfeux-geo python scripts/cluster-detections.py --reset

Référence : cahier §17.2.

`--reset` détache et supprime les événements produits par l'algorithme, puis
recommence. C'est l'outil de calibration et le test du critère de sortie du
jalon : deux exécutions successives doivent donner le même résultat.

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

from geo_worker.db import dsn_from_env_file
from geo_worker.pipelines.clustering import (
    ClusteringParams,
    cluster_detections,
)

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"


def read_dsn() -> str:
    return dsn_from_env_file(ENV_FILE)


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

    with psycopg.connect(read_dsn(), connect_timeout=30) as conn:
        if "--reset" in argv:
            deleted = reset(conn, params.version)
            print(f"{deleted} événement(s) supprimé(s) avant recalcul.\n")

        result = cluster_detections(conn, params=params)
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
