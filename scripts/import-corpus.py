"""Charge le corpus d'archives FIRMS dans la base de calibration.

Usage :
    micromamba run -n mapfeux-geo python scripts/import-corpus.py
    micromamba run -n mapfeux-geo python scripts/import-corpus.py --corpus <chemin.parquet>
    micromamba run -n mapfeux-geo python scripts/import-corpus.py --limite 5000
    micromamba run -n mapfeux-geo python scripts/import-corpus.py --remplacer --corpus <chemin>

Référence : cahier §16.3 et §16.7 ; stratégie §3.4.

Le corpus vit en Parquet, le banc de calibration lit la base : ce script fait le
pont. Il vise **`CALIBRATION_DATABASE_URL`, jamais `DATABASE_URL`** — le banc
efface et réécrit les événements pendant des heures, et la base de production
est celle que le site sert au public. Le refus est explicite si les deux
variables désignent la même base.

Les lignes repassent par l'analyseur du flux temps réel, si bien qu'une
observation du corpus et la même observation importée en direct portent la même
clé d'idempotence. Rejouer ce script ne crée donc aucun doublon, et le corpus
peut être chargé sur une base où l'ingestion a déjà tourné.

`--limite` charge les N premières lignes chronologiques : de quoi vérifier la
chaîne en une minute avant d'engager les 337 757.

`--remplacer` vide d'abord la base — événements algorithmiques puis détections
que plus rien ne référence — **dans la transaction du chargement** : tout ou
rien. C'est la bascule entre corpus complet et sous-corpus de calibration ;
sans elle, l'idempotence ferait du chargement d'un sous-corpus un simple
constat que tout est déjà connu. Les décisions humaines survivent, comme au
banc : le prédicat est le même (`delete_algorithmic_events`).
"""

from __future__ import annotations

import pathlib
import sys
import time
from typing import Any

import pandas as pd
import psycopg

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.db import calibration_dsn, dsn_target
from geo_worker.pipelines.clustering import delete_algorithmic_events
from geo_worker.pipelines.corpus_import import (
    CorpusImportError,
    CorpusImportResult,
    import_corpus,
)
from geo_worker.pipelines.import_run import ImportRunError, import_run

ENV_FILE = ROOT / "services" / "geo-worker" / ".env"
DEFAULT_CORPUS = ROOT / "data" / "firms" / "derive" / "firms_france_viirs_2012-2026.parquet"


def parse_option(argv: list[str], name: str) -> str | None:
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        sys.exit(f"{name} attend une valeur.")
    return argv[index + 1]


def load_corpus(path: pathlib.Path, limit: int | None) -> list[dict[str, Any]]:
    if not path.exists():
        sys.exit(
            f"Corpus introuvable : {path}\n"
            "Le constituer avec services/geo-worker/tools/fusion_corpus_firms.py."
        )

    frame = pd.read_parquet(path)
    if limit is not None:
        # Tête chronologique : le corpus est déjà en ordre canonique par
        # satellite, donc on retrie pour que l'échantillon couvre une période
        # continue plutôt qu'un seul satellite.
        frame = frame.sort_values("detected_at", kind="stable").head(limit)

    # `acq_date` et `acq_time` restent la source de l'horodatage, comme dans le
    # flux temps réel : `detected_at` est une colonne dérivée du corpus, et la
    # reprendre ici ferait diverger les deux chemins.
    #
    # `to_dict` est typé avec des clés `Hashable` — un index pandas peut être
    # numéroté ou composite. Ici les clés sont les noms de colonnes, donc des
    # chaînes ; la conversion est explicite plutôt que supposée.
    return [
        {str(key): (None if pd.isna(value) else value) for key, value in record.items()}
        for record in frame.to_dict(orient="records")
    ]


