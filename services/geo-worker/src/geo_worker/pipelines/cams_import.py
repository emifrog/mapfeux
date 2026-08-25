"""Import d'un run CAMS Europe — `air.model_runs` et `air.grid_assets`.

Référence : cahier v2.1 §16.5 et §13.17 ; plan J9.

Un run par jour, deux polluants (FR-120), un fichier NetCDF chacun : le brut
est déposé, enregistré au registre du schéma `air` — mêmes règles de fusion
que le registre météo, ce sont les mêmes fonctions — puis la **publication
bascule atomiquement** : `is_current` passe de l'ancien run au nouveau dans
une transaction, et l'ancien reste entier, fichiers compris (§16.5,
« conservation de la version précédente »). Un import à moitié réussi ne
publie rien : le run précédent continue de servir.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import psycopg

from geo_worker.logging import get_logger
from geo_worker.pipelines.meteo_runs import merge_files, merge_leads
from geo_worker.providers.cams import (
    EXTENT,
    MODEL,
    RESOLUTION,
    UNIT,
    CamsRequest,
    retrieve,
)
from geo_worker.storage import upload_object

logger = get_logger(__name__)

PROVIDER = "copernicus-ads"
AIR_MODEL = f"cams-europe-{MODEL}"


@dataclass(frozen=True)
class PollutantImport:
    """Ce qu'un polluant importé laisse derrière lui."""

    pollutant: str
    object_path: str
    checksum: str
    source_bytes: int
    stored_bytes: int


def unwrap_netcdf(payload: bytes) -> bytes:
    """Le NetCDF, que l'ADS l'ait servi nu ou dans un zip.

    Le format `netcdf_zip` enveloppe un unique membre ; on stocke le NetCDF
    lui-même (§16.5, « stockage NetCDF/GRIB »), pas son emballage de
    transport.
    """
    if not payload.startswith(b"PK"):
        return payload
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [name for name in archive.namelist() if name.endswith(".nc")]
        if len(members) != 1:
            raise ValueError(f"Zip ADS inattendu : {len(members)} NetCDF au lieu d'un.")
        return archive.read(members[0])


def import_pollutant(
    http: httpx.Client,
    *,
    base_url: str,
    token: str,
    request: CamsRequest,
    supabase_url: str,
    secret_key: str,
    bucket: str,
) -> PollutantImport:
    """Récupère un polluant du run et dépose son brut, empreinte rendue."""
    payload = retrieve(http, base_url=base_url, token=token, request=request)
    netcdf = unwrap_netcdf(payload)
    checksum = upload_object(
        http,
        supabase_url=supabase_url,
        secret_key=secret_key,
        bucket=bucket,
        object_path=request.object_path,
        payload=netcdf,
    )
    logger.info(
        "cams.imported",
        pollutant=request.pollutant,
        object_path=request.object_path,
        stored_mo=round(len(netcdf) / 1e6, 2),
    )
    return PollutantImport(
        pollutant=request.pollutant,
        object_path=f"{bucket}/{request.object_path}",
        checksum=checksum,
        source_bytes=len(payload),
        stored_bytes=len(netcdf),
    )


