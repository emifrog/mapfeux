"""Calcule le panache indicatif d'un événement, vers `meteo.smoke_forecasts`.

Usage :
    micromamba run -n mapfeux-geo python scripts/compute-smoke.py --evenement MPF-XXXXXXXX
    micromamba run -n mapfeux-geo python scripts/compute-smoke.py \
        --evenement MPF-XXXXXXXX --horizon 360

Référence : cahier v2.1 §18 ; plan J8.

Rien de ce script ne publie : la prévision est écrite avec `is_current` à
faux, et le restera tant que la formulation publique du §22.5 n'aura pas été
validée métier. C'est l'outil d'exercice et de calibration du calcul.

Le run est choisi au registre : le plus frais dont la fenêtre d'échéances
couvre la dernière observation de l'événement. L'extrait est relu du froid
avec empreinte vérifiée. La provenance §18.6 est complète : version, commit
du worker, run, paramètres, empreinte des entrées, détections sources.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime

import httpx
import psycopg
import xarray as xr

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target, load_env
from geo_worker.pipelines.smoke_forecast import (
    ALGORITHM_VERSION,
    PlumeError,
    PlumeParameters,
    compute_plume,
    inputs_checksum,
    store_forecast,
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


def worker_commit() -> str:
    """Commit du worker au moment du calcul (§18.6)."""
    git = shutil.which("git")
    if git is None:
        return "inconnu"
    # Exécutable résolu par shutil.which, arguments constants : rien
    # d'extérieur n'entre dans la commande.
    result = subprocess.run(  # noqa: S603
        [git, "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main(argv: list[str]) -> int:
    public_id = parse_option(argv, "--evenement")
    if public_id is None:
        sys.exit("--evenement attend un identifiant public (MPF-…).")
    horizon_option = parse_option(argv, "--horizon")
    parameters = (
        PlumeParameters()
        if horizon_option is None
        else PlumeParameters(horizon_minutes=int(horizon_option))
    )

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
                   last_detected_at, detection_count, frp_max_mw
            from fire.events
            where public_id = %(public_id)s
            """,
            {"public_id": public_id},
        ).fetchone()
        if event is None:
            sys.exit(f"Événement inconnu : {public_id}")
        event_id, longitude, latitude, started_at, detection_count, frp_max = event
        print(f"événement : {public_id} ({latitude:.4f} N, {longitude:.4f} E)")
        print(f"départ    : {started_at:%Y-%m-%d %H:%M} UTC (dernière observation)")
        print(f"horizon   : {parameters.horizon_minutes} min, pas {parameters.step_minutes} min")

        run_row = conn.execute(
            """
            select id, run_at, source_path, checksum
            from meteo.model_runs
            where model = 'arome' and fwi_archived
              and run_at <= %(start)s
              and run_at + make_interval(
                    hours => (select max(l) from unnest(available_leads) l)
                  ) >= %(start)s
            order by run_at desc
            limit 1
            """,
            {"start": started_at},
        ).fetchone()
        if run_row is None:
            print(
                "Aucun run du registre ne couvre la dernière observation : "
                "résultat vide (§18.5), rien n'est écrit."
            )
            return 1
        model_run_id, run_at, source_path, checksum = run_row
        print(f"run       : {run_at:%Y-%m-%d %H:%M} UTC — {source_path}")

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
        print(f"extrait   : {len(payload) / 1e6:.2f} Mo, empreinte conforme au registre")

        with tempfile.TemporaryDirectory() as workspace:
            local = pathlib.Path(workspace) / "extract.nc"
            local.write_bytes(payload)
            with xr.open_dataset(local) as dataset:
                result = compute_plume(
                    dataset,
                    run_at=run_at,
                    longitude=longitude,
                    latitude=latitude,
                    started_at=started_at,
                    parameters=parameters,
                )

        if result is None:
            print("Entrées insuffisantes sur l'horizon : résultat vide (§18.5).")
            return 1

        print(f"\n{'heure':>11}  {'vitesse':>9}  {'direction':>9}  {'distance':>9}  {'largeur':>9}")
        for step in result.steps:
            print(
                f"{step.valid_at:%H:%M} UTC  {step.speed_ms:>5.1f} m/s"
                f"  {step.direction_deg:>7.0f}°  {step.distance_m / 1000:>6.1f} km"
                f"  {step.width_m / 1000:>6.2f} km"
            )
        print(
            f"\nenveloppe : {result.area_km2} km² · confiance {result.confidence_level}"
            f" · valide {result.valid_from:%H:%M} → {result.valid_to:%H:%M} UTC"
        )
        print(f"drapeaux  : {', '.join(result.quality_flags)}")

        provenance = {
            "worker_commit": worker_commit(),
            "model_run": {
                "id": str(model_run_id),
                "run_at": run_at.isoformat(),
                "source_path": source_path,
                "checksum": checksum,
            },
            "source": {
                "event": public_id,
                "last_detected_at": started_at.isoformat(),
                "detection_count": detection_count,
                "frp_max_mw": None if frp_max is None else float(frp_max),
            },
            "inputs_checksum": inputs_checksum(
                extract_checksum=checksum,
                public_id=public_id,
                started_at=started_at,
                longitude=longitude,
                latitude=latitude,
                parameters=parameters,
            ),
            "computed_at": datetime.now(UTC).isoformat(),
        }

        forecast_id = store_forecast(
            conn,
            event_id=event_id,
            model_run_id=model_run_id,
            result=result,
            parameters=parameters,
            provenance=provenance,
        )
        conn.commit()
        print(f"\nprévision : {forecast_id} ({ALGORITHM_VERSION}, is_current=false)")

        communes = conn.execute(
            """
            select a.exposure_rank, a.insee_code, m.name,
                   a.first_intersection_at, a.overlap_area_km2, a.overlap_ratio
            from meteo.affected_municipalities a
            join geo.municipalities m on m.insee_code = a.insee_code
            where a.forecast_id = %(forecast_id)s
            order by a.exposure_rank
            """,
            {"forecast_id": forecast_id},
        ).fetchall()
        print(f"\ncommunes potentiellement concernées : {len(communes)}")
        for rank, insee, name, first_at, area, ratio in communes:
            print(
                f"  {rank:>2}. {name} ({insee}) — dès {first_at:%H:%M} UTC, "
                f"{area} km² ({float(ratio) * 100:.1f} % de la commune)"
            )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (PlumeError, StorageError) as exc:
        print(f"échec : {exc}")
        raise SystemExit(1) from exc
