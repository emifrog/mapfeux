"""Archive les champs AROME utiles au calcul FWI.

Usage :
    micromamba run -n mapfeux-geo python scripts/archive-arome.py

Référence : ADR-025 point 4.

Décorrélé du panache : la donnée est périssable, un jour non capté est perdu
définitivement, et attendre un jalon reporté en v2 reviendrait à ne jamais
commencer.

Ce script ne calcule aucun indice et n'affiche rien. Il capte, et c'est tout.

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
from geo_worker.providers.arome import (
    ARCHIVE_EXTENT,
    AromeError,
    PackageRef,
    latest_run,
    next_reachable_noon,
    noon_lead_time,
    span_for_lead_time,
)

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
SOURCE_KEY = "arome"


def main() -> int:
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

    run = latest_run(datetime.now(UTC))
    noon = next_reachable_noon(run)
    lead = noon_lead_time(run, noon)
    reference = PackageRef(run=run, span=span_for_lead_time(lead))

    print(f"run      : {reference.run_key}")
    print(f"échéance : {lead} h (mi-journée du {noon.date()})")
    print(f"emprise  : {ARCHIVE_EXTENT.as_firms_area()}", flush=True)

    with (
        psycopg.connect(dsn_from_env_file(ENV_FILE), connect_timeout=30) as conn,
        httpx.Client(follow_redirects=True) as http,
    ):
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
                # décrit-elle ».
                #
                # L'échéance est dans le futur : la fraîcheur, calculée en
                # `now() - source_data_at`, devenait négative. La page affichait
                # « il y a moins d'une minute » pour un horodatage à venir, et
                # surtout la détection de panne était neutralisée — AROME
                # serait resté « à jour » des heures après l'arrêt de
                # l'archivage. L'échéance reste consignée dans les métriques,
                # où elle décrit le contenu sans prétendre le dater.
                counters.source_data_at = reference.run
                counters.metrics = {
                    "source_bytes": result.source_bytes,
                    "archived_bytes": result.archived_bytes,
                    "reduction": round(result.reduction, 1),
                    "echeance": noon.isoformat(),
                    "lead_hours": lead,
                    "fields": list(result.fields),
                }

                print(
                    f"\narchivé  : {result.object_path}\n"
                    f"           {result.source_bytes / 1e6:.1f} Mo → "
                    f"{result.archived_bytes / 1e6:.2f} Mo "
                    f"(facteur {result.reduction:.0f})"
                )

        except (AromeError, ImportRunError) as exc:
            print(f"échec : {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
