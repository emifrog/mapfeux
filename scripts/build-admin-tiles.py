"""Génère et publie les tuiles vectorielles des limites administratives.

Usage :
    micromamba run -n mapfeux-geo python scripts/build-admin-tiles.py
    micromamba run -n mapfeux-geo python scripts/build-admin-tiles.py --local
    micromamba run -n mapfeux-geo python scripts/build-admin-tiles.py --depuis-archive

`--depuis-archive` publie l'archive locale existante sans regénérer : le cas
d'un dépôt refusé après une génération réussie — vécu le 7 août, quand la
limite d'envoi du projet était encore à 50 Mo pour une archive de 70.

Référence : cahier §21.1 et §9.5 ; J3 « génération PMTiles ».

À lancer après tout import de communes ou de territoires. Le découpage est
fait par PostGIS, l'archive est écrite localement puis déposée dans le
compartiment public `tiles` sous un nom porteur de son empreinte —
`limites-administratives-<sha12>.pmtiles` — pour un cache CDN long (§21.1).
Un petit fichier d'alias `limites-administratives.json`, lui, est réécrit à
chaque publication : c'est lui que le front lit pour trouver la version
courante, et c'est ce qui rend la bascule atomique.

`--local` : génère sans publier.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
from datetime import UTC, datetime

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, load_env
from geo_worker.pipelines.admin_tiles import (
    TILESET_NAME,
    generate_tiles,
    tileset_metadata,
    write_pmtiles,
)
from geo_worker.providers.admin_boundaries import source_version
from geo_worker.storage import BUCKET_TILES, upload_object

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
OUTPUT_DIR = ROOT / "data" / "derived"


def main(argv: list[str]) -> int:
    local_only = "--local" in argv
    from_archive = "--depuis-archive" in argv
    version = source_version()
    output_path = OUTPUT_DIR / f"{TILESET_NAME}.pmtiles"

    print(f"tuiles  : {TILESET_NAME}")
    print(f"version : {version}\n", flush=True)

    started = time.monotonic()
    if from_archive:
        if not output_path.exists():
            sys.exit(f"Archive absente : {output_path}. Générer d'abord, sans --depuis-archive.")
        # Le compte de tuiles vit dans l'en-tête de l'archive : le relire vaut
        # mieux que de le supposer.
        from pmtiles.tile import deserialize_header

        header = deserialize_header(output_path.read_bytes()[:127])
        written = int(header["addressed_tiles_count"])
    else:
        with psycopg.connect(dsn_from_env_file(ENV_FILE), connect_timeout=30) as conn:
            # Lecture seule, mais les bandes denses du zoom 12 sont des
            # requêtes lourdes : le temps de session par défaut ne suffit pas.
            conn.execute("set statement_timeout = '10min'")
            tiles = generate_tiles(
                conn, on_progress=lambda message: print(f"  {message}", flush=True)
            )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as handle:
            written = write_pmtiles(handle, tiles, tileset_metadata(version))

    payload = output_path.read_bytes()
    checksum = hashlib.sha256(payload).hexdigest()
    size_mb = len(payload) / 1_048_576

    print(f"\narchive : {output_path.relative_to(ROOT).as_posix()}")
    print(f"          {written} tuiles, {size_mb:.1f} Mo, sha256 {checksum[:12]}…")
    print(f"durée   : {time.monotonic() - started:.0f} s")

    if local_only:
        print("\n--local : pas de publication.")
        return 0

    env = load_env(ENV_FILE)
    supabase_url = env.get("SUPABASE_URL", "")
    secret_key = env.get("SUPABASE_SECRET_KEY", "")
    if supabase_url == "" or secret_key == "":
        sys.exit("SUPABASE_URL ou SUPABASE_SECRET_KEY absente : publication impossible.")

    object_name = f"{TILESET_NAME}-{checksum[:12]}.pmtiles"
    alias = {
        "objet": object_name,
        "sha256": checksum,
        "tuiles": written,
        "octets": len(payload),
        "version": version,
        "publie_le": datetime.now(UTC).isoformat(timespec="seconds"),
    }

    with httpx.Client() as client:
        # L'archive d'abord, l'alias ensuite : un lecteur de l'alias ne peut
        # jamais pointer vers un objet qui n'existe pas encore (§21.1).
        upload_object(
            client,
            supabase_url=supabase_url,
            secret_key=secret_key,
            bucket=BUCKET_TILES,
            object_path=object_name,
            payload=payload,
            # Le nom porte l'empreinte du contenu : l'objet ne change jamais,
            # le cache peut être éternel (§21.1). Forme stricte `max-age=N` :
            # Storage ignore toute autre syntaxe.
            cache_control="max-age=31536000",
            timeout=600.0,
        )
        upload_object(
            client,
            supabase_url=supabase_url,
            secret_key=secret_key,
            bucket=BUCKET_TILES,
            object_path=f"{TILESET_NAME}.json",
            payload=(json.dumps(alias, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            content_type="application/json",
            # L'alias, lui, est le pointeur mutable : cache court.
            cache_control="max-age=60",
        )

    base = supabase_url.rstrip("/")
    print(f"\npublié  : {base}/storage/v1/object/public/{BUCKET_TILES}/{object_name}")
    print(f"alias   : {base}/storage/v1/object/public/{BUCKET_TILES}/{TILESET_NAME}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
