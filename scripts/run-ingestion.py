"""Chaîne d'ingestion complète : import, regroupement, snapshots.

Usage :
    micromamba run -n mapfeux-geo python scripts/run-ingestion.py
    micromamba run -n mapfeux-geo python scripts/run-ingestion.py --bbox 5.5,42.7,7.9,44.5

Référence : cahier §16.1 et §16.8.

Point d'entrée unique destiné à l'ordonnanceur. Les trois étapes s'enchaînent
dans le seul ordre qui a du sens : on ne regroupe pas avant d'avoir importé, et
on ne publie pas un état figé avant d'avoir regroupé.

Chaque étape est isolée. Une source indisponible n'empêche pas de regrouper les
détections déjà en base, et un regroupement en échec laisse les snapshots
précédents intacts plutôt que d'en publier de faux.

Seuls les événements touchés voient leur snapshot reconstruit : en reconstruire
la totalité à chaque passage coûterait le prix d'une saison pour la valeur de
dix minutes.

Une seule passe à la fois. Un ordonnanceur qui déclenche toutes les dix minutes
une chaîne qui en met parfois quinze superposerait deux exécutions ; le verrou
fait sortir la seconde sans erreur, ce qui est le comportement attendu d'une
tâche périodique.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import UTC, datetime

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, exclusive_run, read_env_file
from geo_worker.pipelines.clustering import (
    cluster_detections,
)
from geo_worker.pipelines.detections import (
    insert_detections,
    mark_known_thermal_sources,
)
from geo_worker.pipelines.import_run import ImportRunError, import_run
from geo_worker.providers.firms import (
    DEFAULT_PRODUCTS,
    FirmsClient,
    FirmsQuotaError,
    FirmsUnavailableError,
    deduplicate,
    most_recent_acquisition,
    parse_csv,
)
from geo_worker.providers.models import BoundingBox

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"

# France métropolitaine et Corse, avec tampon frontalier : un feu à quelques
# kilomètres de la frontière concerne les communes françaises voisines (§16.3).
FRANCE_WITH_BUFFER = BoundingBox(min_lon=-5.8, min_lat=41.0, max_lon=10.2, max_lat=51.5)


def parse_bbox(argv: list[str]) -> BoundingBox:
    if "--bbox" not in argv:
        return FRANCE_WITH_BUFFER
    index = argv.index("--bbox")
    if index + 1 >= len(argv):
        sys.exit("--bbox attend minLon,minLat,maxLon,maxLat.")
    parts = [float(p) for p in argv[index + 1].split(",")]
    if len(parts) != 4:
        sys.exit("--bbox attend quatre valeurs séparées par des virgules.")
    return BoundingBox(
        min_lon=parts[0], min_lat=parts[1], max_lon=parts[2], max_lat=parts[3]
    )


def step_import(
    conn: psycopg.Connection[object],
    client: httpx.Client,
    map_key: str,
    bbox: BoundingBox,
) -> tuple[int, int]:
    """Importe les détections récentes. Retourne (insérées, produits en échec)."""
    firms = FirmsClient(client, map_key)
    inserted_total = 0
    failures = 0

    for product in DEFAULT_PRODUCTS:
        try:
            with import_run(
                conn, source_key="firms", job_name=f"detections:{product}"
            ) as counters:
                body = firms.fetch_area(product=product, bbox=bbox, day_range=1)
                detections, rejections = parse_csv(body, product=product)
                unique = list(deduplicate(detections))

                counters.records_read = len(detections) + len(rejections)
                counters.records_rejected = len(rejections)

                result = insert_detections(
                    conn, detections=unique, source_key="firms", import_run_id=None
                )
                conn.commit()

                counters.records_inserted = result.inserted
                counters.metrics = {
                    "already_known": result.already_known,
                    "product": product,
                }
                counters.source_data_at = most_recent_acquisition(unique)
                inserted_total += result.inserted

        except FirmsQuotaError as exc:
            failures += 1
            delay = exc.retry_after_seconds
            print(
                f"  {product} : quota atteint"
                + (f", réessayer dans {delay} s" if delay else "")
            )
        except (FirmsUnavailableError, ImportRunError) as exc:
            failures += 1
            print(f"  {product} : {exc}")

    return inserted_total, failures


def main(argv: list[str]) -> int:
    bbox = parse_bbox(argv)
    env = read_env_file(ENV_FILE)

    map_key = env.get("FIRMS_MAP_KEY", "")
    if map_key == "":
        sys.exit(
            "FIRMS_MAP_KEY absente de services/geo-worker/.env.\n"
            "Clé gratuite : https://firms.modaps.eosdis.nasa.gov/api/map_key/"
        )

    started = datetime.now(UTC)
    print(f"emprise : {bbox.as_firms_area()}\n", flush=True)

    with (
        psycopg.connect(dsn_from_env_file(ENV_FILE), connect_timeout=30) as conn,
        exclusive_run(conn, "ingestion") as acquired,
    ):
        if not acquired:
            print("Une passe d'ingestion est déjà en cours. Rien à faire.")
            # Sortie normale : pour un ordonnanceur périodique, se recouvrir est
            # un fonctionnement attendu, pas une panne à signaler.
            return 0

        with httpx.Client() as client:
            inserted, failures = step_import(conn, client, map_key, bbox)
        print(
            f"import      : {inserted} détection(s), {failures} produit(s) en échec",
            flush=True,
        )

        if inserted > 0:
            classified = mark_known_thermal_sources(conn)
            conn.commit()
            if classified > 0:
                print(
                    f"              {classified} rattachée(s) à une source connue",
                    flush=True,
                )

        # Le regroupement tourne même sans nouvelle détection : un import
        # précédent a pu échouer après insertion, laissant des orphelines.
        result = cluster_detections(conn)
        conn.commit()
        print(
            f"regroupement: {result.created} événement(s) créé(s), "
            f"{result.attached} rattachement(s)",
            flush=True,
        )

        refreshed = 0
        with conn.cursor() as cur:
            for event_id in sorted(result.touched_events):
                cur.execute("select fire.refresh_event_snapshot(%s)", (event_id,))
                if cur.fetchone() is not None:
                    refreshed += 1
            conn.commit()
        print(f"snapshots   : {refreshed} reconstruit(s)", flush=True)

    duration = (datetime.now(UTC) - started).total_seconds()
    print(f"\nterminé en {duration:.0f} s.")

    # Un échec total de l'import doit remonter à l'ordonnanceur ; un échec
    # partiel ne doit pas, sous peine d'alerter à chaque passage nocturne où
    # MODIS ne rapporte rien.
    return 1 if failures == len(DEFAULT_PRODUCTS) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
