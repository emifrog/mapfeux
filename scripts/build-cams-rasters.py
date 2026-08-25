"""Dérive et publie les rasters CAMS : COG et tuiles par échéance (§19.1).

Usage :
    micromamba run -n mapfeux-geo python scripts/build-cams-rasters.py
    micromamba run -n mapfeux-geo python scripts/build-cams-rasters.py --date 2026-08-25
    micromamba run -n mapfeux-geo python scripts/build-cams-rasters.py --local

Référence : cahier v2.1 §19.1 et §16.5 ; plan J9.

Le run visé — courant par défaut, daté par `--date` — est relu du registre
`air`, ses NetCDF téléchargés du compartiment `raw` avec **empreinte
vérifiée**, puis chaque échéance de chaque polluant devient un COG et une
archive PMTiles de tuiles PNG colorées par la palette versionnée.

L'ordre de publication rend la bascule sûre : les objets d'abord (noms à
empreinte, cache éternel), le registre ensuite, les **alias JSON en
dernier** — un lecteur d'alias ne voit jamais un objet absent, et un échec
à mi-chemin laisse l'alias sur la version précédente, entière (§16.5).

`--local` : écrit tout dans data/derived/cams/ sans publier ni toucher la base.
"""

from __future__ import annotations

import hashlib
import io
import json
import pathlib
import sys
import tempfile
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target, load_env
from geo_worker.pipelines.cams_import import AIR_MODEL, PROVIDER
from geo_worker.pipelines.cams_rasters import (
    PollutantGrid,
    RasterAsset,
    alias_name,
    alias_payload,
    cog_bytes,
    cog_object_name,
    load_grid,
    record_raster_assets,
    render_tiles,
    tiles_object_name,
    tileset_metadata,
    write_air_pmtiles,
)
from geo_worker.providers.cams import POLLUTANTS
from geo_worker.storage import BUCKET_TILES, download_object, upload_object

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
# Les noms d'objets commencent déjà par `cams/` : la sortie locale reflète
# le compartiment, alias à la racine comme chez Storage.
OUTPUT_DIR = ROOT / "data" / "derived"


def parse_option(argv: list[str], name: str) -> str | None:
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        sys.exit(f"{name} attend une valeur.")
    return argv[index + 1]


def find_run(
    conn: psycopg.Connection[Any], run_date: str | None
) -> tuple[UUID, datetime, list[tuple[str, str, str]]]:
    """Le run visé et ses bruts : (id, run_at, [(polluant, chemin, empreinte)]).

    Sans `--date`, le run **courant** — celui que la publication atomique a
    désigné. Les deux polluants sont exigés : dériver un run à moitié
    importé publierait un alias amputé.
    """
    with conn.cursor() as cur:
        if run_date is None:
            cur.execute(
                """
                select id, run_at from air.model_runs
                where provider = %(provider)s and model = %(model)s and is_current
                """,
                {"provider": PROVIDER, "model": AIR_MODEL},
            )
        else:
            cur.execute(
                """
                select id, run_at from air.model_runs
                where provider = %(provider)s and model = %(model)s and run_at = %(run_at)s
                """,
                {
                    "provider": PROVIDER,
                    "model": AIR_MODEL,
                    "run_at": datetime.strptime(run_date, "%Y-%m-%d").replace(tzinfo=UTC),
                },
            )
        run = cur.fetchone()
        if run is None:
            sys.exit("Aucun run au registre pour cette cible. Importer d'abord (import-cams.py).")
        run_id, run_at = UUID(str(run[0])), run[1]

        cur.execute(
            """
            select pollutant, asset_path, checksum from air.grid_assets
            where model_run_id = %(run_id)s and kind = 'raw'
            order by pollutant
            """,
            {"run_id": run_id},
        )
        raws = [(str(p), str(path), str(checksum)) for p, path, checksum in cur.fetchall()]

    missing = set(POLLUTANTS) - {p for p, _, _ in raws}
    if missing:
        sys.exit(f"Bruts absents du registre pour : {', '.join(sorted(missing))}.")
    return run_id, run_at, raws


def derive_pollutant(
    grid: PollutantGrid,
) -> tuple[list[tuple[RasterAsset, bytes]], list[tuple[RasterAsset, bytes]]]:
    """Tous les actifs d'un polluant : [(actif COG, octets)], [(actif tuiles, octets)]."""
    cogs: list[tuple[RasterAsset, bytes]] = []
    tilesets: list[tuple[RasterAsset, bytes]] = []

    for index, lead in enumerate(grid.lead_hours):
        cog = cog_bytes(grid, index)
        cog_checksum = hashlib.sha256(cog).hexdigest()
        cogs.append(
            (
                RasterAsset(
                    pollutant=grid.pollutant,
                    kind="cog",
                    lead_hours=lead,
                    valid_at=grid.valid_at(index),
                    object_name=cog_object_name(grid, index, cog_checksum),
                    checksum=cog_checksum,
                    size_bytes=len(cog),
                    tile_count=0,
                ),
                cog,
            )
        )

        tiles = render_tiles(grid, index)
        buffer = io.BytesIO()
        count = write_air_pmtiles(buffer, tiles, tileset_metadata(grid, index), grid)
        archive = buffer.getvalue()
        archive_checksum = hashlib.sha256(archive).hexdigest()
        tilesets.append(
            (
                RasterAsset(
                    pollutant=grid.pollutant,
                    kind="tile",
                    lead_hours=lead,
                    valid_at=grid.valid_at(index),
                    object_name=tiles_object_name(grid, index, archive_checksum),
                    checksum=archive_checksum,
                    size_bytes=len(archive),
                    tile_count=count,
                ),
                archive,
            )
        )

    return cogs, tilesets


