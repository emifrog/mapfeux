"""Importe les régions et départements dans le référentiel des territoires.

Usage :
    micromamba run -n mapfeux-geo python scripts/import-territories.py

Référence : cahier §13.1, FR-014 et §16.7 ; ADR-017 pour la source.

À lancer **après** l'import des communes : les géométries des territoires sont
construites par union des limites communales, jamais téléchargées — une seule
source de vérité géométrique. Les territoires nouveaux naissent en `draft`,
invisibles du public (FR-014) ; ouvrir un territoire reste une décision, pas
un effet de bord d'import. Les territoires existants gardent statut, slug,
centre et zoom.
"""

from __future__ import annotations

import pathlib
import sys

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file
from geo_worker.pipelines.import_run import import_run
from geo_worker.pipelines.territories import import_departments, import_regions
from geo_worker.providers.admin_boundaries import PROVIDER_KEY, AdminBoundariesProvider

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"


def main(argv: list[str]) -> int:
    with (
        psycopg.connect(dsn_from_env_file(ENV_FILE), connect_timeout=30) as conn,
        httpx.Client() as client,
    ):
        # L'union des communes d'un gros département dépasse le temps de
        # requête par défaut du projet. Réglage de session uniquement.
        conn.execute("set statement_timeout = '5min'")

        provider = AdminBoundariesProvider(client)

        with import_run(conn, source_key=PROVIDER_KEY, job_name="territories") as counters:
            regions, region_rejections = provider.fetch_regions()
            departments, department_rejections = provider.fetch_departments()
            rejections = region_rejections + department_rejections
            for rejection in rejections[:5]:
                print(f"  rejet : {rejection}")

            print(f"{len(departments)} départements, {len(regions)} régions à traiter…\n")

            dep = import_departments(conn, departments)
            print(
                f"départements : {dep.created} créés, {dep.updated} mis à jour, "
                f"{dep.geometry_missing} sans commune importée"
            )

            reg = import_regions(conn, regions, departments)
            print(
                f"régions      : {reg.created} créées, {reg.updated} mises à jour "
                f"(les régions sans département métropolitain attendent la vague B)"
            )

            counters.records_read = len(departments) + len(regions) + len(rejections)
            counters.records_inserted = dep.created + reg.created
            counters.records_updated = dep.updated + reg.updated
            counters.records_rejected = len(rejections) + dep.geometry_missing
            counters.metrics = {
                "departements": dep.created + dep.updated,
                "regions": reg.created + reg.updated,
                "sans_communes": dep.geometry_missing,
            }

    # Un département sans commune n'est pas un succès silencieux.
    return 1 if dep.geometry_missing > 0 or rejections else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
