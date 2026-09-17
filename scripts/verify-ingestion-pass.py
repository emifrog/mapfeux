"""Une passe complete sous le role d'ingestion, sur une base vierge : la CI la rejoue.

Plan §15, audit du 15 septembre 2026, constat 5. La CI rejouait les
migrations et verifiait les droits de tables ; elle ne faisait jamais tourner
la chaine sous le role qui l'execute. Le 15 septembre au soir, la bascule du
poste sur `mapfeux_ingest` a trouve, avant de casser, un declencheur du jour
qui lisait `app.territories` sous le role de l'appelant — une table que ce
role n'a pas le droit de lire : chaque regroupement aurait echoue en
« permission denied » (50e migration). Ce script est le test qui l'aurait vu.

Ce qu'il fait, dans l'ordre de `run-ingestion.py` : verrou d'execution,
enregistrement de passe (`ingest.import_runs`), insertion de detections
(`fire.detections`, partition creee a la volee), classement des sources
connues, regroupement, cycle de vie de la fraicheur, snapshots, coherence.
Sous `mapfeux_ingest` seul — ses vingt tables et rien de plus : la moindre
lecture hors de ses droits fait echouer la passe ici, avant la production.

Puis ce que la passe doit avoir produit, lu sous le meme role : deux
evenements. L'un dans le Var, trois pixels a la meme minute — dans le
perimetre, publie. L'autre en Belgique, un pixel — hors perimetre, masque par
le declencheur (ADR-027), jamais publie.

Usage (CI) :
    DATABASE_URL=postgresql://mapfeux_ingest:...@localhost:5432/postgres \
        python scripts/verify-ingestion-pass.py

Le script refuse de tourner sous un autre role que `mapfeux_ingest` : sous
`postgres`, il ne prouverait rien.
"""

from __future__ import annotations

import os
import pathlib
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import exclusive_run, normalise_dsn
from geo_worker.pipelines.clustering import ClusteringResult, cluster_detections
from geo_worker.pipelines.detections import (
    insert_detections,
    mark_known_thermal_sources,
)
from geo_worker.pipelines.import_run import import_run
from geo_worker.providers.models import ThermalDetection

ROLE = "mapfeux_ingest"


def pixel(
    key: str, longitude: float, latitude: float, frp_mw: float, at: datetime
) -> ThermalDetection:
    return ThermalDetection(
        provider_key=f"ci:{key}",
        sensor="VIIRS",
        satellite="N20",
        product_version="ci",
        acquired_at=at,
        latitude=latitude,
        longitude=longitude,
        confidence_raw="n",
        confidence_score=0.8,
        frp_mw=frp_mw,
        brightness=330.0,
        day_night="D",
        scan_km=0.4,
        track_km=0.4,
        thermal_type=None,
        raw_payload={"ci": key},
    )


def fixtures(now: datetime) -> list[ThermalDetection]:
    """Trois pixels a Ponteves, dans le Var ; un a Gand, en Belgique. Il y a deux heures."""
    at = now.replace(second=0, microsecond=0) - timedelta(hours=2)
    return [
        pixel("var-1", 6.060, 43.550, 12.0, at),
        pixel("var-2", 6.064, 43.552, 8.5, at),
        pixel("var-3", 6.058, 43.554, 5.0, at),
        pixel("belgique", 3.720, 51.050, 20.0, at),
    ]


