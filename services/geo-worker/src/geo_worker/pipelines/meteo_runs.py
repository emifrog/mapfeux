"""Registre des runs de modèle météo — `meteo.model_runs`.

Référence : cahier §13.12 ; plan J8.

Le registre répond à une question que le stockage froid seul laisse ouverte :
« pour tel run, quelles échéances détenons-nous, dans quels fichiers ? ». Le
panache (§18) choisira son run ici, sans lister un compartiment.

Une ligne par (fournisseur, modèle, run). Chaque import **enrichit** la ligne :
les échéances s'unissent, l'inventaire des fichiers s'étend, `source_path` et
`checksum` suivent le dernier dépôt. L'état reste `partial` tant qu'une partie
seulement des échéances du run est détenue — c'est l'état nominal de
l'archivage FWI, une tranche par jour sur les quarante-huit heures du run.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg

#: Nom de fichier d'un extrait archivé :
#: `2026-08-05T150000Z__19H24H__fwi.nc` — l'horodatage du run sans deux-points
#: (Windows les refuse dans un chemin), la tranche, le contenu.
_EXTRACT_NAME = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})T(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})Z"
    r"__(?P<span>\d{2}H\d{2}H)__"
)

_SPAN = re.compile(r"^(?P<first>\d{2})H(?P<last>\d{2})H$")


class MeteoRunError(RuntimeError):
    """Chemin ou tranche impossibles à interpréter — on n'enregistre pas une
    provenance devinée."""


def span_leads(span: str) -> tuple[int, ...]:
    """Échéances horaires couvertes par une tranche : `13H18H` → 13..18.

    L'extraction (`arome_archive.extract`) conserve tous les pas de la
    tranche, pas seulement l'échéance visée — vérifié sur un extrait réel du
    stockage froid, dont `valid_time` porte bien un pas par heure.
    """
    match = _SPAN.match(span)
    if match is None:
        raise MeteoRunError(f"Tranche illisible : {span!r}")
    first, last = int(match["first"]), int(match["last"])
    if last < first:
        raise MeteoRunError(f"Tranche inversée : {span!r}")
    return tuple(range(first, last + 1))


def parse_extract_path(path: str) -> tuple[datetime, str]:
    """Run et tranche portés par le chemin d'un extrait archivé."""
    match = _EXTRACT_NAME.search(path)
    if match is None:
        raise MeteoRunError(f"Chemin d'extrait illisible : {path!r}")
    year, month, day = match["date"].split("-")
    run_at = datetime(
        int(year),
        int(month),
        int(day),
        int(match["hour"]),
        int(match["minute"]),
        int(match["second"]),
        tzinfo=UTC,
    )
    return run_at, match["span"]


def merge_leads(existing: list[int], added: tuple[int, ...] | list[int]) -> list[int]:
    """Union triée : les échéances déjà détenues ne se perdent jamais."""
    return sorted(set(existing) | set(added))


def merge_files(existing: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Inventaire des fichiers, indexé par chemin : redéposer remplace l'entrée.

    Rejouer une passe d'archivage écrase l'objet dans le stockage (`x-upsert`) ;
    l'inventaire suit la même règle, sinon il compterait deux fois un fichier
    qui n'existe qu'une.
    """
    kept = [item for item in existing if item.get("path") != entry["path"]]
    return [*kept, entry]


def record_model_run(
    conn: psycopg.Connection[Any],
    *,
    run_at: datetime,
    span: str,
    object_path: str,
    checksum: str | None,
    fields: list[str],
    target_lead_hours: int | None,
    domain: str,
    resolution: str,
    provider: str = "meteo-france",
    model: str = "arome",
) -> UUID:
    """Enregistre (ou enrichit) le run couvert par un extrait archivé.

    Lecture sous verrou puis écriture : la fusion des échéances et de
    l'inventaire se fait en Python, où elle est testable, plutôt qu'en SQL où
    elle serait un dialecte jsonb illisible. Le verrou rend le rejeu et les
    recouvrements anodins.
    """
    leads = merge_leads([], span_leads(span))
    entry = {
        "path": object_path,
        "checksum": checksum,
        "span": span,
        "leads": leads,
        "fields": fields,
        "target_lead_hours": target_lead_hours,
    }

    with conn.cursor() as cur:
        cur.execute(
            """
            select id, available_leads, metadata
            from meteo.model_runs
            where provider = %(provider)s and model = %(model)s and run_at = %(run_at)s
            for update
            """,
            {"provider": provider, "model": model, "run_at": run_at},
        )
        row = cur.fetchone()

        if row is None:
            cur.execute(
                """
                insert into meteo.model_runs
                  (provider, model, run_at, domain, resolution, available_leads,
                   import_status, source_path, checksum, metadata, fwi_archived)
                values
                  (%(provider)s, %(model)s, %(run_at)s, %(domain)s, %(resolution)s,
                   %(leads)s, 'partial', %(path)s, %(checksum)s, %(metadata)s, true)
                returning id
                """,
                {
                    "provider": provider,
                    "model": model,
                    "run_at": run_at,
                    "domain": domain,
                    "resolution": resolution,
                    "leads": leads,
                    "path": object_path,
                    "checksum": checksum,
                    "metadata": json.dumps({"files": [entry]}, ensure_ascii=False),
                },
            )
            inserted = cur.fetchone()
            assert inserted is not None  # returning sur insert : toujours une ligne
            return UUID(str(inserted[0]))

        run_id, existing_leads, metadata = UUID(str(row[0])), list(row[1]), dict(row[2])
        metadata["files"] = merge_files(list(metadata.get("files", [])), entry)
        cur.execute(
            """
            update meteo.model_runs
            set available_leads = %(leads)s,
                import_status = 'partial',
                source_path = %(path)s,
                checksum = %(checksum)s,
                metadata = %(metadata)s,
                -- Tout extrait enregistré ici est un dépôt FWI en stockage
                -- froid : l'indicateur du §13.12 (v2.1) suit.
                fwi_archived = true
            where id = %(run_id)s
            """,
            {
                "run_id": run_id,
                "leads": merge_leads(existing_leads, leads),
                "path": object_path,
                "checksum": checksum,
                "metadata": json.dumps(metadata, ensure_ascii=False),
            },
        )
        return run_id


__all__ = [
    "MeteoRunError",
    "merge_files",
    "merge_leads",
    "parse_extract_path",
    "record_model_run",
    "span_leads",
]
