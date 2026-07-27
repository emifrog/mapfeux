"""Cycle de vie d'un import.

Référence : cahier §16.1 et §16.2.

Tout pipeline ouvre un `import_run` avant le premier octet téléchargé et le clôt
quoi qu'il arrive. Un import interrompu sans clôture bloquerait l'index partiel
`import_runs_single_running` et ferait apparaître la source comme éternellement
en cours sur la page /statut.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from geo_worker.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ImportCounters:
    """Compteurs remontés à la fin de l'import."""

    records_read: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_rejected: int = 0
    source_data_at: datetime | None = None
    artifact_path: str | None = None
    checksum: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        """`partial` dès qu'une ligne est rejetée : un import n'est pas « réussi »
        s'il a perdu des données en silence."""
        if self.records_rejected > 0:
            return "partial"
        return "success"


class ImportRunError(Exception):
    """Échec global. Porte un code stable réutilisable dans les alertes."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@contextlib.contextmanager
def import_run(
    conn: psycopg.Connection[Any],
    *,
    source_key: str,
    job_name: str,
) -> Iterator[ImportCounters]:
    """Ouvre un `import_run`, le clôt en sortie, y compris en cas d'exception.

    L'ouverture est validée immédiatement : si le processus est tué brutalement,
    la trace de la tentative doit subsister pour l'exploitation.
    """
    counters = ImportCounters()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            insert into ingest.import_runs (source_id, job_name, status)
            select id, %(job_name)s, 'running'
            from ingest.data_sources
            where key = %(source_key)s
            returning id
            """,
            {"source_key": source_key, "job_name": job_name},
        )
        row = cur.fetchone()

    if row is None:
        raise ImportRunError("UNKNOWN_SOURCE", f"Source inconnue : {source_key}")

    run_id: UUID = row["id"]
    conn.commit()

    log = logger.bind(import_run_id=str(run_id), source=source_key, job=job_name)
    log.info("import.started")
    started = datetime.now(UTC)

    try:
        yield counters
    except ImportRunError as exc:
        conn.rollback()
        _close_run(conn, run_id, status="failed", counters=counters, error=(exc.code, str(exc)))
        log.error("import.failed", error_code=exc.code)
        raise
    except Exception as exc:
        conn.rollback()
        _close_run(
            conn,
            run_id,
            status="failed",
            counters=counters,
            error=("UNEXPECTED_ERROR", type(exc).__name__),
        )
        log.exception("import.crashed")
        raise
    else:
        _close_run(conn, run_id, status=counters.status, counters=counters, error=None)
        log.info(
            "import.finished",
            status=counters.status,
            duration_s=round((datetime.now(UTC) - started).total_seconds(), 3),
            records_read=counters.records_read,
            records_inserted=counters.records_inserted,
            records_rejected=counters.records_rejected,
        )


def _close_run(
    conn: psycopg.Connection[Any],
    run_id: UUID,
    *,
    status: str,
    counters: ImportCounters,
    error: tuple[str, str] | None,
) -> None:
    """Clôture idempotente de l'import."""
    with conn.cursor() as cur:
        cur.execute(
            """
            update ingest.import_runs
            set status = %(status)s,
                finished_at = now(),
                source_data_at = %(source_data_at)s,
                records_read = %(records_read)s,
                records_inserted = %(records_inserted)s,
                records_updated = %(records_updated)s,
                records_rejected = %(records_rejected)s,
                artifact_path = %(artifact_path)s,
                checksum = %(checksum)s,
                error_code = %(error_code)s,
                error_summary = %(error_summary)s,
                metrics = %(metrics)s
            where id = %(run_id)s
            """,
            {
                "run_id": run_id,
                "status": status,
                "source_data_at": counters.source_data_at,
                "records_read": counters.records_read,
                "records_inserted": counters.records_inserted,
                "records_updated": counters.records_updated,
                "records_rejected": counters.records_rejected,
                "artifact_path": counters.artifact_path,
                "checksum": counters.checksum,
                "error_code": None if error is None else error[0],
                "error_summary": None if error is None else error[1],
                "metrics": Jsonb(counters.metrics),
            },
        )
    conn.commit()
