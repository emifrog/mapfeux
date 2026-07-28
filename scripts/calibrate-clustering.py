"""Banc de calibration des paramètres de regroupement.

Usage :
    micromamba run -n mapfeux-geo python scripts/calibrate-clustering.py

Référence : cahier §17.2 et §24.8.

Rejoue le regroupement complet du corpus pour chaque jeu de paramètres et
mesure les indicateurs qui comptent. Le réglage se joue entre deux échecs
symétriques :

- **trop serré** : un même feu éclate en dizaines d'événements d'une seule
  détection, et la carte devient un semis illisible ;
- **trop lâche** : des feux distincts fusionnent par chaînage, et une fiche
  décrit un phénomène qui n'a jamais existé — la faute la plus grave, puisqu'elle
  est invisible sans vérification terrain.

Aucun indicateur ne tranche seul. Le tableau sert à un arbitrage humain, il ne
choisit pas à sa place.

L'état final de la base est restauré avec les paramètres de référence.
"""

from __future__ import annotations

import pathlib
import sys
import time

import psycopg
from psycopg.rows import dict_row

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import dsn_from_env_file
from geo_worker.pipelines.clustering import (
    ClusteringParams,
    cluster_detections,
)

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"

# Jeux à comparer. Le premier est la référence actuelle ; chaque suivant ne fait
# varier qu'un paramètre, faute de quoi l'effet observé ne serait pas
# attribuable.
GRID: list[ClusteringParams] = [
    ClusteringParams(version="calib-reference"),
    ClusteringParams(version="calib-rayon-1500", base_radius_m=1_500),
    ClusteringParams(version="calib-rayon-4000", base_radius_m=4_000),
    ClusteringParams(version="calib-croissance-250", growth_m_per_hour=250),
    ClusteringParams(version="calib-croissance-1000", growth_m_per_hour=1_000),
    ClusteringParams(version="calib-fenetre-12h", attach_window_hours=12),
    ClusteringParams(version="calib-seuil-0.20", min_score=0.20),
    ClusteringParams(version="calib-seuil-0.50", min_score=0.50),
]

METRICS_SQL = """
with e as (
  select
    id,
    detection_count,
    sensor_count,
    extract(epoch from (last_detected_at - first_detected_at)) / 3600.0 as span_hours,
    case
      when extent is null then 0
      else extensions.st_maxdistance(
             extensions.st_convexhull(extent), extensions.st_convexhull(extent)
           ) * 111
    end as diagonale_km
  from fire.events
  where algorithm_version = %(version)s
)
select
  count(*) as evenements,
  coalesce(sum(detection_count), 0) as detections,
  count(*) filter (where detection_count = 1) as singletons,
  count(*) filter (where sensor_count >= 2) as multi_capteurs,
  coalesce(max(detection_count), 0) as plus_gros,
  coalesce(round(max(diagonale_km)::numeric, 1), 0) as diagonale_max_km,
  coalesce(round(percentile_cont(0.5) within group (order by span_hours)::numeric, 1), 0) as duree_mediane_h
from e
"""


def read_dsn() -> str:
    return dsn_from_env_file(ENV_FILE)


def clear(conn: psycopg.Connection[object]) -> None:
    """Supprime les événements algorithmiques, jamais les décisions humaines."""
    with conn.cursor() as cur:
        cur.execute(
            """
            delete from fire.events
            where algorithm_version <> 'demo-fixture'
              and official_control_status is null
              and verification_status in ('satellite_detection', 'probable_event')
              and freshness_status <> 'hidden'
              and manual_state = '{}'::jsonb
            """
        )
    conn.commit()


def measure(conn: psycopg.Connection[object], version: str) -> dict[str, object]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(METRICS_SQL, {"version": version})
        row = cur.fetchone()
    return dict(row or {})


def main() -> int:
    # `flush` systématique : hors terminal, Python met la sortie en tampon par
    # blocs, et un balayage de quinze minutes ne montrerait rien avant la fin.
    print(f"{len(GRID)} jeux de paramètres à comparer.\n", flush=True)

    header = (
        f"{'jeu':<22} {'évts':>5} {'1 det':>6} {'≥2 capt':>8} "
        f"{'+gros':>6} {'diag km':>8} {'durée h':>8} {'temps':>7}"
    )
    print(header, flush=True)
    print("-" * len(header), flush=True)

    with psycopg.connect(read_dsn(), connect_timeout=30) as conn:
        for params in GRID:
            clear(conn)
            started = time.monotonic()
            cluster_detections(conn, params=params)
            conn.commit()
            elapsed = time.monotonic() - started

            m = measure(conn, params.version)
            singleton_pct = (
                0
                if m["evenements"] == 0
                else round(100 * int(m["singletons"]) / int(m["evenements"]))
            )
            multi_pct = (
                0
                if m["evenements"] == 0
                else round(100 * int(m["multi_capteurs"]) / int(m["evenements"]))
            )

            print(
                f"{params.version:<22} {m['evenements']:>5} {str(singleton_pct) + '%':>6} "
                f"{str(multi_pct) + '%':>8} {m['plus_gros']:>6} "
                f"{m['diagonale_max_km']!s:>8} {m['duree_mediane_h']!s:>8} "
                f"{int(elapsed):>6}s",
                flush=True,
            )

        # État final : paramètres de référence, pour ne pas laisser la base
        # dans une configuration expérimentale.
        clear(conn)
        cluster_detections(conn, params=ClusteringParams())
        conn.commit()
        print("\nBase restaurée avec les paramètres de référence (grouping-v1).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
