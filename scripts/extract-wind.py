"""Extrait le vent AROME au point d'un événement, vers `meteo.wind_samples`.

Usage :
    micromamba run -n mapfeux-geo python scripts/extract-wind.py --evenement MPF-XXXXXXXX
    micromamba run -n mapfeux-geo python scripts/extract-wind.py \
        --evenement MPF-XXXXXXXX --run 2026-08-17T06

Référence : cahier v2.1 §13.13 et §16.4 ; plan J8.

Sans `--run`, le run le plus frais du registre est retenu. L'extrait NetCDF
est relu depuis le stockage froid **avec vérification d'empreinte** contre le
registre : un calcul ne lit pas un fichier, il relit ce qui a été déposé.

Les deux méthodes du §16.4 sont calculées et comparées à chaque passe — la
validation est une mesure, pas une opinion — puis la bilinéaire est écrite.
Rejouer rafraîchit : la clé d'upsert (migration `20260818100000`) fait du
même point au même run une seule vérité.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
from datetime import UTC, datetime

import httpx
import psycopg
import xarray as xr

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target, load_env
from geo_worker.pipelines.wind_samples import (
    WindExtractionError,
    extract_samples,
    store_samples,
)
from geo_worker.storage import StorageError, download_object

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"


def parse_option(argv: list[str], name: str) -> str | None:
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        sys.exit(f"{name} attend une valeur.")
    return argv[index + 1]


def main(argv: list[str]) -> int:
    public_id = parse_option(argv, "--evenement")
    if public_id is None:
        sys.exit("--evenement attend un identifiant public (MPF-…).")
    run_option = parse_option(argv, "--run")

    env = load_env(ENV_FILE)
    supabase_url = env.get("SUPABASE_URL", "")
    secret_key = env.get("SUPABASE_SECRET_KEY", "")
    if supabase_url == "" or secret_key == "":
        sys.exit("SUPABASE_URL et SUPABASE_SECRET_KEY sont requises pour lire le froid.")

    dsn = dsn_from_env_file(ENV_FILE)
    host, port, database = dsn_target(dsn)
    print(f"cible : {host}:{port}/{database}")

    with psycopg.connect(dsn, connect_timeout=30) as conn:
        event = conn.execute(
            """
            select id, extensions.st_x(representative_point) as lon,
                   extensions.st_y(representative_point) as lat,
                   last_detected_at
            from fire.events
            where public_id = %(public_id)s
            """,
            {"public_id": public_id},
        ).fetchone()
        if event is None:
            sys.exit(f"Événement inconnu : {public_id}")
        _, longitude, latitude, last_detected_at = event
        print(f"événement : {public_id} ({latitude:.4f} N, {longitude:.4f} E)")
        print(f"dernière observation : {last_detected_at:%Y-%m-%d %H:%M} UTC")

        if run_option is None:
            run_row = conn.execute(
                """
                select id, run_at, source_path, checksum
                from meteo.model_runs
                where model = 'arome' and fwi_archived
                order by run_at desc
                limit 1
                """
            ).fetchone()
        else:
            try:
                wanted = datetime.strptime(run_option, "%Y-%m-%dT%H").replace(tzinfo=UTC)
            except ValueError:
                sys.exit(f"--run attend AAAA-MM-JJTHH (UTC), reçu {run_option!r}.")
            run_row = conn.execute(
                """
                select id, run_at, source_path, checksum
                from meteo.model_runs
                where model = 'arome' and fwi_archived and run_at = %(run_at)s
                """,
                {"run_at": wanted},
            ).fetchone()
        if run_row is None:
            sys.exit("Aucun run au registre pour cette demande.")
        model_run_id, run_at, source_path, checksum = run_row
        print(f"run : {run_at:%Y-%m-%d %H:%M} UTC — {source_path}")

        bucket, _, object_path = source_path.partition("/")
        with httpx.Client() as http:
            payload = download_object(
                http,
                supabase_url=supabase_url,
                secret_key=secret_key,
                bucket=bucket,
                object_path=object_path,
                expected_checksum=checksum,
            )
        print(f"extrait : {len(payload) / 1e6:.2f} Mo, empreinte conforme au registre")

        with tempfile.TemporaryDirectory() as workspace:
            local = pathlib.Path(workspace) / "extract.nc"
            local.write_bytes(payload)
            with xr.open_dataset(local) as dataset:
                bilinear = extract_samples(
                    dataset,
                    run_at=run_at,
                    longitude=longitude,
                    latitude=latitude,
                    method="bilinear",
                )
                nearest = extract_samples(
                    dataset,
                    run_at=run_at,
                    longitude=longitude,
                    latitude=latitude,
                    method="nearest",
                )

        # Validation §16.4 : l'écart entre les deux méthodes, mesuré là où le
        # produit s'en servira. Un écart de direction se lit modulo 360.
        print(f"\n{'échéance':>16}  {'vitesse':>12}  {'direction':>13}  {'Δv':>6}  {'Δdir':>6}")
        max_dv = max_dd = 0.0
        for bil, near in zip(bilinear, nearest, strict=True):
            dv = abs(bil.speed_ms - near.speed_ms)
            dd = abs((bil.direction_deg - near.direction_deg + 180.0) % 360.0 - 180.0)
            max_dv, max_dd = max(max_dv, dv), max(max_dd, dd)
            print(
                f"{bil.valid_at:%d/%m %H:%M} UTC  {bil.speed_ms:>8.2f} m/s"
                f"  {bil.direction_deg:>8.1f}°  {dv:>6.2f}  {dd:>6.1f}"
            )
        print(
            f"\nbilinéaire vs voisin : Δvitesse max {max_dv:.2f} m/s, "
            f"Δdirection max {max_dd:.1f}° "
            f"(distance à la cellule : {bilinear[0].cell_distance_m:.0f} m)"
        )

        written = store_samples(
            conn,
            model_run_id=model_run_id,
            longitude=longitude,
            latitude=latitude,
            samples=bilinear,
        )
        conn.commit()
        print(f"écrits : {written} échantillon(s) bilinéaires dans meteo.wind_samples")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (WindExtractionError, StorageError) as exc:
        print(f"échec : {exc}")
        raise SystemExit(1) from exc
