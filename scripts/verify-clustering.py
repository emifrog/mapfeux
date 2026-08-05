"""Vérifie que le regroupement est reproductible.

Usage :
    micromamba run -n mapfeux-geo python scripts/verify-clustering.py
    micromamba run -n mapfeux-geo python scripts/verify-clustering.py --recompute
    micromamba run -n mapfeux-geo python scripts/verify-clustering.py --recompute --calibration

Référence : cahier §17.2, critère de sortie du jalon J2.

Sans argument, le script se contente d'imprimer l'empreinte de l'état courant.
`--recompute` fait le contrôle réel : empreinte, effacement des événements
algorithmiques, recalcul complet, seconde empreinte, comparaison.

L'empreinte porte sur le **partitionnement**, pas sur les identifiants. Un
recalcul recrée les événements avec de nouveaux UUID et de nouveaux
`public_id` ; comparer ceux-là ne dirait rien. Ce qui doit être stable, c'est
l'affectation : quelles détections se retrouvent ensemble. Chaque événement est
donc réduit à la liste triée des clés naturelles de ses membres, et les
événements sont eux-mêmes triés entre eux avant hachage.

Un résultat non reproductible n'est pas un défaut mineur : il rend l'algorithme
inexplicable, ce qui est une condition d'arrêt du projet.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys
import time
from typing import Any

import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import calibration_dsn, dsn_from_env_file, dsn_target
from geo_worker.pipelines.clustering import (
    ClusteringParams,
    cluster_detections,
    pending_detection_count,
)

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"


def signature(conn: psycopg.Connection[Any]) -> tuple[str, int, int]:
    """Empreinte du partitionnement, nombre d'événements, nombre de membres."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select ed.event_id, d.provider_key, d.acquired_at
            from fire.event_detections ed
            join fire.detections d
              on d.id = ed.detection_id
             and d.acquired_at = ed.detection_acquired_at
            """
        )
        rows = cur.fetchall()

    groups: dict[object, list[str]] = {}
    for event_id, provider_key, acquired_at in rows:
        groups.setdefault(event_id, []).append(f"{provider_key}@{acquired_at.isoformat()}")

    # Chaque groupe est trié en interne, puis les groupes sont triés entre eux
    # par leur contenu : l'empreinte ne dépend ni de l'ordre de lecture, ni des
    # identifiants attribués.
    canonical = sorted("|".join(sorted(members)) for members in groups.values())
    digest = hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest()[:16]
    return digest, len(groups), len(rows)


def reset(conn: psycopg.Connection[Any], version: str) -> int:
    """Supprime les seuls événements produits par l'algorithme (§17.7)."""
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


def replay(
    conn: psycopg.Connection[Any], params: ClusteringParams, chunk: int | None
) -> tuple[int, int, float]:
    """Rejoue le regroupement, en une passe ou par tranches.

    Le découpage n'est pas un détail d'exécution : en production le regroupement
    tourne toutes les dix minutes sur les quelques détections qui viennent
    d'arriver, alors que la calibration le rejoue sur une saison entière. Si les
    deux ne donnaient pas le même résultat, la carte servie au public ne serait
    pas celle qu'on a calibrée.
    """
    started = time.monotonic()
    created = 0
    attached = 0

    while True:
        # `chunk` à None demande la passe en bloc : le plafond est levé, sans
        # quoi « en bloc » ne voudrait dire « tout le corpus » que tant que le
        # corpus tient sous le plafond par défaut.
        result = cluster_detections(conn, params=params, limit=chunk)
        conn.commit()
        created += result.created
        attached += result.attached
        if chunk is None or result.processed == 0:
            break

    # Le contrôle compare deux empreintes du partitionnement. Si le rejeu a
    # laissé des orphelines, il compare deux partitionnements partiels et peut
    # les déclarer égaux : le contrôle passerait sans rien avoir contrôlé.
    remaining = pending_detection_count(conn)
    if remaining > 0:
        raise SystemExit(
            f"{remaining} détection(s) publiable(s) sans événement après le rejeu. "
            "L'empreinte ne porterait pas sur tout le corpus."
        )

    return created, attached, time.monotonic() - started


def parse_chunk(argv: list[str]) -> int | None:
    if "--incremental" not in argv:
        return None
    index = argv.index("--incremental")
    if index + 1 < len(argv) and not argv[index + 1].startswith("-"):
        return int(argv[index + 1])
    return 250


def main(argv: list[str]) -> int:
    params = ClusteringParams()
    chunk = parse_chunk(argv)

    # Par défaut la base de production : ce contrôle rejoue les **paramètres de
    # référence** et restaure l'état qu'il a trouvé, contrairement au banc et à
    # l'inspection qui font tourner des jeux qu'on ne publie pas. Le vérifier là
    # où le site lit est précisément ce qui a du sens.
    #
    # `--calibration` le porte sur le corpus, où le rejeu est bien plus long et
    # où l'égalité entre passe en bloc et passe par tranches se joue sur des
    # volumes qui la mettent réellement à l'épreuve.
    sur_calibration = "--calibration" in argv
    dsn = calibration_dsn(ENV_FILE) if sur_calibration else dsn_from_env_file(ENV_FILE)
    host, port, database = dsn_target(dsn)
    print(f"base    : {host}:{port}/{database}" + ("  (calibration)" if sur_calibration else ""))

    with psycopg.connect(dsn, connect_timeout=30) as conn:
        before, events_before, members_before = signature(conn)
        print(f"avant   : {before}  {events_before} événement(s), {members_before} membre(s)")

        if "--recompute" not in argv and chunk is None:
            print("\n--recompute pour rejouer le regroupement et comparer.")
            print("--incremental [N] pour le rejouer par tranches de N détections.")
            return 0

        deleted = reset(conn, params.version)
        print(f"effacé  : {deleted} événement(s)")
        if chunk is not None:
            print(f"mode    : par tranches de {chunk} détection(s)")
        print()

        created, attached, elapsed = replay(conn, params, chunk)

        after, events_after, members_after = signature(conn)
        print(f"\naprès   : {after}  {events_after} événement(s), {members_after} membre(s)")
        print(f"recalcul: {created} créé(s), {attached} rattaché(s), {elapsed:.1f} s")

        if before != after:
            print(
                "\nÉCHEC : le partitionnement a changé. L'algorithme n'est pas "
                "reproductible, donc pas explicable."
            )
            return 1

        print("\nreproductible : empreinte identique.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
