"""Détaille les plus gros événements produits par un jeu de paramètres.

Usage :
    micromamba run -n mapfeux-geo python scripts/inspect-clustering.py
    micromamba run -n mapfeux-geo python scripts/inspect-clustering.py \
        --radius 1000 --window 48 --score 0.50

Référence : cahier §17.2.

Le banc de calibration compare des agrégats ; il ne dit pas *ce qui* a été
regroupé. Or les deux fautes possibles produisent des chiffres qui se
ressemblent : un jeu de paramètres qui découpe un grand feu réel en morceaux et
un jeu qui sépare correctement deux feux voisins donnent tous deux « plus
d'événements, plus petits ».

Ce script montre les plus gros événements avec ce qui permet de trancher : leur
profil temporel jour par jour, leur étendue et leurs capteurs. Un vrai feu a un
profil continu ; un chaînage a des trous, parce qu'il agrège des départs
distincts qui ne brûlaient pas en même temps.

Le regroupement est rejoué sous une version dédiée puis effacé : la base
retrouve ses paramètres de référence.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file
from geo_worker.pipelines.clustering import ClusteringParams, cluster_detections

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
INSPECTION_VERSION = "inspect-run"

TOP_EVENTS_SQL = """
select
  e.id,
  e.detection_count,
  e.sensor_count,
  round(extensions.st_y(e.representative_point)::numeric, 3) as lat,
  round(extensions.st_x(e.representative_point)::numeric, 3) as lon,
  round(
    (extract(epoch from (e.last_detected_at - e.first_detected_at)) / 3600.0)::numeric, 1
  ) as duree_h,
  case
    when e.extent is null then 0
    else round(
      (extensions.st_maxdistance(
         extensions.st_convexhull(e.extent), extensions.st_convexhull(e.extent)
       ) * 111)::numeric, 1)
  end as diagonale_km,
  m.name as commune
from fire.events e
left join geo.municipalities m on m.insee_code = e.nearest_municipality_code
where e.algorithm_version = %(version)s
order by e.detection_count desc
limit %(top)s
"""

PROFILE_SQL = """
select
  (d.acquired_at at time zone 'UTC')::date as jour,
  count(*) as detections,
  count(distinct d.sensor) as capteurs,
  round(max(d.frp_mw)::numeric, 0) as frp_max
from fire.event_detections ed
join fire.detections d
  on d.id = ed.detection_id and d.acquired_at = ed.detection_acquired_at
where ed.event_id = %(event_id)s
group by 1
order by 1
"""


def option(argv: list[str], name: str, fallback: float) -> float:
    if name not in argv:
        return fallback
    index = argv.index(name)
    if index + 1 >= len(argv):
        sys.exit(f"{name} attend une valeur.")
    return float(argv[index + 1])


def clear(conn: psycopg.Connection[Any], version: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            delete from fire.events
            where algorithm_version = %(version)s
              and official_control_status is null
              and verification_status in ('satellite_detection', 'probable_event')
              and freshness_status <> 'hidden'
              and manual_state = '{}'::jsonb
            """,
            {"version": version},
        )
    conn.commit()


def restore(conn: psycopg.Connection[Any]) -> None:
    reference = ClusteringParams()
    clear(conn, INSPECTION_VERSION)
    clear(conn, reference.version)
    cluster_detections(conn, params=reference, limit=None)
    conn.commit()


def inspect(conn: psycopg.Connection[Any], params: ClusteringParams, top: int) -> None:
    clear(conn, INSPECTION_VERSION)
    clear(conn, ClusteringParams().version)
    # Sans plafond : l'inspection cherche le plus gros événement du corpus, et
    # une passe bornée n'en montrerait que le plus gros de sa tranche.
    cluster_detections(conn, params=params, limit=None)
    conn.commit()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(TOP_EVENTS_SQL, {"version": params.version, "top": top})
        events = cur.fetchall()

        for rank, event in enumerate(events, start=1):
            commune = event["commune"] or "commune inconnue"
            print(
                f"\n{rank}. {event['detection_count']} détections, "
                f"{event['sensor_count']} capteur(s), "
                f"{event['duree_h']} h, diagonale {event['diagonale_km']} km"
            )
            print(f"   {commune} ({event['lat']}, {event['lon']})")

            cur.execute(PROFILE_SQL, {"event_id": event["id"]})
            days = cur.fetchall()
            print("   jour         det  capt  FRP max")
            for day in days:
                print(
                    f"   {day['jour']}  {day['detections']:>4}  "
                    f"{day['capteurs']:>4}  {day['frp_max']:>7}"
                )
            # Un jour manquant entre le premier et le dernier signale un
            # regroupement qui a franchi une interruption de l'activité.
            span_days = (days[-1]["jour"] - days[0]["jour"]).days + 1
            if span_days > len(days):
                print(f"   ⚠ {span_days - len(days)} jour(s) sans aucune détection")


def main(argv: list[str]) -> int:
    params = ClusteringParams(
        version=INSPECTION_VERSION,
        base_radius_m=option(argv, "--radius", 2_500),
        growth_m_per_hour=option(argv, "--growth", 500),
        attach_window_hours=option(argv, "--window", 24),
        min_score=option(argv, "--score", 0.35),
    )
    top = int(option(argv, "--top", 5))

    print(
        f"rayon {params.base_radius_m:.0f} m, croissance {params.growth_m_per_hour:.0f} m/h, "
        f"fenêtre {params.attach_window_hours:.0f} h, seuil {params.min_score:.2f}"
    )

    with psycopg.connect(dsn_from_env_file(ENV_FILE), connect_timeout=30) as conn:
        try:
            inspect(conn, params, top)
        finally:
            restore(conn)
            print("\nBase restaurée avec les paramètres de référence (grouping-v1).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
