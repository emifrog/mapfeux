"""Réconciliation trimestrielle NRT/standard des détections FIRMS.

Référence : cahier v2.1 §16.3 et FR-032 ; plan J10.

FIRMS republie ses détections en qualité scientifique standard (`*_SP`)
avec environ cinq mois de décalage, et **rogne lui-même le NRT** à mesure
que le standard avance — les bornes, lues de l'API de disponibilité, sont
exactement contiguës (constaté le 26 août : N20 SP jusqu'au 31 mai, N20
NRT depuis le 1ᵉʳ juin). La tâche relit le standard sur la fenêtre où il
recouvre la base, rapproche par **clé spatiotemporelle** — satellite,
horodatage, coordonnées à cinq décimales, la clé naturelle du corpus — et
enrichit les lignes appariées : `thermal_type` (le vrai `type` FIRMS, que
le flux NRT ne porte pas), la ligne standard complète en
`standard_payload`, l'horodatage en `reconciled_at`.

Ce que la réconciliation ne fait **pas**, et pourquoi :
- elle ne touche jamais `provider_key` — la version fait partie du hash
  (« 2.0NRT » côté flux, « 2 » côté standard, testé comme distinct dans
  `test_corpus_import`) : le rapprochement passe par la clé naturelle,
  l'identité des lignes ne bouge pas ;
- elle ne réécrit jamais `raw_payload` ni les grandeurs mesurées — le §16.3
  parle d'enrichissements, l'ADR-004 rend le brut immuable ;
- elle n'insère pas les lignes standard sans correspondance (v1) : la base
  de mai-juillet est volontairement pilote 06/83 quand le standard est
  national — insérer créerait rétroactivement des événements d'archive
  hors périmètre. Les non-appariées sont **comptées et rendues**, jamais
  tues ; l'insertion se décidera quand la fenêtre nationale recouvrira.

`reconciled_at` est le verrou d'idempotence : rejouer un trimestre déjà
traité ne met à jour aucune ligne — le critère de sortie de J10.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg

from geo_worker.logging import get_logger
from geo_worker.providers.firms import MAX_DAY_RANGE
from geo_worker.providers.models import ThermalDetection

logger = get_logger(__name__)

#: Produit standard par valeur de `satellite` en base. MODIS partage un
#: produit pour ses deux satellites ; N21 n'a pas de produit standard chez
#: FIRMS à ce jour — la disponibilité, lue à chaque passe, fait foi.
STANDARD_PRODUCTS: dict[str, str] = {
    "N20": "VIIRS_NOAA20_SP",
    "N": "VIIRS_SNPP_SP",
    "N21": "VIIRS_NOAA21_SP",
    "Terra": "MODIS_SP",
    "Aqua": "MODIS_SP",
}

AVAILABILITY_PATH = "api/data_availability/csv/{map_key}/ALL"


def parse_availability(payload: str) -> dict[str, tuple[date, date]]:
    """Bornes min/max par produit, depuis le CSV de disponibilité FIRMS."""
    availability: dict[str, tuple[date, date]] = {}
    for row in csv.DictReader(io.StringIO(payload)):
        data_id = (row.get("data_id") or "").strip()
        try:
            first = date.fromisoformat((row.get("min_date") or "").strip())
            last = date.fromisoformat((row.get("max_date") or "").strip())
        except ValueError:
            continue
        if data_id:
            availability[data_id] = (first, last)
    return availability


def fetch_windows(start: date, end: date, max_days: int = MAX_DAY_RANGE) -> list[tuple[date, int]]:
    """Découpe [start, end] inclus en fenêtres (départ, nombre de jours).

    L'API Area plafonne à cinq jours par requête ; la dernière fenêtre
    porte le reliquat exact plutôt que de déborder la borne standard.
    """
    if end < start:
        return []
    windows: list[tuple[date, int]] = []
    cursor = start
    while cursor <= end:
        span = min(max_days, (end - cursor).days + 1)
        windows.append((cursor, span))
        cursor += timedelta(days=span)
    return windows


@dataclass(frozen=True)
class ProductPlan:
    """La fenêtre réconciliable d'un produit standard."""

    product: str
    satellites: tuple[str, ...]
    start: date
    end: date

    @property
    def windows(self) -> list[tuple[date, int]]:
        return fetch_windows(self.start, self.end)


