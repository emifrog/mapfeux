"""Banc de calibration des paramètres de regroupement.

Usage :
    micromamba run -n mapfeux-geo python scripts/calibrate-clustering.py
    micromamba run -n mapfeux-geo python scripts/calibrate-clustering.py --axes
    micromamba run -n mapfeux-geo python scripts/calibrate-clustering.py --etiquette sous-corpus

`--etiquette` suffixe le fichier de résultats — `croise-<etiquette>.csv` — pour
qu'un balayage sur le sous-corpus n'écrase pas les mesures du corpus complet.
Le banc mesure ce que contient la base : le fichier doit dire sur quoi.

Référence : cahier §17.2 et §24.8.

Rejoue le regroupement complet du corpus pour chaque jeu de paramètres et
mesure les indicateurs qui comptent. Le réglage se joue entre deux échecs
symétriques :

- **trop serré** : un même feu éclate en dizaines d'événements d'une seule
  détection, et la carte devient un semis illisible ;
- **trop lâche** : des feux distincts fusionnent par chaînage, et une fiche
  décrit un phénomène qui n'a jamais existé — la faute la plus grave, puisqu'elle
  est invisible sans vérification terrain.

Par défaut le balayage est **croisé** : rayon, fenêtre et seuil combinés. Une première
version ne faisait varier qu'un paramètre à la fois, parce qu'un jeu coûtait
deux minutes. Elle avait montré des résultats non monotones, que des variations
isolées ne permettaient pas d'expliquer : on ne voit pas une interaction en
regardant les axes séparément. Le regroupement en mémoire ramène le coût à
quelques secondes, ce qui rend le produit cartésien abordable.

`--axes` retrouve l'ancien mode, une variation par ligne, utile pour une
lecture rapide.

Aucun indicateur ne tranche seul. Le tableau sert à un arbitrage humain, il ne
choisit pas à sa place.

L'état final de la base est restauré avec les paramètres de référence. Cette
restauration passe par un `finally`, qui couvre une erreur ou une interruption
au clavier — pas la mort du processus. Tuée, la passe en cours est défaite par
le serveur et la base reste sur le jeu précédent : jamais l'état de référence,
mais jamais un corpus sans événements non plus.
"""

from __future__ import annotations

import csv
import pathlib
import sys
import time
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import calibration_dsn, dsn_target
from geo_worker.pipelines.clustering import (
    ClusteringParams,
    cluster_detections,
    delete_algorithmic_events,
    pending_detection_count,
)

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
RESULT_DIR = ROOT / "data" / "calibration"

RADII = (1_000, 1_500, 2_000, 2_500, 3_000, 4_000, 5_000)
WINDOWS = (6, 12, 24, 48)
THRESHOLDS = (0.20, 0.35, 0.50, 0.65)

# La croissance du rayon avec le temps s'était montrée quasi inerte sur ce
# corpus : la faire varier ici quadruplerait le balayage sans rien révéler.
GROWTH_M_PER_HOUR = 500


def label(radius: int, window: int, threshold: float) -> str:
    return f"calib-r{radius}-w{window}-s{threshold:.2f}"


def crossed_grid() -> list[ClusteringParams]:
    return [
        ClusteringParams(
            version=label(radius, window, threshold),
            base_radius_m=radius,
            growth_m_per_hour=GROWTH_M_PER_HOUR,
            attach_window_hours=window,
            min_score=threshold,
        )
        for radius in RADII
        for window in WINDOWS
        for threshold in THRESHOLDS
    ]


