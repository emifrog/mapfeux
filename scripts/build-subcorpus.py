"""Constitue le sous-corpus stratifié de calibration.

Usage :
    micromamba run -n mapfeux-geo python scripts/build-subcorpus.py
    micromamba run -n mapfeux-geo python scripts/build-subcorpus.py --corpus <chemin.parquet>

Référence : cahier §17.2 et §24.8 ; plan de développement §2.

Les strates vivent dans `geo_worker.subcorpus`, éprouvées sans fichier ni base ;
ce script les applique au corpus complet et écrit le Parquet à côté, avec son
compte rendu JSON.

Le Parquet du sous-corpus n'est **pas** versionné — le dépôt porte déjà 13 Mo
de binaires régénérables (dette §15). Le compte rendu l'est : il prouve la
provenance — version des strates, effectifs, empreinte de contenu — et
l'extraction est reproductible à l'identique depuis le corpus complet.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "geo-worker" / "src"))

from geo_worker.corpus import CorpusError
from geo_worker.subcorpus import SUBCORPUS_VERSION, extract

DERIVE = ROOT / "data" / "firms" / "derive"
DEFAULT_CORPUS = DERIVE / "firms_france_viirs_2012-2026.parquet"
DEFAULT_OUTPUT = DERIVE / f"firms_calibration_{SUBCORPUS_VERSION}.parquet"


def parse_option(argv: list[str], name: str) -> str | None:
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        sys.exit(f"{name} attend une valeur.")
    return argv[index + 1]


def main(argv: list[str]) -> int:
    corpus_path = pathlib.Path(parse_option(argv, "--corpus") or DEFAULT_CORPUS)
    output_path = pathlib.Path(parse_option(argv, "--sortie") or DEFAULT_OUTPUT)

    if not corpus_path.exists():
        sys.exit(
            f"Corpus introuvable : {corpus_path}\n"
            "Le constituer avec services/geo-worker/tools/fusion_corpus_firms.py."
        )

    frame = pd.read_parquet(corpus_path)
    print(f"corpus  : {corpus_path.name} — {len(frame)} lignes")
    print(f"strates : {SUBCORPUS_VERSION}\n", flush=True)

    try:
        selection, stats = extract(frame)
    except CorpusError as exc:
        sys.exit(f"Extraction impossible : {exc}")

    for key, detail in stats["strates"].items():
        print(f"  {key:<26} {detail['lignes']:>6} ligne(s)")
    print(
        f"\n  {'total':<26} {stats['lignes']:>6} ligne(s) "
        f"({stats['part_du_corpus_pct']} % du corpus, "
        f"recouvrement {stats['recouvrement_strates']})"
    )
    print(f"  empreinte de contenu : {stats['empreinte_contenu']}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    selection.to_parquet(output_path, index=False)
    report_path = output_path.with_suffix(".json")
    report_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\nsous-corpus  : {output_path.relative_to(ROOT).as_posix()}")
    print(f"compte rendu : {report_path.relative_to(ROOT).as_posix()}")

    print("\nÉtapes suivantes :")
    print(
        "  python scripts/import-corpus.py --remplacer "
        f"--corpus {output_path.relative_to(ROOT).as_posix()}"
    )
    print("  python scripts/calibrate-clustering.py --axes --etiquette sous-corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