def main(argv: list[str]) -> int:
    local_only = "--local" in argv
    run_date = parse_option(argv, "--date")

    env = load_env(ENV_FILE)
    supabase_url = env.get("SUPABASE_URL", "")
    secret_key = env.get("SUPABASE_SECRET_KEY", "")
    if supabase_url == "" or secret_key == "":
        sys.exit("SUPABASE_URL et SUPABASE_SECRET_KEY sont requises pour relire le brut.")

    dsn = dsn_from_env_file(ENV_FILE)
    host, port, database = dsn_target(dsn)
    print(f"cible : {host}:{port}/{database}")

    started = time.monotonic()
    with psycopg.connect(dsn, connect_timeout=30) as conn, httpx.Client() as http:
        run_id, run_at, raws = find_run(conn, run_date)
        print(f"run   : {run_at:%Y-%m-%d} 00 UTC — {run_id}\n")

        grids: list[PollutantGrid] = []
        with tempfile.TemporaryDirectory() as workdir:
            for pollutant, asset_path, checksum in raws:
                bucket, _, object_path = asset_path.partition("/")
                payload = download_object(
                    http,
                    supabase_url=supabase_url,
                    secret_key=secret_key,
                    bucket=bucket,
                    object_path=object_path,
                    expected_checksum=checksum,
                )
                netcdf = pathlib.Path(workdir) / f"{pollutant}.nc"
                netcdf.write_bytes(payload)
                grids.append(
                    load_grid(netcdf, pollutant=pollutant, run_at=run_at, source_checksum=checksum)
                )
                print(f"{pollutant} : brut relu, empreinte vérifiée ({len(payload) / 1e6:.2f} Mo)")

        published_at = datetime.now(UTC)
        total_bytes = 0
        total_objects = 0

        for grid in grids:
            cogs, tilesets = derive_pollutant(grid)
            artifacts = cogs + tilesets
            pollutant_bytes = sum(len(payload) for _, payload in artifacts)
            total_bytes += pollutant_bytes
            total_objects += len(artifacts)
            print(
                f"{grid.pollutant} : {len(cogs)} COG + {len(tilesets)} archives de tuiles "
                f"({sum(a.tile_count for a, _ in tilesets)} tuiles, "
                f"{pollutant_bytes / 1e6:.2f} Mo)"
            )

            if local_only:
                for asset, payload in artifacts:
                    target = OUTPUT_DIR / asset.object_name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(payload)
                alias_file = OUTPUT_DIR / alias_name(grid.pollutant)
                alias = alias_payload(grid, [a for a, _ in tilesets], published_at=published_at)
                alias_file.write_text(
                    json.dumps(alias, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                continue

            # 1. Les objets d'abord : noms à empreinte, cache éternel (§21.1).
            for asset, payload in artifacts:
                upload_object(
                    http,
                    supabase_url=supabase_url,
                    secret_key=secret_key,
                    bucket=BUCKET_TILES,
                    object_path=asset.object_name,
                    payload=payload,
                    content_type=(
                        "image/tiff" if asset.kind == "cog" else "application/octet-stream"
                    ),
                    cache_control="max-age=31536000",
                )

            # 2. Le registre ensuite : l'échantillonnage (§19.2) ne peut
            #    désigner que des objets déjà déposés.
            record_raster_assets(
                conn, run_id=run_id, bucket=BUCKET_TILES, assets=[a for a, _ in artifacts]
            )
            conn.commit()

            # 3. L'alias en dernier : la bascule visible du front, atomique.
            alias = alias_payload(grid, [a for a, _ in tilesets], published_at=published_at)
            upload_object(
                http,
                supabase_url=supabase_url,
                secret_key=secret_key,
                bucket=BUCKET_TILES,
                object_path=alias_name(grid.pollutant),
                payload=(json.dumps(alias, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
                content_type="application/json",
                cache_control="max-age=60",
            )

    print(f"\ntotal : {total_objects} objets, {total_bytes / 1e6:.2f} Mo")
    print(f"durée : {time.monotonic() - started:.0f} s")

    if local_only:
        print(f"--local : tout est sous {OUTPUT_DIR.relative_to(ROOT).as_posix()}, rien publié.")
        return 0

    base = supabase_url.rstrip("/")
    for pollutant in POLLUTANTS:
        print(f"alias : {base}/storage/v1/object/public/{BUCKET_TILES}/{alias_name(pollutant)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
