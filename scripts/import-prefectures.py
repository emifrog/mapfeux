"""Capture les publications officielles de la liste blanche préfectorale.

Usage :
    micromamba run -n mapfeux-geo python scripts/import-prefectures.py

Référence : cahier v2.1 §9.2 et §20.4, FR-141 à FR-143 ; ADR-026 ; plan J4.

La passe lit les entrées actives de `app.official_feeds`, archive chaque
page brute avant analyse, extrait les publications datées et les range en
citations — titre verbatim, URL, date de l'autorité. Une page en panne ou
restructurée est **comptée et visible** : republier du bruit sous le nom
d'une préfecture serait pire qu'un retard. Rien ne se supprime jamais.

Variables : `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import UTC, datetime
from datetime import time as time_of_day

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target, load_env
from geo_worker.pipelines.import_run import ImportRunError, import_run
from geo_worker.pipelines.official_feeds import (
    active_feeds,
    mark_polled,
    raw_object_name,
    record_items,
)
from geo_worker.providers.prefecture import parse_actualites
from geo_worker.storage import BUCKET_RAW, upload_object

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
SOURCE_KEY = "prefectures"

#: La capture s'annonce : un site de l'État mérite de savoir qui le lit.
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

    with (
        psycopg.connect(dsn, connect_timeout=30) as conn,
        httpx.Client(timeout=60, follow_redirects=True, headers={"user-agent": USER_AGENT}) as http,
    ):
        try:
            with import_run(
                conn, source_key=SOURCE_KEY, job_name="prefectures:actualites"
            ) as counters:
                feeds = active_feeds(conn)
                if not feeds:
                    print("Liste blanche vide : rien à capter.")
                    return 0

                total_read = 0
                total_inserted = 0
                total_refreshed = 0
                rejections: list[str] = []
                latest_published = None
                per_feed: dict[str, dict[str, int]] = {}

                for feed in feeds:
                    label = feed.department_code or feed.organisation
                    try:
                        response = http.get(feed.feed_url)
                    except httpx.HTTPError as exc:
                        mark_polled(conn, feed_id=feed.id, http_status=0)
                        rejections.append(f"{label} : injoignable ({type(exc).__name__})")
                        print(f"{label} : injoignable ({type(exc).__name__})")
                        continue

                    mark_polled(conn, feed_id=feed.id, http_status=response.status_code)
                    if response.status_code != 200:
                        rejections.append(f"{label} : HTTP {response.status_code}")
                        print(f"{label} : HTTP {response.status_code}")
                        continue

                    # Le brut d'abord, avant toute interprétation (§16.1).
                    polled_at = datetime.now(UTC)
                    object_path = raw_object_name(feed, polled_at)
                    checksum = upload_object(
                        http,
                        supabase_url=supabase_url,
                        secret_key=secret_key,
                        bucket=BUCKET_RAW,
                        object_path=object_path,
                        payload=response.content,
                        content_type="text/html",
                    )

                    items, page_rejections = parse_actualites(response.text, base_url=feed.feed_url)
                    rejections.extend(f"{label} : {reason}" for reason in page_rejections)
                    if not items:
                        # Une page d'autorité sans aucune publication datée
                        # n'existe pas : c'est une restructuration à voir.
                        rejections.append(f"{label} : aucune publication datée sur la page")
                        print(f"{label} : aucune publication datée — page restructurée ?")
                        continue

                    result = record_items(
                        conn,
                        feed_id=feed.id,
                        items=items,
                        import_run_id=str(counters.run_id) if counters.run_id else None,
                    )
                    total_read += len(items)
                    total_inserted += result.inserted
                    total_refreshed += result.refreshed
                    newest = max(item.published_on for item in items)
                    if latest_published is None or newest > latest_published:
                        latest_published = newest
                    per_feed[label] = {
                        "publications": len(items),
                        "nouvelles": result.inserted,
                    }
                    print(
                        f"{label} : {len(items)} publication(s), "
                        f"{result.inserted} nouvelle(s), {result.refreshed} revue(s)"
                    )

                    counters.artifact_path = f"{BUCKET_RAW}/{object_path}"
                    counters.checksum = checksum

                counters.records_read = total_read
                counters.records_inserted = total_inserted
                counters.records_updated = total_refreshed
                counters.records_rejected = len(rejections)
                if latest_published is not None:
                    counters.source_data_at = datetime.combine(
                        latest_published, time_of_day(), tzinfo=UTC
                    )
                counters.metrics = {"feeds": per_feed, "rejets": rejections}
        except ImportRunError as exc:
            print(f"échec : {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
