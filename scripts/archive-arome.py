"""Archive les champs AROME utiles au calcul FWI.

Usage :
    micromamba run -n mapfeux-geo python scripts/archive-arome.py
    micromamba run -n mapfeux-geo python scripts/archive-arome.py --jour 2026-08-08

Référence : ADR-025 point 4 ; plan J8 pour le registre des runs.

Décorrélé du panache : la donnée est périssable, un jour non capté est perdu
définitivement, et attendre un jalon reporté en v2 reviendrait à ne jamais
commencer.

Sans option, le script vise la prochaine mi-journée atteignable. `--jour`
rattrape la mi-journée d'un jour donné, tant que le dépôt sert encore un run
qui l'atteint — c'est le geste de reprise après un cron manqué.

La mi-journée est atteignable par plusieurs runs, à échéance croissante : si
le plus frais n'est pas encore publié — le délai de diffusion fluctue autour
de trois heures et demie, et les passes des 8 et 9 août 2026 sont mortes sur
ce seuil — le script replie sur les précédents au lieu d'échouer. La
disponibilité est sondée par HEAD avant d'ouvrir l'import_run : le journal ne
porte que les passes réellement tentées.

Chaque extrait déposé est enregistré au registre `meteo.model_runs` (§13.12) :
c'est là que le panache choisira son run, sans lister le compartiment.

Dépôt dans le compartiment **froid**, désigné par `SUPABASE_STORAGE_BUCKET_COLD`
— jamais purgé (§12.4). `raw` ne conviendrait pas : le registre l'annonce en
rétention trente jours, et ce qui est archivé ici ne se retrouve nulle part
passé ce délai.

Variables attendues, du fichier `.env` ou de l'environnement, ce dernier
l'emportant : `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
`SUPABASE_STORAGE_BUCKET_COLD`.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import UTC, datetime

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, load_env
from geo_worker.pipelines.arome_archive import archive_package
from geo_worker.pipelines.import_run import ImportRunError, import_run
from geo_worker.pipelines.meteo_runs import record_model_run
from geo_worker.providers.arome import (
    ARCHIVE_EXTENT,
    RESOLUTION,
    AromeError,
    PackageRef,
    PackageUnavailableError,
    latest_run,
    next_reachable_noon,
    noon_lead_time,
    runs_reaching_noon,
    span_for_lead_time,
)

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
SOURCE_KEY = "arome"


def parse_option(argv: list[str], name: str) -> str | None:
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        sys.exit(f"{name} attend une valeur.")
    return argv[index + 1]


def resolve_noon(argv: list[str], latest: datetime) -> datetime:
    day_option = parse_option(argv, "--jour")
    if day_option is None:
        return next_reachable_noon(latest)
    try:
        day = datetime.strptime(day_option, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        sys.exit(f"--jour attend une date AAAA-MM-JJ, reçu {day_option!r}.")
    return day.replace(hour=11)


def main(argv: list[str]) -> int:
    env = load_env(ENV_FILE)
    supabase_url = env.get("SUPABASE_URL", "")
    secret_key = env.get("SUPABASE_SECRET_KEY", "")
    # Stockage **froid**, et non `raw`. Le registre des sources déclare `raw` en
    # « GRIB2 bruts 30 jours » : y déposer l'archive pérenne l'exposerait à la
    # purge de rétention, c'est-à-dire au risque « purge accidentelle du
    # stockage froid PR-1 » du §29. Or l'argument même de cet archivage est que
    # la donnée ne se rattrape pas — un jour purgé est un jour perdu.
    bucket = env.get("SUPABASE_STORAGE_BUCKET_COLD", "")

    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", supabase_url),
            ("SUPABASE_SECRET_KEY", secret_key),
            ("SUPABASE_STORAGE_BUCKET_COLD", bucket),
        )
        if value == ""
    ]
    if missing:
        sys.exit(f"Variables absentes : {', '.join(missing)}")

    latest = latest_run(datetime.now(UTC))
    noon = resolve_noon(argv, latest)
    candidates = runs_reaching_noon(noon, latest=latest)
    if not candidates:
        print(f"Aucun run publiable n'atteint la mi-journée du {noon.date()}.")
        return 1

    print(f"mi-journée : {noon.isoformat()}")
    print(f"emprise    : {ARCHIVE_EXTENT.as_firms_area()}")
    print(f"candidats  : {len(candidates)} run(s), du plus frais au plus vieux", flush=True)

    with (
        psycopg.connect(dsn_from_env_file(ENV_FILE), connect_timeout=30) as conn,
        httpx.Client(follow_redirects=True) as http,
    ):
        for run in candidates:
            lead = noon_lead_time(run, noon)
            reference = PackageRef(run=run, span=span_for_lead_time(lead))
            print(f"\nrun      : {reference.run_key}")
            print(f"           échéance {lead} h, tranche {reference.span}")

            # Sondé avant d'ouvrir l'import_run : un run pas encore publié est
            # un état normal du dépôt, pas une passe échouée à journaliser.
            probe = http.head(reference.url, timeout=60)
            if probe.status_code == 404:
                print("           absent du dépôt — repli sur le run précédent")
                continue

            try:
                with import_run(
                    conn, source_key=SOURCE_KEY, job_name=f"arome:fwi:{reference.span}"
                ) as counters:
                    result = archive_package(
                        http,
                        reference=reference,
                        extent=ARCHIVE_EXTENT,
                        lead_hours=lead,
                        supabase_url=supabase_url,
                        secret_key=secret_key,
                        bucket=bucket,
                    )

                    counters.records_read = 1
                    counters.records_inserted = 1
                    counters.artifact_path = f"{bucket}/{result.object_path}"
                    counters.checksum = result.checksum
                    # Heure de **publication du run**, non l'échéance de la
                    # prévision. La question posée par /statut est « à quand
                    # remonte la donnée dont nous disposons », pas « que
                    # décrit-elle ». L'échéance reste dans les métriques, où
                    # elle décrit le contenu sans prétendre le dater.
                    counters.source_data_at = reference.run
                    counters.metrics = {
                        "source_bytes": result.source_bytes,
                        "archived_bytes": result.archived_bytes,
                        "reduction": round(result.reduction, 1),
                        "echeance": noon.isoformat(),
                        "lead_hours": lead,
                        "fields": list(result.fields),
                    }

                    model_run_id = record_model_run(
                        conn,
                        run_at=reference.run,
                        span=reference.span,
                        object_path=f"{bucket}/{result.object_path}",
                        checksum=result.checksum,
                        fields=list(result.fields),
                        target_lead_hours=lead,
                        domain=ARCHIVE_EXTENT.as_firms_area(),
                        resolution=RESOLUTION,
                    )

                    print(
                        f"archivé  : {result.object_path}\n"
                        f"           {result.source_bytes / 1e6:.1f} Mo → "
                        f"{result.archived_bytes / 1e6:.2f} Mo "
                        f"(facteur {result.reduction:.0f})\n"
                        f"registre : meteo.model_runs {model_run_id}"
                    )
                return 0

            except PackageUnavailableError as exc:
                # Retiré entre le sondage et le téléchargement : rare, mais le
                # repli reste le bon geste. La passe échouée est au journal.
                print(f"           {exc} — repli sur le run précédent")
                continue
            except (AromeError, ImportRunError) as exc:
                print(f"échec : {exc}")
                return 1

    print("\néchec : aucun des runs candidats n'est disponible sur le dépôt.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
