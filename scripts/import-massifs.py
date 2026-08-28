"""Capture les niveaux d'accès aux massifs (83 et 06), aujourd'hui et demain.

Usage :
    micromamba run -n mapfeux-geo python scripts/import-massifs.py

Référence : cahier v2.1 §9.2 et §20.4, FR-140 ; ADR-026 ; plan J4.

Pour chaque département : le référentiel des massifs et les libellés
officiels sont relus du site, puis le JSON quotidien d'aujourd'hui — et
celui de demain, publié vers 18 h, dont l'absence le matin n'est pas une
panne mais un fait dit. Chaque JSON brut est archivé avant analyse ; les
niveaux se rangent un par massif et par jour, libellé officiel verbatim.

Variables : `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import UTC, datetime, timedelta

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target, load_env
from geo_worker.pipelines.import_run import ImportRunError, import_run
from geo_worker.pipelines.massif_levels import assemble_levels, record_levels
from geo_worker.providers.massifs import (
    DEPARTMENT_PATHS,
    daily_levels_url,
    department_page_url,
    massif_names_url,
    parse_daily_levels,
    parse_level_labels,
    parse_massif_names,
    translation_url,
)
from geo_worker.storage import BUCKET_RAW, upload_object

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
SOURCE_KEY = "massifs"

USER_AGENT = "MapFeux/1.0 (+https://mapfeux.vercel.app)"


def main(argv: list[str]) -> int:
    env = load_env(ENV_FILE)
    supabase_url = env.get("SUPABASE_URL", "")
    secret_key = env.get("SUPABASE_SECRET_KEY", "")
    if supabase_url == "" or secret_key == "":
        sys.exit("SUPABASE_URL et SUPABASE_SECRET_KEY sont requises pour archiver le brut.")

    dsn = dsn_from_env_file(ENV_FILE)
    host, port, database = dsn_target(dsn)
    print(f"cible : {host}:{port}/{database}")

    now = datetime.now(UTC)
    days = [now.date(), (now + timedelta(days=1)).date()]

    with (
        psycopg.connect(dsn, connect_timeout=30) as conn,
        httpx.Client(timeout=60, follow_redirects=True, headers={"user-agent": USER_AGENT}) as http,
    ):
        try:
            with import_run(conn, source_key=SOURCE_KEY, job_name="massifs:niveaux") as counters:
                total_read = 0
                total_inserted = 0
                total_updated = 0
                rejections: list[str] = []
                pending: list[str] = []

                for department in sorted(DEPARTMENT_PATHS):
                    names_body = http.get(massif_names_url(department))
                    translation_body = http.get(translation_url(department))
                    if names_body.status_code != 200 or translation_body.status_code != 200:
                        rejections.append(
                            f"{department} : référentiel ou libellés injoignables "
                            f"({names_body.status_code}/{translation_body.status_code})"
                        )
                        continue
                    names = parse_massif_names(names_body.text)
                    labels = parse_level_labels(translation_body.text)

                    for day in days:
                        stamp = day.strftime("%Y%m%d")
                        response = http.get(daily_levels_url(department, stamp))
                        if response.status_code == 404:
                            # La prévision du lendemain paraît vers 18 h : son
                            # absence avant n'est pas une panne, c'est un fait.
                            pending.append(f"{department} {day} : pas encore publié")
                            continue
                        if response.status_code != 200:
                            rejections.append(f"{department} {day} : HTTP {response.status_code}")
                            continue

                        # Le brut d'abord, avant toute interprétation (§16.1).
                        checksum = upload_object(
                            http,
                            supabase_url=supabase_url,
                            secret_key=secret_key,
                            bucket=BUCKET_RAW,
                            object_path=f"massifs/{department}/{stamp}.json",
                            payload=response.content,
                            content_type="application/json",
                        )

                        levels = parse_daily_levels(response.text)
                        assembled, day_rejections = assemble_levels(
                            levels, names, labels, department_path=DEPARTMENT_PATHS[department]
                        )
                        rejections.extend(
                            f"{department} {day} : {reason}" for reason in day_rejections
                        )
                        inserted, updated = record_levels(
                            conn,
                            department_code=department,
                            valid_on=day,
                            levels=assembled,
                            source_url=department_page_url(department),
                            import_run_id=str(counters.run_id) if counters.run_id else None,
                        )
                        total_read += len(levels)
                        total_inserted += inserted
                        total_updated += updated
                        counters.artifact_path = f"{BUCKET_RAW}/massifs/{department}/{stamp}.json"
                        counters.checksum = checksum
                        counters.source_data_at = datetime.combine(
                            day, datetime.min.time(), tzinfo=UTC
                        )
                        print(
                            f"{department} {day} : {len(assembled)} massif(s), "
                            f"{inserted} créé(s), {updated} mis à jour"
                        )

                for note in pending:
                    print(f"attente : {note}")

                counters.records_read = total_read
                counters.records_inserted = total_inserted
                counters.records_updated = total_updated
                counters.records_rejected = len(rejections)
                counters.metrics = {"rejets": rejections, "en_attente": pending}
        except (ImportRunError, ValueError, httpx.HTTPError) as exc:
            print(f"échec : {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
