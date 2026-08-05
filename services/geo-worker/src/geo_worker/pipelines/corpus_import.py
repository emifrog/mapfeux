"""Chargement du corpus d'archives FIRMS dans `fire.detections`.

Référence : cahier §16.3 et §16.7 ; stratégie §3.4.

Le corpus de quatorze saisons vit en Parquet ; le banc de calibration lit la
base. Ce module fait le pont, sous trois contraintes.

**La normalisation est celle du flux temps réel, pas une seconde.** Chaque ligne
repasse par `geo_worker.providers.firms.parse_row`, la fonction qu'emploie
l'ingestion de production. Si le corpus était normalisé autrement — ne serait-ce
que par un arrondi de coordonnée ou une table de confiance recopiée — la
calibration porterait sur une donnée que la production ne produit pas, et son
résultat ne serait transposable à rien.

**Le nom de produit reprend celui du flux.** La clé d'idempotence retient le
produit ; donner aux lignes d'archive un nom distinct ferait apparaître deux
fois toute observation présente dans les deux sources. Or la queue NRT du
corpus recouvre exactement la période où l'ingestion tourne déjà. Le corpus
retraité, lui, ne peut pas entrer en collision : FIRMS l'estampille `version 2`
là où le temps réel porte `2.0NRT`, et la version fait partie de la clé.

**L'insertion passe par une table de transit.** Une écriture ligne à ligne
demanderait 337 757 allers-retours ; sur une base hébergée, le réseau à lui seul
en ferait des heures. `COPY` verse le lot d'un trait, puis un unique
`insert … select` construit les géométries et laisse la contrainte
d'idempotence trancher.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg

from geo_worker.logging import get_logger
from geo_worker.providers.firms import FirmsParseError, parse_row
from geo_worker.providers.models import ThermalDetection

logger = get_logger(__name__)

#: Produit FIRMS correspondant à chaque satellite du corpus VIIRS.
#:
#: Ce sont les noms du flux temps réel, délibérément. Voir l'en-tête du module :
#: le produit entre dans la clé d'idempotence, et un nom distinct dédoublerait
#: les observations que le corpus et l'ingestion couvrent tous les deux.
PRODUCT_BY_SATELLITE: dict[str, str] = {
    "N20": "VIIRS_NOAA20_NRT",
    "N21": "VIIRS_NOAA21_NRT",
    "SNPP": "VIIRS_SNPP_NRT",
}

#: Colonnes du corpus transmises telles quelles à l'analyseur FIRMS. Ce sont
#: celles du CSV d'origine : l'analyseur attend un enregistrement CSV, et lui en
#: donner un le fait travailler sur ce qu'il sait lire.
CSV_COLUMNS: tuple[str, ...] = (
    "latitude",
    "longitude",
    "brightness",
    "scan",
    "track",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
    "confidence",
    "version",
    "bright_t31",
    "frp",
    "daynight",
    "type",
)

#: Colonnes de la table de transit, dans l'ordre du `COPY`.
STAGING_COLUMNS: tuple[str, ...] = (
    "provider_key",
    "sensor",
    "satellite",
    "product_version",
    "acquired_at",
    "latitude",
    "longitude",
    "confidence_raw",
    "confidence_score",
    "frp_mw",
    "brightness",
    "day_night",
    "scan_km",
    "track_km",
    "thermal_type",
    "raw_payload",
)

DEFAULT_BATCH = 50_000


class CorpusImportError(RuntimeError):
    """Le corpus ne peut pas être chargé tel quel."""


@dataclass
class CorpusImportResult:
    read: int = 0
    inserted: int = 0
    already_known: int = 0
    rejected: int = 0
    rejections: list[str] = field(default_factory=list)
    months: int = 0
    source_data_at: datetime | None = None

    @property
    def status(self) -> str:
        return "partial" if self.rejected > 0 else "success"


def product_for(satellite: str) -> str:
    """Produit FIRMS d'un satellite du corpus.

    Un satellite inconnu arrête le chargement. Lui inventer un produit
    changerait sa clé d'idempotence sans que rien ne le signale : les mêmes
    observations rentreraient deux fois au prochain import, une fois sous chaque
    nom.
    """
    try:
        return PRODUCT_BY_SATELLITE[satellite]
    except KeyError as exc:
        connus = ", ".join(sorted(PRODUCT_BY_SATELLITE))
        raise CorpusImportError(
            f"Satellite {satellite!r} sans produit FIRMS connu. Connus : {connus}. "
            f"Renseigner PRODUCT_BY_SATELLITE avant de charger le corpus."
        ) from exc


def to_csv_row(record: dict[str, Any]) -> dict[str, str]:
    """Reconstitue l'enregistrement CSV FIRMS attendu par l'analyseur.

    Les valeurs absentes deviennent la chaîne vide, comme dans un CSV : c'est
    ainsi que l'analyseur distingue « non renseigné » d'une valeur nulle.
    """
    row: dict[str, str] = {}
    for column in CSV_COLUMNS:
        value = record.get(column)
        row[column] = "" if value is None else str(value)
    return row


def normalise_records(
    records: Sequence[dict[str, Any]],
) -> tuple[list[ThermalDetection], list[str]]:
    """Normalise un lot du corpus avec l'analyseur du flux temps réel.

    Une ligne inexploitable est comptée et écartée, jamais silencieusement
    corrigée : le corpus sert de référence, et une valeur devinée y aurait le
    même poids qu'une valeur observée.
    """
    detections: list[ThermalDetection] = []
    rejections: list[str] = []

    for position, record in enumerate(records):
        satellite = str(record.get("satellite", "")).strip()
        try:
            detections.append(parse_row(to_csv_row(record), product=product_for(satellite)))
        except FirmsParseError as exc:
            rejections.append(f"ligne {position} ({satellite}) : {exc}")

    return detections, rejections


def ensure_partitions_for_span(
    conn: psycopg.Connection[Any], *, first: datetime, last: datetime
) -> int:
    """Crée les partitions mensuelles couvrant toute la période du corpus.

    Quatorze saisons font environ cent soixante-quinze partitions. Les créer
    d'avance, plutôt qu'au fil des lots, évite de découvrir au milieu du
    chargement qu'un mois manque — et évite surtout la partition par défaut,
    dont ADR-015 explique le coût.
    """
    created = 0
    with conn.cursor() as cur:
        for month in months_between(first, last):
            cur.execute("select fire.ensure_detection_partition(%s)", (month,))
            created += 1
    return created


def months_between(first: datetime, last: datetime) -> Iterator[date]:
    """Premiers jours de chaque mois entre deux instants, bornes incluses."""
    if last < first:
        raise CorpusImportError("La fin du corpus précède son début.")

    month = first.astimezone(UTC).date().replace(day=1)
    end = last.astimezone(UTC).date().replace(day=1)
    while month <= end:
        yield month
        # Le 28 est le seul jour présent dans tous les mois : y ajouter quatre
        # jours tombe toujours dans le mois suivant, février bissextile compris.
        month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)


def _staging_rows(detections: Sequence[ThermalDetection]) -> Iterator[tuple[Any, ...]]:
    for d in detections:
        yield (
            d.provider_key,
            d.sensor,
            d.satellite,
            d.product_version,
            d.acquired_at,
            d.latitude,
            d.longitude,
            d.confidence_raw,
            d.confidence_score,
            d.frp_mw,
            d.brightness,
            d.day_night,
            d.scan_km,
            d.track_km,
            d.thermal_type,
            json.dumps(d.raw_payload, ensure_ascii=False),
        )


def _create_staging(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            create temp table staging_corpus_detections (
              provider_key text not null,
              sensor text not null,
              satellite text not null,
              product_version text,
              acquired_at timestamptz not null,
              latitude double precision not null,
              longitude double precision not null,
              confidence_raw text,
              confidence_score numeric(4, 3),
              frp_mw numeric(10, 3),
              brightness numeric(8, 3),
              day_night char(1),
              scan_km numeric(6, 3),
              track_km numeric(6, 3),
              thermal_type text,
              raw_payload jsonb not null
            ) on commit drop
        """)


