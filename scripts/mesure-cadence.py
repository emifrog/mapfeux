"""Mesure la cadence réelle des passes d'ingestion, source par source.

Usage :
    micromamba run -n mapfeux-geo python scripts/mesure-cadence.py \\
        [--jours 7] [--depuis ISO] [--source firms]

Référence : plan §15 (« cadence étranglée »), stratégie §8.1, critère de J4.

La cadence **déclarée** est celle du registre des tâches (`ops/tasks.json`) ;
la cadence **réelle** est ce que `ingest.import_runs` a enregistré. La médiane
des écarts entre deux passes réussies dit ce que le déclencheur tient ; les
trous disent quand il ne tenait pas. C'est la mesure faite à la main le
13 septembre 2026 — qui a condamné le cron GitHub Actions — rendue rejouable
pour la remesure promise sous le planificateur Windows, puis sous le VPS.

Une passe peut écrire plusieurs enregistrements — import, regroupement,
instantanés — à quelques secondes d'écart : les départs à moins d'une minute
l'un de l'autre comptent pour une seule passe, sans quoi FIRMS lisait une
médiane de zéro.

Le script lit seulement. Il ne sait rien de la qualité des passes, juste de
leur rythme : une passe « réussie » vide compte comme une passe.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
from datetime import UTC, datetime, timedelta
from itertools import pairwise

import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file, dsn_target

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
TASKS_FILE = ROOT / "ops" / "tasks.json"

# Une tâche du registre lit une source : la clé du registre des sources.
TASK_SOURCE = {
    "ingestion": "firms",
    "radar": "radar",
    "prefectures": "prefectures",
    "vigilance": "vigilance",
    "massifs": "massifs",
    "cams": "cams",
    "arome-archive": "arome",
}

# Deux départs plus proches que cela sont une même passe.
SAME_PASS = timedelta(minutes=1)


def declared_minutes() -> dict[str, int]:
    """Cadence déclarée par source, en minutes, lue dans `ops/tasks.json`."""
    registry = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    declared: dict[str, int] = {}
    for task in registry["tasks"]:
        source = TASK_SOURCE.get(task["unit"])
        if source is None:
            continue
        schedule = task["schedule"]
        declared[source] = int(schedule["minutes"]) if schedule["kind"] == "every" else 1440
    return declared


def collapse(starts: list[datetime]) -> list[datetime]:
    """Les départs d'une même passe, réduits au premier."""
    passes: list[datetime] = []
    for start in starts:
        if not passes or start - passes[-1] > SAME_PASS:
            passes.append(start)
    return passes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--jours", type=float, default=7.0, help="fenêtre de mesure, en jours")
    parser.add_argument(
        "--depuis", default=None, help="début de la fenêtre, ISO 8601 (prime sur --jours)"
    )
    parser.add_argument("--source", default=None, help="ne mesurer qu'une source")
    args = parser.parse_args()

    now = datetime.now(UTC)
    since = (
        datetime.fromisoformat(args.depuis).astimezone(UTC)
        if args.depuis is not None
        else now - timedelta(days=args.jours)
    )
    span_hours = (now - since).total_seconds() / 3600
    declared = declared_minutes()
    dsn = dsn_from_env_file(ENV_FILE)
    host, database, user = dsn_target(dsn)
    print(f"base      : {database} sur {host} ({user})")
    print(f"fenêtre   : depuis {since:%Y-%m-%d %H:%M} UTC, {span_hours:.1f} h")
    print()
    print(
        f"{'source':<12} {'passes':>6} {'attendu':>7} {'médiane':>8} {'p90':>7} {'max':>8} "
        f"{'déclarée':>9} {'registre':>9}  verdict"
    )

    holes: list[tuple[str, datetime, datetime, float]] = []
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select s.key,
                   extract(epoch from s.expected_interval)::int / 60 as expected_minutes,
                   array_agg(r.started_at order by r.started_at) filter (where r.id is not null)
            from ingest.data_sources s
            left join ingest.import_runs r
              on r.source_id = s.id
             and r.status in ('success', 'partial')
             and r.started_at >= %s
            where (%s::text is null or s.key = %s)
            group by s.key, s.expected_interval
            order by s.key
            """,
            (since, args.source, args.source),
        )
        for key, expected_minutes, starts in cur.fetchall():
            passes = collapse(list(starts or []))
            cadence = declared.get(key)
            expected = "—" if cadence is None else f"{span_hours * 60 / cadence:.0f}"
            shown_cadence = "—" if cadence is None else str(cadence)
            if len(passes) < 2:
                verdict = "aucune tâche planifiée" if cadence is None else "pas assez de passes"
                print(
                    f"{key:<12} {len(passes):>6} {expected:>7} {'—':>8} {'—':>7} {'—':>8} "
                    f"{shown_cadence:>9} {expected_minutes:>9}  {verdict}"
                )
                continue
            gaps = [(later - earlier).total_seconds() / 60 for earlier, later in pairwise(passes)]
            if cadence is not None:
                threshold = max(3 * cadence, 30)
                holes.extend(
                    (key, earlier, later, gap)
                    for (earlier, later), gap in zip(pairwise(passes), gaps, strict=True)
                    if gap > threshold
                )
            ordered = sorted(gaps)
            median = statistics.median(ordered)
            p90 = ordered[min(len(ordered) - 1, round(0.9 * (len(ordered) - 1)))]
            worst = ordered[-1]
            if cadence is None:
                verdict = "aucune tâche planifiée"
            elif median <= cadence * 1.5:
                verdict = "tient"
            else:
                verdict = f"ne tient pas ({median / cadence:.1f} fois la cadence)"
            print(
                f"{key:<12} {len(passes):>6} {expected:>7} {median:>8.0f} {p90:>7.0f} "
                f"{worst:>8.0f} {shown_cadence:>9} {expected_minutes:>9}  {verdict}"
            )

    print()
    print(
        "minutes ; « attendu » = passes qu'aurait données la cadence déclarée sur la fenêtre ; "
        "médiane et p90"
    )
    print(
        "des écarts entre passes ; « déclarée » = ops/tasks.json, "
        "« registre » = expected_interval. Tient : médiane ≤ 1,5 fois la déclarée."
    )
    if holes:
        print()
        print("trous (écart > 3 fois la cadence, ou > 30 min) :")
        for key, earlier, later, gap in sorted(holes, key=lambda hole: hole[1]):
            print(
                f"  {key:<12} {earlier:%d/%m %H:%M} → {later:%d/%m %H:%M} UTC  "
                f"{gap / 60:.1f} h sans passe"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
