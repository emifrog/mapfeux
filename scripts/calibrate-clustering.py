"""Banc de calibration des paramètres de regroupement.

Usage :
    micromamba run -n mapfeux-geo python scripts/calibrate-clustering.py
    micromamba run -n mapfeux-geo python scripts/calibrate-clustering.py --axes
    micromamba run -n mapfeux-geo python scripts/calibrate-clustering.py --etiquette sous-corpus
    micromamba run -n mapfeux-geo python scripts/calibrate-clustering.py \
        --jeux calib-r2500-w24-s0.35,calib-r2000-w24-s0.50 --etiquette finalistes

`--etiquette` suffixe le fichier de résultats — `croise-<etiquette>.csv` — pour
qu'un balayage sur le sous-corpus n'écrase pas les mesures du corpus complet.
Le banc mesure ce que contient la base : le fichier doit dire sur quoi.

`--jeux` rejoue une liste de jeux désignés par leur étiquette, telle qu'elle
figure dans la colonne `version` du CSV : les finalistes du dépouillement se
copient tels quels — retaper des paramètres, c'est se tromper. C'est la passe
de validation : classement sur le sous-corpus, finalistes seuls sur le corpus
complet, une nuit au plus.

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

Les résultats s'écrivent **au fil de l'eau**, une ligne par jeu mesuré. Une
version antérieure écrivait le CSV à la fin : le balayage du 6 août au soir est
mort à l'extinction du poste après un jeu sur cent douze, et ce jeu — mesuré,
payé — n'a laissé aucune trace hors du journal. Un fichier qui grandit pendant
la nuit dit aussi où en est la course, ce qu'un tampon en mémoire ne dit pas.
"""

from __future__ import annotations

import csv
import pathlib
import re
import sys
import time
from collections.abc import Callable
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

#: Colonnes du CSV, figées : l'écriture au fil de l'eau pose l'en-tête avant la
#: première mesure, elle ne peut plus le déduire de la première ligne.
FIELDNAMES: tuple[str, ...] = (
    "version",
    "rayon_m",
    "croissance_m_h",
    "fenetre_h",
    "seuil",
    "evenements",
    "detections",
    "singletons",
    "singletons_pct",
    "detections_etayees_pct",
    "multi_capteurs_pct",
    "plus_gros",
    "diagonale_max_km",
    "duree_mediane_h",
    "secondes",
)


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


#: Forme des étiquettes produites par `label()`. La croissance n'y figure pas :
#: elle est figée hors de la surface de calibration (voir GROWTH_M_PER_HOUR).
LABEL_PATTERN = re.compile(r"^calib-r(\d+)-w(\d+)-s(\d\.\d{2})$")


def parse_set_label(raw: str) -> ClusteringParams:
    """Reconstruit un jeu de paramètres depuis son étiquette.

    `calib-reference` est accepté : le jeu de référence est un finaliste
    légitime, et la passe de validation doit pouvoir l'inclure dans la même
    mesure que ses concurrents.
    """
    if raw == "calib-reference":
        return ClusteringParams(version="calib-reference")
    match = LABEL_PATTERN.match(raw)
    if match is None:
        raise SystemExit(
            f"Étiquette de jeu invalide : {raw}\n"
            "Attendu calib-r<rayon>-w<fenêtre>-s<seuil> — la colonne version "
            "du CSV — ou calib-reference."
        )
    return ClusteringParams(
        version=raw,
        base_radius_m=int(match.group(1)),
        growth_m_per_hour=GROWTH_M_PER_HOUR,
        attach_window_hours=int(match.group(2)),
        min_score=float(match.group(3)),
    )


def finalist_grid(raw: str) -> list[ClusteringParams]:
    """Liste de jeux depuis `--jeux`, refusée si une étiquette s'y répète.

    Mesurer deux fois le même jeu coûterait dix minutes sur le corpus complet
    pour produire une ligne en double — et un doublon dans la liste est
    toujours une erreur de copie, jamais une intention.
    """
    labels = [part.strip() for part in raw.split(",") if part.strip()]
    if not labels:
        raise SystemExit("--jeux attend au moins une étiquette.")
    duplicates = {name for name in labels if labels.count(name) > 1}
    if duplicates:
        raise SystemExit(f"Étiquette(s) en double dans --jeux : {', '.join(sorted(duplicates))}")
    return [parse_set_label(name) for name in labels]


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


def parse_option(argv: list[str], name: str) -> str | None:
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        raise SystemExit(f"{name} attend une valeur.")
    return argv[index + 1]