def axis_grid() -> list[ClusteringParams]:
    """Une variation par ligne, à partir de la référence."""
    return [
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
  -- Part des observations portée par les événements les plus fournis. C'est
  -- l'indicateur de lisibilite : quand sept evenements portent plus des trois
  -- quarts des observations, la carte montre surtout du bruit.
  -- (Pas de signe pour-cent dans cette requete : psycopg le lirait comme un
  -- marqueur de parametre.)
  coalesce(sum(detection_count) filter (where detection_count >= 5), 0) as detections_etayees,
  coalesce(round(max(diagonale_km)::numeric, 1), 0) as diagonale_max_km,
  -- Mediane calculee sur les seuls evenements a plusieurs detections. Prise sur
  -- l'ensemble, elle valait zero partout : plus de la moitie des evenements sont
  -- des observations isolees, dont la duree est nulle par construction. La
  -- colonne avait donc l'apparence d'une mesure sans en etre une.
  coalesce(
    round(
      percentile_cont(0.5) within group (
        order by span_hours
      ) filter (where detection_count > 1)::numeric,
      1
    ),
    0
  ) as duree_mediane_h
from e
"""


def clear(conn: psycopg.Connection[Any]) -> None:
    """Supprime les événements algorithmiques, jamais les décisions humaines.

    Le prédicat vit dans `delete_algorithmic_events`, partagé avec le
    remplacement de corpus d'`import-corpus.py` : une seule définition de
    « algorithmique », qui ne valide pas — l'appelant enchaîne un regroupement
    et valide l'ensemble, de sorte qu'un jeu de paramètres est tout ou rien.
    L'histoire de cette règle est dans la docstring de la fonction.
    """
    delete_algorithmic_events(conn)


def measure(conn: psycopg.Connection[Any], version: str) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(METRICS_SQL, {"version": version})
        row = cur.fetchone()
    return dict(row or {})


def percent(part: Any, whole: Any) -> int:
    total = int(whole or 0)
    return 0 if total == 0 else round(100 * int(part or 0) / total)


def output_name(argv: list[str]) -> str:
    """Nom du fichier de résultats, suffixé par l'étiquette éventuelle."""
    base = "axes" if "--axes" in argv else "croise"
    if "--etiquette" not in argv:
        return f"{base}.csv"
    index = argv.index("--etiquette")
    if index + 1 >= len(argv):
        raise SystemExit("--etiquette attend une valeur.")
    return f"{base}-{argv[index + 1]}.csv"


def main(argv: list[str]) -> int:
    grid = axis_grid() if "--axes" in argv else crossed_grid()

    # Base de calibration obligatoire : chaque jeu efface et réécrit les
    # événements, et sur le corpus complet le balayage dure des heures. Sur la
    # base de production, le site servirait pendant tout ce temps des
    # regroupements qu'on ne publie pas.
    dsn = calibration_dsn(ENV_FILE)
    host, port, database = dsn_target(dsn)

    # `flush` systématique : hors terminal, Python met la sortie en tampon par
    # blocs, et un balayage de plusieurs minutes ne montrerait rien avant la fin.
    print(f"base : {host}:{port}/{database}", flush=True)
    print(f"{len(grid)} jeux de paramètres à comparer.\n", flush=True)

    header = (
        f"{'jeu':<26} {'évts':>5} {'1 det':>6} {'étayé':>6} "
        f"{'≥2 capt':>8} {'+gros':>6} {'diag km':>8} {'durée h':>8} {'temps':>7}"
    )
    print(header, flush=True)
    print("-" * len(header), flush=True)

    rows: list[dict[str, Any]] = []

    with psycopg.connect(dsn, connect_timeout=30) as conn:
        try:
            sweep(conn, grid, rows)
        finally:
            # Une interruption ne doit pas laisser la base sur un jeu
            # expérimental : le site lit la même table, et servirait alors une
            # carte produite par des paramètres qu'on ne publie pas.
            restore(conn)

    if not rows:
        print("Aucun résultat à écrire.")
        return 1

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    destination = RESULT_DIR / output_name(argv)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Résultats : {destination.relative_to(ROOT)}")

    return 0


def restore(conn: psycopg.Connection[Any]) -> None:
    clear(conn)
    cluster_detections(conn, params=ClusteringParams(), limit=None)
    conn.commit()
    print("\nBase restaurée avec les paramètres de référence (grouping-v1).", flush=True)


def sweep(
    conn: psycopg.Connection[Any],
    grid: list[ClusteringParams],
    rows: list[dict[str, Any]],
) -> None:
    for params in grid:
        clear(conn)
        started = time.monotonic()
        # Passe unique sans plafond : un jeu de paramètres se juge sur le corpus
        # entier. Une passe bornée en regrouperait la tête — les premières
        # semaines, l'ordre étant chronologique — et le tableau annoncerait ces
        # chiffres comme ceux du corpus.
        cluster_detections(conn, params=params, limit=None)
        conn.commit()
        elapsed = time.monotonic() - started

        # Le banc mesure ce qu'il a regroupé, pas ce qu'il croit avoir regroupé.
        # Si des orphelines subsistent, la ligne décrirait une fraction du
        # corpus sous le nom du corpus : on s'arrête plutôt que de l'écrire.
        remaining = pending_detection_count(conn)
        if remaining > 0:
            raise SystemExit(
                f"{params.version} : {remaining} détection(s) publiable(s) sans "
                "événement après la passe. Le balayage s'arrête — une ligne "
                "mesurée sur une partie du corpus n'est pas comparable aux autres."
            )

        m = measure(conn, params.version)
        singleton_pct = percent(m["singletons"], m["evenements"])
        multi_pct = percent(m["multi_capteurs"], m["evenements"])
        # Part des observations dans les événements à cinq détections ou plus :
        # ce que la carte montre vraiment quand on hiérarchise.
        substantiated_pct = percent(m["detections_etayees"], m["detections"])

        print(
            f"{params.version:<26} {m['evenements']:>5} {str(singleton_pct) + '%':>6} "
            f"{str(substantiated_pct) + '%':>6} {str(multi_pct) + '%':>8} "
            f"{m['plus_gros']:>6} {m['diagonale_max_km']!s:>8} "
            f"{m['duree_mediane_h']!s:>8} {elapsed:>6.1f}s",
            flush=True,
        )

        rows.append(
            {
                "version": params.version,
                "rayon_m": params.base_radius_m,
                "croissance_m_h": params.growth_m_per_hour,
                "fenetre_h": params.attach_window_hours,
                "seuil": params.min_score,
                "evenements": m["evenements"],
                "detections": m["detections"],
                "singletons": m["singletons"],
                "singletons_pct": singleton_pct,
                "detections_etayees_pct": substantiated_pct,
                "multi_capteurs_pct": multi_pct,
                "plus_gros": m["plus_gros"],
                "diagonale_max_km": m["diagonale_max_km"],
                "duree_mediane_h": m["duree_mediane_h"],
                "secondes": round(elapsed, 1),
            }
        )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