def record_air_run(
    conn: psycopg.Connection[Any],
    *,
    run_at: datetime,
    lead_hours: tuple[int, ...],
    imports: list[PollutantImport],
    complete: bool,
) -> UUID:
    """Enregistre (ou enrichit) le run au registre du schéma `air`.

    Même contrat que le registre météo : les échéances s'unissent,
    l'inventaire des fichiers se fusionne par chemin, le rejeu est anodin.
    """
    leads = merge_leads([], lead_hours)
    entries = [
        {
            "path": item.object_path,
            "checksum": item.checksum,
            "pollutant": item.pollutant,
            "leads": leads,
        }
        for item in imports
    ]

    with conn.cursor() as cur:
        cur.execute(
            """
            select id, available_leads, metadata
            from air.model_runs
            where provider = %(provider)s and model = %(model)s and run_at = %(run_at)s
            for update
            """,
            {"provider": PROVIDER, "model": AIR_MODEL, "run_at": run_at},
        )
        row = cur.fetchone()

        status = "complete" if complete else "partial"
        if row is None:
            cur.execute(
                """
                insert into air.model_runs
                  (provider, model, run_at, domain, resolution, available_leads,
                   import_status, metadata)
                values
                  (%(provider)s, %(model)s, %(run_at)s, %(domain)s, %(resolution)s,
                   %(leads)s, %(status)s, %(metadata)s)
                returning id
                """,
                {
                    "provider": PROVIDER,
                    "model": AIR_MODEL,
                    "run_at": run_at,
                    "domain": EXTENT.as_firms_area(),
                    "resolution": RESOLUTION,
                    "leads": leads,
                    "status": status,
                    "metadata": json.dumps({"files": entries}, ensure_ascii=False),
                },
            )
            inserted = cur.fetchone()
            assert inserted is not None  # returning sur insert : toujours une ligne
            run_id = UUID(str(inserted[0]))
        else:
            run_id, existing_leads, metadata = UUID(str(row[0])), list(row[1]), dict(row[2])
            files = list(metadata.get("files", []))
            for entry in entries:
                files = merge_files(files, entry)
            metadata["files"] = files
            cur.execute(
                """
                update air.model_runs
                set available_leads = %(leads)s,
                    import_status = %(status)s,
                    metadata = %(metadata)s
                where id = %(run_id)s
                """,
                {
                    "run_id": run_id,
                    "leads": merge_leads(existing_leads, lead_hours),
                    "status": status,
                    "metadata": json.dumps(metadata, ensure_ascii=False),
                },
            )

        # Le brut d'un polluant est un seul fichier couvrant toutes les
        # échéances : une ligne d'actif à l'échéance zéro, l'inventaire des
        # heures en métadonnées. Les COG et tuiles auront, eux, une ligne
        # par échéance (§19.1) — c'est là que `lead_hours` prendra son sens.
        for item in imports:
            cur.execute(
                """
                insert into air.grid_assets
                  (model_run_id, pollutant, unit, lead_hours, valid_at, kind,
                   extent, resolution, asset_path, checksum, metadata)
                values
                  (%(run_id)s, %(pollutant)s, %(unit)s, 0, %(run_at)s, 'raw',
                   %(extent)s, %(resolution)s, %(path)s, %(checksum)s, %(metadata)s)
                on conflict (model_run_id, pollutant, kind, lead_hours) do update set
                  asset_path = excluded.asset_path,
                  checksum = excluded.checksum,
                  metadata = excluded.metadata
                """,
                {
                    "run_id": run_id,
                    "pollutant": item.pollutant,
                    "unit": UNIT,
                    "run_at": run_at,
                    "extent": EXTENT.as_firms_area(),
                    "resolution": RESOLUTION,
                    "path": item.object_path,
                    "checksum": item.checksum,
                    "metadata": json.dumps({"leads": leads}, ensure_ascii=False),
                },
            )

    return run_id


def publish_run(conn: psycopg.Connection[Any], run_id: UUID) -> None:
    """Bascule la publication vers ce run — atomique, l'ancien survit.

    À n'appeler que sur un run **complet** : publier un run partiel ferait
    disparaître un polluant que le run précédent servait encore.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            update air.model_runs
            set is_current = false
            where model = %(model)s and is_current and id <> %(run_id)s
            """,
            {"model": AIR_MODEL, "run_id": run_id},
        )
        cur.execute(
            "update air.model_runs set is_current = true where id = %(run_id)s",
            {"run_id": run_id},
        )
    logger.info("cams.published", run_id=str(run_id))


def default_run_at(now: datetime) -> datetime:
    """Le run du jour à 00 UTC — ou celui de la veille avant la publication.

    Le produit paraît en cours de matinée ; avant huit heures, demander le
    run du jour ne rendrait rien.
    """
    utc = now.astimezone(UTC)
    base = utc.replace(hour=0, minute=0, second=0, microsecond=0)
    if utc.hour < 8:
        base -= timedelta(days=1)
    return base


__all__ = [
    "AIR_MODEL",
    "PROVIDER",
    "PollutantImport",
    "default_run_at",
    "import_pollutant",
    "publish_run",
    "record_air_run",
    "unwrap_netcdf",
]
