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
from urllib.parse import quote

import httpx
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.pipelines.import_run import ImportRunError, import_run  # noqa: E402
from geo_worker.pipelines.municipalities import import_department  # noqa: E402
from geo_worker.providers.admin_boundaries import (  # noqa: E402
    PROVIDER_KEY,
    AdminBoundariesProvider,
    source_version,
)

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"


def read_dsn() -> str:
    """Lit DATABASE_URL, en réparant un `@` non encodé dans le mot de passe.

    Correctif volontairement étroit : encoder inconditionnellement produirait un
    double encodage sur une chaîne déjà correcte.
    """
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("DATABASE_URL="):
            continue
        dsn = line.split("=", 1)[1].strip()
        scheme, sep, rest = dsn.partition("://")
        if sep == "":
            return dsn
        authority, slash, path = rest.partition("/")
        if authority.count("@") <= 1:
            return dsn
        userinfo, _, hostpart = authority.rpartition("@")
        user, _, password = userinfo.partition(":")
        return f"{scheme}://{user}:{quote(password, safe='')}@{hostpart}{slash}{path}"

    sys.exit(f"DATABASE_URL absente de {ENV_FILE}")


def main(departments: list[str]) -> int:
    if not departments:
        sys.exit("Usage : import-municipalities.py <code département> [...]")

    version = source_version()
    print(f"version enregistrée : {version}\n")

    with psycopg.connect(read_dsn(), connect_timeout=30) as conn, httpx.Client() as client:
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