def plan_reconciliation(
    availability: dict[str, tuple[date, date]],
    base_ranges: dict[str, tuple[datetime, datetime]],
) -> tuple[list[ProductPlan], list[str]]:
    """Croise la disponibilité standard et la base : quoi relire, et pourquoi pas.

    Un produit n'entre au plan que si sa fenêtre standard recouvre des
    lignes en base ; le reste est **dit**, pas ignoré — un satellite sans
    produit standard (N21) ou un standard encore trop court est un fait
    d'exploitation, pas un silence.
    """
    plans: list[ProductPlan] = []
    skipped: list[str] = []

    by_product: dict[str, list[str]] = {}
    for satellite in sorted(base_ranges):
        product = STANDARD_PRODUCTS.get(satellite)
        if product is None:
            skipped.append(f"{satellite} : satellite hors correspondance standard")
            continue
        by_product.setdefault(product, []).append(satellite)

    for product, satellites in sorted(by_product.items()):
        window = availability.get(product)
        if window is None:
            skipped.append(f"{product} : aucun produit standard chez FIRMS")
            continue
        _, sp_last = window
        base_first = min(base_ranges[s][0] for s in satellites).date()
        base_last = max(base_ranges[s][1] for s in satellites).date()
        start = base_first
        end = min(base_last, sp_last)
        if end < start:
            skipped.append(
                f"{product} : standard jusqu'au {sp_last}, base à partir du {base_first}"
            )
            continue
        plans.append(
            ProductPlan(product=product, satellites=tuple(satellites), start=start, end=end)
        )

    return plans, skipped


@dataclass(frozen=True)
class ReconcileResult:
    """Ce qu'une passe de réconciliation a fait — et n'a pas fait."""

    read: int
    updated: int
    already_reconciled: int
    unmatched: int


def reconcile_standard(
    conn: psycopg.Connection[Any],
    detections: list[ThermalDetection],
    *,
    now: datetime | None = None,
) -> ReconcileResult:
    """Enrichit les lignes de la base appariées aux détections standard.

    Liste blanche du §17.1, explicite : `thermal_type`, `standard_payload`,
    `reconciled_at` — rien d'autre. La garde `reconciled_at is null` rend
    le rejeu inerte : une ligne déjà enrichie ne l'est jamais deux fois.
    """
    if not detections:
        return ReconcileResult(read=0, updated=0, already_reconciled=0, unmatched=0)
    stamp = now or datetime.now(UTC)

    with conn.cursor() as cur:
        cur.execute(
            """
            create temp table staging_standard (
              satellite text not null,
              acquired_at timestamptz not null,
              lat5 numeric not null,
              lon5 numeric not null,
              thermal_type text,
              payload jsonb not null
            ) on commit drop
            """
        )
        cur.executemany(
            """
            insert into staging_standard
              (satellite, acquired_at, lat5, lon5, thermal_type, payload)
            values (%s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    item.satellite,
                    item.acquired_at,
                    f"{item.latitude:.5f}",
                    f"{item.longitude:.5f}",
                    item.thermal_type,
                    json.dumps(item.raw_payload, ensure_ascii=False),
                )
                for item in detections
            ],
        )

        cur.execute(
            """
            select
              count(*) filter (where d.id is not null) as matched,
              count(*) filter (where d.reconciled_at is not null) as already
            from staging_standard s
            left join fire.detections d
              on d.satellite = s.satellite
             and d.acquired_at = s.acquired_at
             and round(d.latitude::numeric, 5) = s.lat5
             and round(d.longitude::numeric, 5) = s.lon5
            """
        )
        counted = cur.fetchone()
        assert counted is not None  # un agrégat rend toujours une ligne
        matched, already = int(counted[0]), int(counted[1])

        cur.execute(
            """
            update fire.detections d
            set thermal_type = s.thermal_type,
                standard_payload = s.payload,
                reconciled_at = %(stamp)s
            from staging_standard s
            where d.satellite = s.satellite
              and d.acquired_at = s.acquired_at
              and round(d.latitude::numeric, 5) = s.lat5
              and round(d.longitude::numeric, 5) = s.lon5
              and d.reconciled_at is null
            """,
            {"stamp": stamp},
        )
        updated = cur.rowcount

        cur.execute("drop table staging_standard")

    result = ReconcileResult(
        read=len(detections),
        updated=updated,
        already_reconciled=already,
        unmatched=len(detections) - matched,
    )
    logger.info(
        "reconciliation.applied",
        read=result.read,
        updated=result.updated,
        already=result.already_reconciled,
        unmatched=result.unmatched,
    )
    return result


__all__ = [
    "AVAILABILITY_PATH",
    "STANDARD_PRODUCTS",
    "ProductPlan",
    "ReconcileResult",
    "fetch_windows",
    "parse_availability",
    "plan_reconciliation",
    "reconcile_standard",
]