def _publish(
    conn: psycopg.Connection[Any], *, source_id: Any, import_run_id: str | None
) -> tuple[int, int]:
    """Verse la table de transit dans `fire.detections`. Retourne (insérées, déjà connues)."""
    with conn.cursor() as cur:
        cur.execute("select count(*) from staging_corpus_detections")
        row = cur.fetchone()
        staged = 0 if row is None else int(row[0])

        cur.execute(
            """
            insert into fire.detections (
              provider_key, source_id, import_run_id, sensor, satellite, product_version,
              acquired_at, location, latitude, longitude,
              confidence_raw, confidence_score, frp_mw, brightness, day_night,
              scan_km, track_km, thermal_type, raw_payload
            )
            select
              s.provider_key, %(source_id)s, %(import_run_id)s, s.sensor, s.satellite,
              s.product_version, s.acquired_at,
              extensions.st_setsrid(extensions.st_makepoint(s.longitude, s.latitude), 4326),
              s.latitude, s.longitude,
              s.confidence_raw, s.confidence_score, s.frp_mw, s.brightness, s.day_night,
              s.scan_km, s.track_km, s.thermal_type, s.raw_payload
            from staging_corpus_detections s
            -- Même règle que l'ingestion : la donnée brute est immuable
            -- (ADR-004), et un réimport ne doit rien écraser des champs
            -- enrichis en aval.
            on conflict (provider_key, acquired_at) do nothing
            """,
            {"source_id": source_id, "import_run_id": import_run_id},
        )
        inserted = cur.rowcount

        cur.execute("truncate staging_corpus_detections")

    return inserted, staged - inserted


