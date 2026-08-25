"""Calcule le panache indicatif d'un événement, vers `meteo.smoke_forecasts`.

Usage :
    micromamba run -n mapfeux-geo python scripts/compute-smoke.py --evenement MPF-XXXXXXXX
    micromamba run -n mapfeux-geo python scripts/compute-smoke.py \
        --evenement MPF-XXXXXXXX --horizon 360

Référence : cahier v2.1 §18 et §16.4 ; plan J8.

Rien de ce script ne publie : la prévision est écrite avec `is_current` à
faux, et le restera tant que la formulation publique du §22.5 n'aura pas été
validée métier. C'est l'outil d'exercice et de calibration du calcul.

Le run se choisit sur la **grille du fournisseur**, du plus frais au plus
vieux — pour un feu détecté à deux heures du matin, le bon run est celui de
minuit, pas celui de la veille à midi. Les tranches d'échéances qui manquent
au registre sont **récupérées à la demande** (§16.4) : extraites, déposées au
froid, consignées — le corpus y gagne ce que le panache exige. Une tranche
que le dépôt ne sert plus est dite indisponible, jamais inventée ; le panache
tronque et le dit.

La provenance §18.6 est complète : version, commit du worker, run, fichiers
et empreintes, paramètres, empreinte composite des entrées.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target, load_env
from geo_worker.pipelines.arome_coverage import (
    coverage_checksum,
    ensure_window_coverage,
    open_window_dataset,
)
from geo_worker.pipelines.smoke_forecast import (
    ALGORITHM_VERSION,
    PlumeError,
    PlumeParameters,
    compute_plume,
    inputs_checksum,
    store_forecast,
)
from geo_worker.providers.arome import latest_run, runs_reaching
from geo_worker.storage import StorageError

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
    bucket = env.get("SUPABASE_STORAGE_BUCKET_COLD", "")
    if supabase_url == "" or secret_key == "" or bucket == "":
        sys.exit(
            "SUPABASE_URL, SUPABASE_SECRET_KEY et SUPABASE_STORAGE_BUCKET_COLD "
            "sont requises pour lire et compléter le froid."
        )

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
        window_end = started_at + timedelta(minutes=parameters.horizon_minutes)
        print(f"événement : {public_id} ({latitude:.4f} N, {longitude:.4f} E)")
        print(f"fenêtre   : {started_at:%Y-%m-%d %H:%M} → {window_end:%H:%M} UTC")

        candidates = runs_reaching(started_at, latest=latest_run(datetime.now(UTC)))
        if not candidates:
            print("Aucun run publiable n'atteint la fenêtre : résultat vide (§18.5).")
            return 1

        coverage = None
        with httpx.Client(follow_redirects=True) as http:
            for run_at in candidates:
                print(f"\nrun candidat : {run_at:%Y-%m-%d %H:%M} UTC")
                attempt = ensure_window_coverage(
                    conn,
                    http,
                    run_at=run_at,
                    start=started_at,
                    end=window_end,
                    supabase_url=supabase_url,
                    secret_key=secret_key,
                    bucket=bucket,
                )
                if attempt.fetched_spans:
                    print(f"  récupérées  : {', '.join(attempt.fetched_spans)}")
                if attempt.unavailable_spans:
                    print(f"  introuvables : {', '.join(attempt.unavailable_spans)}")
                if attempt.has_start:
                    coverage = attempt
                    break
                print("  aucune tranche exploitable — repli sur le run précédent")

            if coverage is None:
                print("\nAucun run ne couvre la fenêtre : résultat vide (§18.5).")
                return 1

            row = conn.execute(
                """
                select id from meteo.model_runs
                where provider = 'meteo-france' and model = 'arome'
                  and run_at = %(run_at)s
                """,
                {"run_at": coverage.run_at},
            ).fetchone()
            if row is None:
                # has_start implique la ligne au registre ; son absence est
                # une incohérence à regarder, pas à enjamber.
                sys.exit("Registre incohérent : couverture sans ligne de run.")
            model_run_id = row[0]
            print(
                f"couverture : {len(coverage.files)} fichier(s), "
                f"tranches {', '.join(coverage.needed_spans)}"
            )

            with tempfile.TemporaryDirectory() as workspace:
                dataset = open_window_dataset(
                    http,
                    files=coverage.files,
                    supabase_url=supabase_url,
                    secret_key=secret_key,
                    workspace=pathlib.Path(workspace),
                )

        result = compute_plume(
            dataset,
            run_at=coverage.run_at,
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
                "run_at": coverage.run_at.isoformat(),
                "files": [
                    {"path": f.get("path"), "checksum": f.get("checksum")} for f in coverage.files
                ],
            },
            "source": {
                "event": public_id,
                "last_detected_at": started_at.isoformat(),
                "detection_count": detection_count,
                "frp_max_mw": None if frp_max is None else float(frp_max),
            },
            "inputs_checksum": inputs_checksum(
                extract_checksum=coverage_checksum(coverage.files),
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
