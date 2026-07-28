"""Importe les limites communales d'un ou plusieurs départements.

Usage :
    micromamba run -n mapfeux-geo python scripts/import-municipalities.py 06 83

Référence : cahier §16.7 et ADR-017.

L'import est volontairement manuel : le référentiel communal change deux fois
par an, un job récurrent serait du gaspillage et un risque de réécriture
inopinée. Chaque exécution ouvre un `import_run`, visible sur /statut.
"""

from __future__ import annotations

import pathlib
import sys

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file
from geo_worker.pipelines.import_run import ImportRunError, import_run
from geo_worker.pipelines.municipalities import import_department
from geo_worker.providers.admin_boundaries import (
    PROVIDER_KEY,
    AdminBoundariesProvider,
    source_version,
)

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"


def read_dsn() -> str:
    return dsn_from_env_file(ENV_FILE)


def main(departments: list[str]) -> int:
    if not departments:
        sys.exit("Usage : import-municipalities.py <code département> [...]")

    version = source_version()
    print(f"version enregistrée : {version}\n")

    with (
        psycopg.connect(read_dsn(), connect_timeout=30) as conn,
        httpx.Client() as client,
    ):
        provider = AdminBoundariesProvider(client)

        for department in departments:
            with import_run(
                conn, source_key=PROVIDER_KEY, job_name=f"municipalities:{department}"
            ) as counters:
                boundaries, rejections = provider.fetch_municipalities(department, version)
                counters.records_read = len(boundaries) + len(rejections)
                counters.records_rejected = len(rejections)

                for rejection in rejections[:5]:
                    print(f"  rejet : {rejection}")

                if not boundaries:
                    raise ImportRunError(
                        "EMPTY_RESPONSE",
                        f"Aucune commune retournée pour le département {department}",
                    )

                result = import_department(conn, department_code=department, boundaries=boundaries)
                conn.commit()

                counters.records_inserted = result.inserted
                counters.records_updated = result.updated
                counters.records_rejected += result.rejected
                counters.metrics = {
                    "retired": result.retired,
                    "department": department,
                }
                # L'API n'expose pas la date du COG servi : voir ADR-017.
                counters.source_data_at = None

                print(
                    f"{department} : {result.inserted} créées, {result.updated} mises à jour, "
                    f"{result.retired} retirées, {result.rejected} rejetées"
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