def run_pass(conn: psycopg.Connection[Any], now: datetime) -> ClusteringResult:
    """La passe de `run-ingestion.py`, avec des pixels de test a la place de FIRMS."""
    with exclusive_run(conn, "ingestion") as acquired:
        if not acquired:
            raise RuntimeError("le verrou d'ingestion est pris : une autre passe tourne")

        with import_run(conn, source_key="firms", job_name="ci:passe-sous-role") as counters:
            detections = fixtures(now)
            inserted = insert_detections(
                conn, detections=detections, source_key="firms", import_run_id=None
            )
            conn.commit()
            counters.records_read = len(detections)
            counters.records_inserted = inserted.inserted
        print(f"import      : {inserted.inserted} detection(s)", flush=True)

        classified = mark_known_thermal_sources(conn)
        conn.commit()
        print(f"sources connues : {classified} rattachee(s)", flush=True)

        result = ClusteringResult()
        while True:
            current = cluster_detections(conn)
            conn.commit()
            result.created += current.created
            result.attached += current.attached
            result.touched_events |= current.touched_events
            if not current.truncated or current.processed == 0:
                break
        print(
            f"regroupement: {result.created} evenement(s) cree(s), "
            f"{result.attached} rattachement(s)",
            flush=True,
        )

        with conn.cursor() as cur:
            cur.execute("select fire.refresh_freshness()")
            requalified = {str(row[0]) for row in cur.fetchall()}
            conn.commit()
        refreshed = 0
        with conn.cursor() as cur:
            for event_id in sorted(result.touched_events | requalified):
                cur.execute("select fire.refresh_event_snapshot(%s)", (event_id,))
                if cur.fetchone() is not None:
                    refreshed += 1
            conn.commit()
        print(f"snapshots   : {refreshed} reconstruit(s)", flush=True)

        with conn.cursor() as cur:
            cur.execute("select public_id from fire.flag_official_status_divergences()")
            cur.fetchall()
            conn.commit()
    return result


def verify(conn: psycopg.Connection[Any], result: ClusteringResult) -> list[str]:
    """Ce que la passe doit avoir laisse en base. Retourne les manquements."""
    faults: list[str] = []
    if result.created != 2:
        faults.append(f"{result.created} evenement(s) cree(s), 2 attendus")
    if result.attached != 4:
        faults.append(f"{result.attached} rattachement(s), 4 attendus")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select e.public_id, e.in_territory, e.freshness_status,
                   (select count(*) from fire.event_detections ed where ed.event_id = e.id)
                     as members
            from fire.events e
            order by e.in_territory desc, e.public_id
            """
        )
        events = cur.fetchall()

    for event in events:
        print(
            f"evenement   : {event['public_id']} — dans le perimetre : {event['in_territory']}, "
            f"fraicheur : {event['freshness_status']}, membres : {event['members']}",
            flush=True,
        )
    if len(events) != 2:
        faults.append(f"{len(events)} evenement(s) en base, 2 attendus")
        return faults

    var, belgique = events
    if not var["in_territory"] or var["members"] != 3 or var["freshness_status"] == "hidden":
        faults.append("l'evenement du Var devrait etre dans le perimetre, publie, a trois pixels")
    if belgique["in_territory"] or belgique["members"] != 1:
        faults.append("l'evenement de Belgique devrait etre hors perimetre, a un pixel")
    if belgique["freshness_status"] != "hidden":
        faults.append(
            "l'evenement de Belgique devrait etre masque par le declencheur de perimetre "
            f"(ADR-027), il est « {belgique['freshness_status']} »"
        )
    return faults


def main() -> int:
    raw = os.environ.get("DATABASE_URL", "")
    if raw == "":
        print("DATABASE_URL absente : passer la chaine du role d'ingestion.", file=sys.stderr)
        return 2
    now = datetime.now(UTC)

    with psycopg.connect(normalise_dsn(raw), connect_timeout=30) as conn:
        with conn.cursor() as cur:
            cur.execute("select current_user")
            row = cur.fetchone()
        user = "" if row is None else str(row[0])
        if user != ROLE:
            print(
                f"role courant : {user} — ce test ne prouve rien hors de {ROLE}.", file=sys.stderr
            )
            return 2
        print(f"role        : {user}", flush=True)

        result = run_pass(conn, now)
        faults = verify(conn, result)

    if faults:
        for fault in faults:
            print(f"MANQUE      : {fault}", file=sys.stderr)
        return 1
    print("La passe tient sous le role d'ingestion, et le perimetre aussi.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
