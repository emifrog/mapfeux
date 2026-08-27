"""Réconcilie les détections NRT avec l'archive standard FIRMS (§16.3).

Usage :
    micromamba run -n mapfeux-geo python scripts/reconcile-firms.py
    micromamba run -n mapfeux-geo python scripts/reconcile-firms.py --plan

Référence : cahier v2.1 §16.3, FR-032 ; plan J10.

La passe lit la disponibilité FIRMS, croise les bornes standard avec ce que
la base contient par satellite, relit le standard sur les fenêtres qui se
recouvrent (API Area, cinq jours par requête) et enrichit les lignes
appariées — `thermal_type`, ligne standard complète, `reconciled_at`.
Jamais d'insertion, jamais de réécriture du brut : les non-appariées sont
comptées et rendues au journal. Rejouer une fenêtre déjà traitée ne change
rien : c'est le critère de sortie du jalon.

`--plan` : affiche ce que la passe ferait — fenêtres et exclusions — sans
rien lire ni écrire.

Variables : `FIRMS_MAP_KEY`, `DATABASE_URL`.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import UTC, datetime, time

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target, load_env
from geo_worker.pipelines.import_run import ImportRunError, import_run
from geo_worker.pipelines.reconciliation import (
    AVAILABILITY_PATH,
    parse_availability,
    plan_reconciliation,
    reconcile_standard,
)
from geo_worker.providers.firms import (
    FirmsClient,
    FirmsQuotaError,
    FirmsUnavailableError,
    looks_like_csv,
    parse_csv,
)
from geo_worker.providers.models import BoundingBox, ThermalDetection

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
SOURCE_KEY = "firms"

#: Même emprise que l'ingestion : France métropolitaine et Corse, avec
#: tampon frontalier (voir import-firms.py — la duplication est une dette
#: connue, les quatre nombres vivent dans trois scripts).
FRANCE_WITH_BUFFER = BoundingBox(min_lon=-5.8, min_lat=41.0, max_lon=10.2, max_lat=51.5)

FIRMS_BASE = "https://firms.modaps.eosdis.nasa.gov"


def main(argv: list[str]) -> int:
    env = load_env(ENV_FILE)
    map_key = env.get("FIRMS_MAP_KEY", "").strip()
    if map_key == "":
        sys.exit("FIRMS_MAP_KEY absente : la réconciliation lit l'API Area.")

    dsn = dsn_from_env_file(ENV_FILE)
    host, port, database = dsn_target(dsn)
    print(f"cible : {host}:{port}/{database}")

    with httpx.Client(timeout=120) as http:
        availability_url = f"{FIRMS_BASE}/{AVAILABILITY_PATH.format(map_key=map_key)}"
        availability = parse_availability(http.get(availability_url).text)

        with psycopg.connect(dsn, connect_timeout=30) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select satellite, min(acquired_at), max(acquired_at)
                    from fire.detections
                    group by satellite
                    """
                )
                base_ranges = {str(row[0]): (row[1], row[2]) for row in cur.fetchall()}

            plans, skipped = plan_reconciliation(availability, base_ranges)
            for reason in skipped:
                print(f"écarté : {reason}")
            if not plans:
                print("Aucune fenêtre réconciliable : le standard ne recouvre pas la base.")
                return 0
            for plan in plans:
                print(
                    f"plan   : {plan.product} ({', '.join(plan.satellites)}) "
                    f"{plan.start} → {plan.end}, {len(plan.windows)} fenêtre(s)"
                )
            if "--plan" in argv:
                print("--plan : rien lu, rien écrit.")
                return 0

            client = FirmsClient(http, map_key)
            try:
                with import_run(
                    conn, source_key=SOURCE_KEY, job_name="firms:reconciliation"
                ) as counters:
                    detections: list[ThermalDetection] = []
                    rejections: list[str] = []
                    for plan in plans:
                        before = len(detections)
                        for window_start, span in plan.windows:
                            body = client.fetch_area(
                                product=plan.product,
                                bbox=FRANCE_WITH_BUFFER,
                                day_range=span,
                                start_date=datetime.combine(window_start, time(), tzinfo=UTC),
                            )
                            if not looks_like_csv(body):
                                raise FirmsUnavailableError(
                                    f"Réponse non CSV pour {plan.product} au {window_start}."
                                )
                            parsed, rejected = parse_csv(body, product=plan.product)
                            detections.extend(parsed)
                            rejections.extend(rejected)
                        print(
                            f"{plan.product} : {len(detections) - before} ligne(s) standard "
                            f"en {len(plan.windows)} requête(s)"
                        )

                    result = reconcile_standard(conn, detections)
                    print(
                        f"appariées : {result.updated} enrichie(s), "
                        f"{result.already_reconciled} déjà réconciliée(s), "
                        f"{result.unmatched} sans correspondance en base"
                    )

                    counters.records_read = result.read
                    counters.records_updated = result.updated
                    counters.records_rejected = len(rejections)
                    if detections:
                        counters.source_data_at = max(item.acquired_at for item in detections)
                    counters.metrics = {
                        "produits": [plan.product for plan in plans],
                        "fenetres": sum(len(plan.windows) for plan in plans),
                        "ecartes": skipped,
                        "non_appariees": result.unmatched,
                        "deja_reconciliees": result.already_reconciled,
                    }
            except FirmsQuotaError as exc:
                print(f"quota FIRMS atteint : {exc} — la passe se rejouera.")
                return 1
            except (FirmsUnavailableError, ImportRunError) as exc:
                print(f"échec : {exc}")
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
