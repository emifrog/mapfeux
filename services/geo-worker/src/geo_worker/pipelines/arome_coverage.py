"""Couverture du vent sur une fenêtre — ingestion à la demande des tranches.

Référence : cahier v2.1 §16.4 (« extraction à la demande autour des
événements », « recalcul des panaches concernés ») ; plan J8.

L'archivage quotidien capte une tranche par jour — la mi-journée, pour le
FWI. Le panache, lui, a besoin du vent sur l'horizon réel d'un événement :
six à douze heures à partir de sa dernière observation, qui tombent rarement
dans la tranche archivée. Ce module répond à la question laissée ouverte le
18 août : quelles échéances faut-il pour cette fenêtre, quelles tranches les
portent, lesquelles manquent au registre — et il va chercher les manquantes
au dépôt tant qu'il les sert encore.

Chaque tranche récupérée suit le chemin de l'archivage nominal : extraction
des champs FWI sur l'emprise nationale, dépôt au froid, passe consignée au
journal (`arome:panache:<tranche>`), registre enrichi par fusion. Le corpus
y gagne ce que le panache exige : rien n'est jeté après calcul.

La lecture assemble ensuite les fichiers du run couvrant la fenêtre en un
seul jeu, trié par échéance — les tranches ne se recouvrent pas, la couture
est exacte.
"""

from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import numpy as np
import psycopg
import xarray as xr

from geo_worker.logging import get_logger
from geo_worker.pipelines.arome_archive import archive_package
from geo_worker.pipelines.import_run import import_run
from geo_worker.pipelines.meteo_runs import record_model_run, span_leads
from geo_worker.providers.arome import (
    ARCHIVE_EXTENT,
    RESOLUTION,
    PackageRef,
    PackageUnavailableError,
    span_for_lead_time,
)
from geo_worker.storage import download_object

logger = get_logger(__name__)

SOURCE_KEY = "arome"

#: Portée du modèle : au-delà, aucune tranche n'existe.
MAX_LEAD_HOURS = 48


@dataclass(frozen=True)
class WindowCoverage:
    """Ce que le registre détient du run pour la fenêtre demandée."""

    run_at: datetime
    needed_spans: tuple[str, ...]
    fetched_spans: tuple[str, ...]
    unavailable_spans: tuple[str, ...]
    #: Inventaire des fichiers du run dont les échéances croisent la fenêtre —
    #: entrées de `metadata.files` : chemin, empreinte, échéances.
    files: tuple[dict[str, Any], ...]

    @property
    def has_start(self) -> bool:
        """La fenêtre peut au moins commencer : son premier pas a du vent."""
        return len(self.files) > 0


def window_leads(run_at: datetime, start: datetime, end: datetime) -> tuple[int, ...]:
    """Échéances horaires nécessaires pour couvrir [start, end] depuis un run.

    Bornées à la portée du modèle : une fenêtre qui déborde 48 h est couverte
    jusqu'à 48 h — le panache dira sa troncature, comme toujours. Vide si la
    fenêtre est entièrement hors de portée, ou antérieure au run.
    """
    if end < start:
        return ()
    first_h = (start - run_at).total_seconds() / 3600.0
    last_h = (end - run_at).total_seconds() / 3600.0
    if last_h < 0 or first_h > MAX_LEAD_HOURS:
        return ()
    first = max(math.floor(first_h), 0)
    last = min(math.ceil(last_h), MAX_LEAD_HOURS)
    return tuple(range(first, last + 1))


def spans_for_leads(leads: tuple[int, ...]) -> tuple[str, ...]:
    """Tranches portant ces échéances, dans l'ordre, sans doublon."""
    spans: list[str] = []
    for lead in leads:
        span = span_for_lead_time(lead)
        if span not in spans:
            spans.append(span)
    return tuple(spans)


def missing_spans(spans: tuple[str, ...], available_leads: list[int]) -> tuple[str, ...]:
    """Tranches dont au moins une échéance manque au registre.

    Une tranche se dépose entière : si une seule de ses échéances manque,
    c'est que le fichier n'y est pas — on la compte manquante en bloc.
    """
    held = set(available_leads)
    return tuple(span for span in spans if not set(span_leads(span)) <= held)


