"""Importe un run CAMS Europe : PM2,5 et PM10, brut déposé, publication atomique.

Usage :
    micromamba run -n mapfeux-geo python scripts/import-cams.py
    micromamba run -n mapfeux-geo python scripts/import-cams.py --date 2026-08-24

Référence : cahier v2.1 §16.5 et §13.17 ; plan J9.

Sans clé, le script explique le provisionnement et sort sans toucher au
journal : une configuration absente n'est pas une panne. Avec elle, chaque
polluant est récupéré depuis l'ADS, son NetCDF déposé dans `raw`, le run
enregistré au registre du schéma `air` — et la publication ne bascule que si
le run est **complet** : à moitié importé, le run précédent continue de
servir (§16.5).

Variables : `COPERNICUS_URL`, `COPERNICUS_KEY` (`.env.example`), plus
`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
`SUPABASE_STORAGE_BUCKET_RAW`.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import UTC, datetime

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target, load_env
from geo_worker.pipelines.cams_import import (
    default_run_at,
    import_pollutant,
    publish_run,
    record_air_run,
)
from geo_worker.pipelines.import_run import ImportRunError, import_run
from geo_worker.providers.cams import (
    DATASET,
    POLLUTANTS,
    CamsAuthError,
    CamsError,
    CamsRequest,
)

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
SOURCE_KEY = "cams"

#: Échéances importées : les vingt-quatre premières heures, horaires. Le
#: produit en offre 96 ; on n'importe que ce que l'affichage servira, et la
#: fenêtre s'élargira quand un besoin la réclamera.
LEAD_HOURS = tuple(range(0, 25))

PROVISIONING = """\
COPERNICUS_KEY absente : l'import CAMS n'est pas configuré.

Pour provisionner (une fois) :
  1. Créer un compte sur https://ads.atmosphere.copernicus.eu (gratuit).
  2. Sur la page du jeu %s,
     onglet « Download », accepter la licence CAMS en bas de page.
  3. Copier le jeton : profil → « Personal Access Token ».
  4. Le poser dans services/geo-worker/.env :
       COPERNICUS_URL=https://ads.atmosphere.copernicus.eu/api
       COPERNICUS_KEY=<jeton>
Le jour de la planification, le poser aussi en secret GitHub Actions."""


def parse_option(argv: list[str], name: str) -> str | None:
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        sys.exit(f"{name} attend une valeur.")
    return argv[index + 1]


def main(argv: list[str]) -> int:
    env = load_env(ENV_FILE)
    base_url = env.get("COPERNICUS_URL", "https://ads.atmosphere.copernicus.eu/api")
    token = env.get("COPERNICUS_KEY", "")
    supabase_url = env.get("SUPABASE_URL", "")
    secret_key = env.get("SUPABASE_SECRET_KEY", "")
    bucket = env.get("SUPABASE_STORAGE_BUCKET_RAW", "raw")

    if token == "":
        print(PROVISIONING % f"https://ads.atmosphere.copernicus.eu/datasets/{DATASET}")
        return 2
    if supabase_url == "" or secret_key == "":
        sys.exit("SUPABASE_URL et SUPABASE_SECRET_KEY sont requises pour déposer le brut.")

    date_option = parse_option(argv, "--date")
    if date_option is None:
        run_at = default_run_at(datetime.now(UTC))
    else:
        try:
            run_at = datetime.strptime(date_option, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            sys.exit(f"--date attend AAAA-MM-JJ, reçu {date_option!r}.")

    print(f"run       : {run_at:%Y-%m-%d} 00 UTC — {DATASET}")
    print(f"polluants : {', '.join(POLLUTANTS)} · échéances 0-{max(LEAD_HOURS)} h", flush=True)

    dsn = dsn_from_env_file(ENV_FILE)
    host, port, database = dsn_target(dsn)
    print(f"cible     : {host}:{port}/{database}")

    with (
        psycopg.connect(dsn, connect_timeout=30) as conn,
        httpx.Client() as http,
    ):
        try:
            with import_run(conn, source_key=SOURCE_KEY, job_name="cams:pm:0-24h") as counters:
                imports = []
                for pollutant in POLLUTANTS:
                    request = CamsRequest(pollutant=pollutant, run_at=run_at, lead_hours=LEAD_HOURS)
                    print(f"\n{pollutant} : soumission à l'ADS…", flush=True)
                    item = import_pollutant(
                        http,
                        base_url=base_url,
                        token=token,
                        request=request,
                        supabase_url=supabase_url,
                        secret_key=secret_key,
                        bucket=bucket,
                    )
                    imports.append(item)
                    print(
                        f"{pollutant} : {item.stored_bytes / 1e6:.2f} Mo déposés — "
                        f"{item.object_path}"
                    )

                complete = len(imports) == len(POLLUTANTS)
                run_id = record_air_run(
                    conn,
                    run_at=run_at,
                    lead_hours=LEAD_HOURS,
                    imports=imports,
                    complete=complete,
                )
                if complete:
                    publish_run(conn, run_id)

                counters.records_read = len(POLLUTANTS)
                counters.records_inserted = len(imports)
                counters.artifact_path = imports[-1].object_path if imports else None
                counters.checksum = imports[-1].checksum if imports else None
                counters.source_data_at = run_at
                counters.metrics = {
                    "leads": [min(LEAD_HOURS), max(LEAD_HOURS)],
                    "pollutants": [item.pollutant for item in imports],
                    "published": complete,
                }

                print(
                    f"\nregistre : air.model_runs {run_id} "
                    f"({'publié' if complete else 'partiel, non publié'})"
                )
        except CamsAuthError as exc:
            print(f"échec d'authentification : {exc}")
            return 1
        except (CamsError, ImportRunError) as exc:
            print(f"échec : {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