def replace_existing(conn: psycopg.Connection[Any]) -> tuple[int, int]:
    """Vide le corpus en place, sans valider — tout ou rien avec le chargement.

    Les événements algorithmiques d'abord — prédicat partagé avec le banc de
    calibration, les décisions humaines survivent —, puis les détections que
    plus aucun événement ne référence. Aucune validation ici : un processus tué
    pendant le chargement laisse la base sur le corpus précédent, jamais vide.
    """
    events = delete_algorithmic_events(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            delete from fire.detections d
            where not exists (
              select 1
              from fire.event_detections ed
              where ed.detection_id = d.id
                and ed.detection_acquired_at = d.acquired_at
            )
            """
        )
        detections = cur.rowcount
    return events, detections


def main(argv: list[str]) -> int:
    corpus_path = pathlib.Path(parse_option(argv, "--corpus") or DEFAULT_CORPUS)
    raw_limit = parse_option(argv, "--limite")
    limit = int(raw_limit) if raw_limit is not None else None
    replace = "--remplacer" in argv

    try:
        dsn = calibration_dsn(ENV_FILE)
    except Exception as exc:  # DsnError, message déjà explicite
        sys.exit(str(exc))

    host, port, database = dsn_target(dsn)
    print(f"corpus  : {corpus_path}")
    print(f"cible   : {host}:{port}/{database}")
    if limit is not None:
        print(f"limite  : {limit} lignes")
    if replace:
        print("mode    : remplacement — la base est vidée dans la même transaction")
    print(flush=True)

    records = load_corpus(corpus_path, limit)
    print(f"{len(records)} ligne(s) lue(s). Normalisation et chargement…\n", flush=True)

    started = time.monotonic()
    last_report = [0]

    def report(result: CorpusImportResult) -> None:
        written = result.inserted + result.already_known
        if written == last_report[0]:
            return
        last_report[0] = written
        elapsed = time.monotonic() - started
        debit = written / elapsed if elapsed > 0 else 0
        print(
            f"  {written:>7} / {len(records)}  "
            f"({result.inserted} insérée(s), {result.already_known} déjà connue(s))  "
            f"{debit:.0f} l/s",
            flush=True,
        )

    removed: tuple[int, int] | None = None
    with psycopg.connect(dsn, connect_timeout=30) as conn:
        try:
            with import_run(conn, source_key="firms", job_name="corpus:archive") as counters:
                if replace:
                    removed = replace_existing(conn)
                    print(
                        f"  retrait : {removed[0]} événement(s), {removed[1]} détection(s)"
                        " — validé avec le chargement, tout ou rien\n",
                        flush=True,
                    )
                result = import_corpus(conn, records, on_progress=report)
                conn.commit()

                counters.records_read = result.read
                counters.records_inserted = result.inserted
                counters.records_rejected = result.rejected
                counters.source_data_at = result.source_data_at
                counters.metrics = {
                    "corpus": corpus_path.name,
                    "already_known": result.already_known,
                    "partitions": result.months,
                }
                if removed is not None:
                    counters.metrics["remplacement"] = {
                        "evenements_retires": removed[0],
                        "detections_retirees": removed[1],
                    }
        except CorpusImportError as exc:
            sys.exit(f"\nChargement impossible : {exc}")
        except ImportRunError as exc:
            sys.exit(f"\n{exc}")

    duration = time.monotonic() - started
    print(f"\nterminé en {duration:.0f} s.")
    print(f"  lues          : {result.read}")
    print(f"  insérées      : {result.inserted}")
    print(f"  déjà connues  : {result.already_known}")
    print(f"  rejetées      : {result.rejected}")
    print(f"  partitions    : {result.months} mois")

    if result.rejections:
        print("\nPremiers motifs de rejet :")
        for motif in result.rejections[:10]:
            print(f"  {motif}")

    # Un rejet n'annule pas le chargement, mais il ne doit pas passer pour un
    # succès : l'ordonnanceur comme l'opérateur doivent le voir.
    return 1 if result.rejected > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
