"""Importe la dernière mosaïque radar : brut archivé, image web, timeline.

Usage :
    micromamba run -n mapfeux-geo python scripts/import-radar.py

Référence : cahier v2.1 §16.6, §19.1, §19.3 ; plan J9.

Sans clé, le script explique le provisionnement et sort sans toucher au
journal : une configuration absente n'est pas une panne. Avec elle : la
production annoncée est comparée à la base — une frame déjà servie ne se
retélécharge pas —, le HDF5 ODIM est archivé dans `raw` avant analyse,
converti en PNG Web Mercator coloré par la palette versionnée, enregistré
dans `radar.frames` avec son expiration, et la timeline (alias JSON, au
plus 24 frames) est réécrite en dernier : un lecteur d'alias ne voit
jamais un objet absent.

Variables : `METEOFRANCE_RADAR_API_KEY` (application « Données Publiques
Radar » du portail — la clé d'une autre application produirait un 403),
plus `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from datetime import UTC, datetime

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target, load_env
from geo_worker.pipelines.import_run import ImportRunError, import_run
from geo_worker.pipelines.radar_frames import (
    alias_name,
    alias_payload,
    expire_frames,
    frame_object_name,
    has_ready_frame,
    parse_odim,
    raw_object_name,
    record_frame,
    render_web_frame,
    timeline,
)
from geo_worker.providers.radar import (
    RadarAuthError,
    RadarClient,
    RadarError,
    api_key_from,
)
from geo_worker.storage import BUCKET_RAW, BUCKET_TILES, upload_object

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
SOURCE_KEY = "radar"

PROVISIONING = """\
METEOFRANCE_RADAR_API_KEY absente : l'import radar n'est pas configuré.

Pour provisionner (une fois) :
  1. Sur https://portail-api.meteofrance.fr, souscrire à l'API
     « Données Publiques Radar » (DPRadar).
  2. Générer la clé d'application de CETTE API — une clé par application :
     celle de la vigilance produirait un 403 sans motif.
  3. La poser dans services/geo-worker/.env :
       METEOFRANCE_RADAR_API_KEY=<clé>
Le jour de la planification, la poser aussi en secret GitHub Actions."""


def main(argv: list[str]) -> int:
    env = load_env(ENV_FILE)
    api_key = api_key_from(env)
    supabase_url = env.get("SUPABASE_URL", "")
    secret_key = env.get("SUPABASE_SECRET_KEY", "")

    if api_key == "":
        print(PROVISIONING)
        return 2
    if supabase_url == "" or secret_key == "":
        sys.exit("SUPABASE_URL et SUPABASE_SECRET_KEY sont requises pour archiver le brut.")

    dsn = dsn_from_env_file(ENV_FILE)
    host, port, database = dsn_target(dsn)
    print(f"cible   : {host}:{port}/{database}")
    print("produit : mosaïque lame d'eau METROPOLE, maille 500 m", flush=True)

    with (
        psycopg.connect(dsn, connect_timeout=30) as conn,
        httpx.Client() as http,
    ):
        client = RadarClient(http, api_key)
        try:
            with import_run(
                conn, source_key=SOURCE_KEY, job_name="radar:lame-d-eau:5min"
            ) as counters:
                announced = client.announced_at()
                if announced is not None and has_ready_frame(conn, announced):
                    # La production n'a pas bougé : rien à retélécharger. La
                    # passe reste un succès daté de la donnée réellement servie.
                    expired = expire_frames(conn, now=datetime.now(UTC))
                    counters.records_read = 1
                    counters.source_data_at = announced
                    counters.metrics = {"deja_servie": True, "expirees": expired}
                    print(f"frame   : {announced:%Y-%m-%d %H:%M} déjà servie — rien à faire")
                    return 0

                product = client.fetch_product()
                checksum = hashlib.sha256(product.payload).hexdigest()
                mosaic = parse_odim(product.payload)
                print(
                    f"frame   : {mosaic.acquired_at:%Y-%m-%d %H:%M} UTC, "
                    f"{len(product.payload) / 1e6:.2f} Mo, sha256 {checksum[:12]}…"
                )

                # 1. Le brut d'abord, avant toute interprétation (§16.1).
                raw_name = raw_object_name(mosaic, product.filename)
                upload_object(
                    http,
                    supabase_url=supabase_url,
                    secret_key=secret_key,
                    bucket=BUCKET_RAW,
                    object_path=raw_name,
                    payload=product.payload,
                )

                # 2. La conversion contrôlée, puis l'image publique immuable.
                frame = render_web_frame(mosaic)
                frame_checksum = hashlib.sha256(frame.png).hexdigest()
                web_name = frame_object_name(mosaic.acquired_at, frame_checksum)
                upload_object(
                    http,
                    supabase_url=supabase_url,
                    secret_key=secret_key,
                    bucket=BUCKET_TILES,
                    object_path=web_name,
                    payload=frame.png,
                    content_type="image/png",
                    cache_control="max-age=31536000",
                )
                print(
                    f"image   : {frame.width}x{frame.height}, "
                    f"{len(frame.png) / 1e3:.0f} ko — {web_name}"
                )

                # 3. Le registre : frame prête, expiration posée, vieilles
                #    frames basculées.
                record_frame(
                    conn,
                    acquired_at=mosaic.acquired_at,
                    projection=mosaic.projdef,
                    extent=frame.extent,
                    raw_path=f"{BUCKET_RAW}/{raw_name}",
                    web_path=f"{BUCKET_TILES}/{web_name}",
                    checksum=checksum,
                )
                expired = expire_frames(conn, now=datetime.now(UTC))

                # 4. La timeline en dernier : la bascule visible du front.
                #    Elle se lit sur la même connexion, donc voit la frame
                #    tout juste écrite ; la validation appartient à
                #    `import_run`, qui clôt la passe.
                frames = timeline(conn)
                alias = alias_payload(frames, extent=frame.extent, published_at=datetime.now(UTC))
                upload_object(
                    http,
                    supabase_url=supabase_url,
                    secret_key=secret_key,
                    bucket=BUCKET_TILES,
                    object_path=alias_name(),
                    payload=(json.dumps(alias, ensure_ascii=False, indent=2) + "\n").encode(
                        "utf-8"
                    ),
                    content_type="application/json",
                    cache_control="max-age=60",
                )

                counters.records_read = 1
                counters.records_inserted = 1
                counters.artifact_path = f"{BUCKET_RAW}/{raw_name}"
                counters.checksum = checksum
                counters.source_data_at = mosaic.acquired_at
                counters.metrics = {
                    "timeline": len(frames),
                    "expirees": expired,
                    "octets_web": len(frame.png),
                }
                print(f"timeline : {len(frames)} frame(s), {expired} expirée(s)")
        except RadarAuthError as exc:
            print(f"échec d'authentification : {exc}")
            return 1
        except (RadarError, ImportRunError, ValueError) as exc:
            print(f"échec : {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