def output_name(argv: list[str]) -> str:
    """Nom du fichier de résultats, suffixé par l'étiquette éventuelle."""
    if "--axes" in argv:
        base = "axes"
    elif "--jeux" in argv:
        base = "jeux"
    else:
        base = "croise"
    etiquette = parse_option(argv, "--etiquette")
    return f"{base}.csv" if etiquette is None else f"{base}-{etiquette}.csv"


def main(argv: list[str]) -> int:
    if "--axes" in argv and "--jeux" in argv:
        raise SystemExit("--axes et --jeux sont exclusifs : un mode de grille à la fois.")

    finalists = parse_option(argv, "--jeux")
    if finalists is not None:
        grid = finalist_grid(finalists)
    elif "--axes" in argv:
        grid = axis_grid()
    else:
        grid = crossed_grid()

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

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    destination = RESULT_DIR / output_name(argv)
    measured = 0

    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(FIELDNAMES))
        writer.writeheader()
        handle.flush()

        def on_row(row: dict[str, Any]) -> None:
            # Une ligne mesurée est une ligne sur disque : l'extinction du
            # poste ne peut plus effacer une mesure déjà payée.
            nonlocal measured
            measured += 1
            writer.writerow(row)
            handle.flush()

        failures: list[str] = []
        with psycopg.connect(dsn, connect_timeout=30) as conn:
            # Les agrégats d'un jeu serré — 2 500 événements à recalculer —
            # dépassent le statement_timeout par défaut du projet Supabase :
            # QueryCanceled a arrêté le balayage du 7 août au premier jeu.
            # Réglage de session : la production garde le sien.
            conn.execute("set statement_timeout = '10min'")
            try:
                failures = sweep(conn, grid, on_row)
            finally:
                # Une interruption ne doit pas laisser la base sur un jeu
                # expérimental : le site lit la même table, et servirait alors
                # une carte produite par des paramètres qu'on ne publie pas.
                restore(conn)

    print(f"Résultats : {destination.relative_to(ROOT)}")
    if measured == 0:
        print("Aucun jeu mesuré : le fichier ne contient que l'en-tête.")
        return 1
    if failures:
        # Un balayage partiel ne doit pas passer pour un succès : les lignes
        # présentes se comparent entre elles, mais la grille est incomplète.
        print(f"{len(failures)} jeu(x) en échec : {', '.join(failures)}")
        return 1

    return 0


def restore(conn: psycopg.Connection[Any]) -> None:
    # La connexion peut arriver ici avec une transaction avortée : le `finally`
    # s'exécute aussi sur exception. Sans rollback, la restauration échouait à
    # son tour (`InFailedSqlTransaction`) et la base restait sur le jeu
    # expérimental — c'est arrivé le 7 août.
    conn.rollback()
    clear(conn)
    cluster_detections(conn, params=ClusteringParams(), limit=None)
    conn.commit()
    print("\nBase restaurée avec les paramètres de référence (grouping-v1).", flush=True)


def sweep(
    conn: psycopg.Connection[Any],
    grid: list[ClusteringParams],
    on_row: Callable[[dict[str, Any]], None],
) -> list[str]:
    """Mesure chaque jeu ; retourne les étiquettes des jeux en échec.

    Un incident de base sur un jeu — timeout, coupure réseau — ne condamne pas
    la nuit entière : le jeu est annulé, annoncé, et la course continue. Le
    balayage du 7 août s'était arrêté au premier jeu pour un QueryCanceled que
    les cent onze suivants n'auraient jamais vu.
    """
    failures: list[str] = []
    for params in grid:
        clear(conn)
        started = time.monotonic()
        # Passe unique sans plafond : un jeu de paramètres se juge sur le corpus
        # entier. Une passe bornée en regrouperait la tête — les premières
        # semaines, l'ordre étant chronologique — et le tableau annoncerait ces
        # chiffres comme ceux du corpus.
        try:
            cluster_detections(conn, params=params, limit=None)
            conn.commit()
        except psycopg.Error as exc:
            # Tout ou rien : le rollback défait aussi le clear(), la base reste
            # sur le jeu précédent, jamais vide.
            conn.rollback()
            reason = str(exc).splitlines()[0][:90] if str(exc) else type(exc).__name__
            print(f"{params.version:<26} ÉCHEC — {reason}", flush=True)
            failures.append(params.version)
            continue
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

        on_row(
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

    return failures


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