def _source_id(conn: psycopg.Connection[Any], source_key: str) -> Any:
    with conn.cursor() as cur:
        cur.execute("select id from ingest.data_sources where key = %s", (source_key,))
        row = cur.fetchone()
    if row is None:
        raise CorpusImportError(
            f"Source inconnue : {source_key}. Les migrations sont-elles appliquées sur cette base ?"
        )
    return row[0]


def import_corpus(
    conn: psycopg.Connection[Any],
    records: Sequence[dict[str, Any]],
    *,
    source_key: str = "firms",
    import_run_id: str | None = None,
    batch_size: int = DEFAULT_BATCH,
    on_progress: Any = None,
) -> CorpusImportResult:
    """Charge le corpus. L'appelant gère la transaction.

    Le lot est découpé pour que la table de transit reste de taille bornée. Le
    découpage n'a pas d'effet sur le résultat : l'idempotence porte sur la clé
    fournisseur, pas sur l'ordre d'arrivée.
    """
    result = CorpusImportResult(read=len(records))
    if not records:
        return result

    detections, rejections = normalise_records(records)
    result.rejected = len(rejections)
    # Les motifs sont bornés : un corpus entièrement mal formé en produirait
    # trois cent mille, et le compte rendu deviendrait illisible.
    result.rejections = rejections[:50]

    if not detections:
        raise CorpusImportError(
            f"Aucune ligne exploitable sur {len(records)} lues. "
            f"Premier motif : {rejections[0] if rejections else 'inconnu'}"
        )

    result.source_data_at = max(d.acquired_at for d in detections)
    result.months = ensure_partitions_for_span(
        conn,
        first=min(d.acquired_at for d in detections),
        last=result.source_data_at,
    )

    source_id = _source_id(conn, source_key)
    _create_staging(conn)

    # Les noms de colonnes sont une constante du module, pas une entrée : rien
    # d'extérieur n'entre dans cette chaîne.
    copy_sql = f"copy staging_corpus_detections ({', '.join(STAGING_COLUMNS)}) from stdin"

    for start in range(0, len(detections), batch_size):
        chunk = detections[start : start + batch_size]
        with conn.cursor() as cur, cur.copy(copy_sql) as copy:
            for row in _staging_rows(chunk):
                copy.write_row(row)

        inserted, known = _publish(conn, source_id=source_id, import_run_id=import_run_id)
        result.inserted += inserted
        result.already_known += known

        if on_progress is not None:
            on_progress(result)

    logger.info(
        "corpus.imported",
        read=result.read,
        inserted=result.inserted,
        already_known=result.already_known,
        rejected=result.rejected,
        months=result.months,
    )
    return result


__all__ = [
    "PRODUCT_BY_SATELLITE",
    "CorpusImportError",
    "CorpusImportResult",
    "ensure_partitions_for_span",
    "import_corpus",
    "months_between",
    "normalise_records",
    "product_for",
    "to_csv_row",
]
