"""Amorce `meteo.model_runs` depuis les passes d'archivage déjà consignées.

Usage :
    micromamba run -n mapfeux-geo python scripts/backfill-meteo-runs.py

Référence : cahier §13.12 ; plan J8.

Le registre des runs est né après les premières passes d'archivage : les
extraits déposés avant lui sont consignés dans `ingest.import_runs` — chemin,
empreinte, échéance visée — mais absents du registre. Ce script les y reporte,
depuis la base seule : le stockage n'est pas relu, la provenance consignée
fait foi.

Rejouable : l'enregistrement est une fusion par (fournisseur, modèle, run), un
extrait déjà connu remplace son entrée d'inventaire au lieu de la dupliquer.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target
from geo_worker.pipelines.meteo_runs import MeteoRunError, parse_extract_path, record_model_run
from geo_worker.providers.arome import ARCHIVE_EXTENT, FWI_FIELDS, RESOLUTION

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"


def main() -> int:
    dsn = dsn_from_env_file(ENV_FILE)
    host, port, database = dsn_target(dsn)
    print(f"cible : {host}:{port}/{database}\n")

    with psycopg.connect(dsn, connect_timeout=30) as conn:
        rows = conn.execute(
            """
            select artifact_path, checksum, metrics
            from ingest.import_runs
            where job_name like 'arome:fwi:%'
              and status = 'success'
              and artifact_path is not null
            order by started_at
            """
        ).fetchall()
        print(f"passes d'archivage consignées : {len(rows)}")

        recorded = 0
        for artifact_path, checksum, metrics in rows:
            try:
                run_at, span = parse_extract_path(artifact_path)
            except MeteoRunError as exc:
                # Un chemin illisible est une anomalie à regarder, pas à
                # enjamber en silence.
                print(f"  ignoré : {exc}")
                continue

            metrics = metrics or {}
            lead: Any = metrics.get("lead_hours")
            fields: Any = metrics.get("fields") or list(FWI_FIELDS)

            run_id = record_model_run(
                conn,
                run_at=run_at,
                span=span,
                object_path=artifact_path,
                checksum=checksum,
                fields=list(fields),
                target_lead_hours=None if lead is None else int(lead),
                domain=ARCHIVE_EXTENT.as_firms_area(),
                resolution=RESOLUTION,
            )
            recorded += 1
            print(f"  {artifact_path} → {run_id}")

        conn.commit()
        print(f"\n{recorded} extrait(s) reporté(s) au registre.")

        state = conn.execute(
            """
            select run_at, available_leads, import_status, source_path
            from meteo.model_runs
            order by run_at
            """
        ).fetchall()
        print(f"registre : {len(state)} run(s)")
        for run_at, leads, status, path in state:
            print(f"  {run_at:%Y-%m-%d %H:%M} UTC  échéances {leads}  {status}  {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