def ensure_window_coverage(
    conn: psycopg.Connection[Any],
    http: httpx.Client,
    *,
    run_at: datetime,
    start: datetime,
    end: datetime,
    supabase_url: str,
    secret_key: str,
    bucket: str,
) -> WindowCoverage:
    """Complète le registre pour couvrir [start, end] depuis ce run.

    Idempotente : les tranches déjà détenues ne déclenchent aucun appel ; une
    tranche absente du dépôt est signalée, jamais inventée. La disponibilité
    est sondée par HEAD avant d'ouvrir une passe — un dépôt qui a expiré le
    run est un état normal, pas une passe échouée à journaliser.
    """
    leads = window_leads(run_at, start, end)
    spans = spans_for_leads(leads)
    if not spans:
        return WindowCoverage(run_at, (), (), (), ())

    row = conn.execute(
        """
        select available_leads
        from meteo.model_runs
        where provider = 'meteo-france' and model = 'arome' and run_at = %(run_at)s
        """,
        {"run_at": run_at},
    ).fetchone()
    available: list[int] = [] if row is None else list(row[0])

    fetched: list[str] = []
    unavailable: list[str] = []
    for span in missing_spans(spans, available):
        reference = PackageRef(run=run_at, span=span)
        probe = http.head(reference.url, timeout=60)
        if probe.status_code == 404:
            unavailable.append(span)
            continue

        try:
            with import_run(
                conn, source_key=SOURCE_KEY, job_name=f"arome:panache:{span}"
            ) as counters:
                result = archive_package(
                    http,
                    reference=reference,
                    extent=ARCHIVE_EXTENT,
                    # L'échéance visée est la première utile de la tranche
                    # pour cette fenêtre — informatif, le fichier porte de
                    # toute façon la tranche entière.
                    lead_hours=min(lead for lead in leads if span_for_lead_time(lead) == span),
                    supabase_url=supabase_url,
                    secret_key=secret_key,
                    bucket=bucket,
                )
                counters.records_read = 1
                counters.records_inserted = 1
                counters.artifact_path = f"{bucket}/{result.object_path}"
                counters.checksum = result.checksum
                counters.source_data_at = run_at
                counters.metrics = {
                    "source_bytes": result.source_bytes,
                    "archived_bytes": result.archived_bytes,
                    "motif": "panache",
                    "fenetre": [start.isoformat(), end.isoformat()],
                    "fields": list(result.fields),
                }
                record_model_run(
                    conn,
                    run_at=run_at,
                    span=span,
                    object_path=f"{bucket}/{result.object_path}",
                    checksum=result.checksum,
                    fields=list(result.fields),
                    target_lead_hours=None,
                    domain=ARCHIVE_EXTENT.as_firms_area(),
                    resolution=RESOLUTION,
                )
            fetched.append(span)
        except PackageUnavailableError:
            # Retiré entre le sondage et le téléchargement : rare, la passe
            # échouée est au journal, la tranche est dite indisponible.
            unavailable.append(span)

    row = conn.execute(
        """
        select metadata
        from meteo.model_runs
        where provider = 'meteo-france' and model = 'arome' and run_at = %(run_at)s
        """,
        {"run_at": run_at},
    ).fetchone()
    inventory: list[dict[str, Any]] = [] if row is None else list(row[0].get("files", []))
    wanted = set(leads)
    files = tuple(f for f in inventory if wanted & set(f.get("leads", [])))

    coverage = WindowCoverage(
        run_at=run_at,
        needed_spans=spans,
        fetched_spans=tuple(fetched),
        unavailable_spans=tuple(unavailable),
        files=files,
    )
    logger.info(
        "coverage.ensured",
        run_at=run_at.isoformat(),
        needed=list(spans),
        fetched=fetched,
        unavailable=unavailable,
        files=len(files),
    )
    return coverage


def merge_wind_datasets(datasets: list[xr.Dataset]) -> xr.Dataset:
    """Assemble les extraits d'un même run en un seul jeu, trié par échéance.

    Les tranches ne se recouvrent pas ; un même fichier chargé deux fois
    produirait des échéances en double, qu'on dédouble par prudence — la
    première occurrence fait foi.
    """
    if not datasets:
        raise ValueError("Aucun extrait à assembler.")
    merged = xr.concat(datasets, dim="step") if len(datasets) > 1 else datasets[0]
    merged = merged.sortby("step")
    steps = merged["step"].values
    _, first_indices = np.unique(steps, return_index=True)
    if len(first_indices) != len(steps):
        merged = merged.isel(step=np.sort(first_indices))
    return merged


def open_window_dataset(
    http: httpx.Client,
    *,
    files: tuple[dict[str, Any], ...],
    supabase_url: str,
    secret_key: str,
    workspace: pathlib.Path,
) -> xr.Dataset:
    """Relit et assemble les fichiers d'une couverture, empreintes vérifiées.

    Les données sont chargées en mémoire (`load`) : le jeu survit à la
    disparition du répertoire de travail, et quelques dizaines de mégaoctets
    sont le prix normal d'une fenêtre de vent.
    """
    datasets: list[xr.Dataset] = []
    for index, entry in enumerate(files):
        bucket, _, object_path = str(entry["path"]).partition("/")
        payload = download_object(
            http,
            supabase_url=supabase_url,
            secret_key=secret_key,
            bucket=bucket,
            object_path=object_path,
            expected_checksum=entry.get("checksum"),
        )
        local = workspace / f"extract-{index}.nc"
        local.write_bytes(payload)
        with xr.open_dataset(local) as dataset:
            datasets.append(dataset.load())
    return merge_wind_datasets(datasets)


def coverage_checksum(files: tuple[dict[str, Any], ...]) -> str:
    """Empreinte composite des extraits d'une couverture, ordre des échéances.

    Sert d'entrée au versionnement §18.6 quand le vent vient de plusieurs
    fichiers : mêmes fichiers, même empreinte.
    """
    ordered = sorted(files, key=lambda f: min(f.get("leads", [MAX_LEAD_HOURS + 1])))
    return "|".join(str(f.get("checksum")) for f in ordered)


__all__ = [
    "MAX_LEAD_HOURS",
    "WindowCoverage",
    "coverage_checksum",
    "ensure_window_coverage",
    "merge_wind_datasets",
    "missing_spans",
    "open_window_dataset",
    "spans_for_leads",
    "window_leads",
]
