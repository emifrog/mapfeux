#!/usr/bin/env python3
"""Fusion et normalisation du corpus d'archives NASA FIRMS (VIIRS, France).

Usage :
    micromamba run -n mapfeux-geo python services/geo-worker/tools/fusion_corpus_firms.py \\
        data/firms/brut data/firms/derive/firms_france_viirs_2012-2026.parquet

Entrée  : le dossier des téléchargements Archive Download FIRMS. Les archives
          `.zip` sont lues telles quelles ; les `fire_*.csv` déjà extraits sont
          acceptés aussi.
Sortie  : un Parquet normalisé, et à côté un compte rendu `.json`.

Les règles de fusion (R1 à R7) vivent dans `geo_worker.corpus`, où elles sont
couvertes par des tests. Ce script ne fait que lire, appeler, écrire et rendre
compte.

Le compte rendu est le point du dispositif, pas un ornement. Il porte :

- l'empreinte SHA-256 de chaque zip lu, avec ses membres. Les zips FIRMS ne
  sont pas reproductibles : ils sont engendrés à la demande, sur commande
  numérotée. Ce qu'on peut prouver, c'est qu'un corpus donné vient de ces
  fichiers-là ;
- l'empreinte de **contenu** du corpus produit. Deux écritures Parquet du même
  tableau ne donnent pas les mêmes octets, à version d'écrivain identique :
  hacher le fichier ne prouverait rien ;
- ce que chaque règle a écarté, et sur quelle borne. R4 n'écarte rien
  aujourd'hui, la passation entre corpus étant nette ; c'est une propriété du
  téléchargement, pas de la règle, et elle doit se lire.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import zipfile
from typing import Any

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from geo_worker.corpus import CorpusError, merge  # noqa: E402


def read_sources(source: pathlib.Path) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Lit les CSV FIRMS, depuis les zips comme depuis les fichiers extraits."""
    frames: dict[str, pd.DataFrame] = {}
    provenance: list[dict[str, Any]] = []

    for archive in sorted(source.glob("*.zip")):
        octets = archive.read_bytes()
        membres: list[dict[str, Any]] = []
        with zipfile.ZipFile(archive) as z:
            for info in sorted(z.infolist(), key=lambda i: i.filename):
                if not info.filename.startswith("fire_"):
                    continue
                with z.open(info) as handle:
                    frames[info.filename] = pd.read_csv(handle, dtype=str)
                membres.append({"nom": info.filename, "octets": info.file_size})
        provenance.append(
            {
                "fichier": archive.name,
                "octets": len(octets),
                "sha256": hashlib.sha256(octets).hexdigest(),
                "membres": membres,
            }
        )

    for csv in sorted(source.glob("fire_*.csv")):
        if csv.name in frames:
            continue
        octets = csv.read_bytes()
        frames[csv.name] = pd.read_csv(csv, dtype=str)
        provenance.append(
            {
                "fichier": csv.name,
                "octets": len(octets),
                "sha256": hashlib.sha256(octets).hexdigest(),
                "membres": [],
            }
        )

    if not frames:
        raise CorpusError(f"Aucun fire_*.csv, ni dans un zip ni en clair, dans {source}")

    return frames, provenance


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    source = pathlib.Path(argv[0])
    destination = pathlib.Path(argv[1])

    frames, provenance = read_sources(source)
    corpus, stats = merge(frames)

    destination.parent.mkdir(parents=True, exist_ok=True)
    corpus.to_parquet(destination, index=False)

    rapport = {"sources": provenance, "regles": stats}
    rapport_path = destination.with_suffix(".json")
    rapport_path.write_text(
        json.dumps(rapport, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    taille = destination.stat().st_size / 1e6
    print(f"Corpus écrit  : {destination} ({taille:.1f} Mo)")
    print(f"Compte rendu  : {rapport_path}")
    print(f"Empreinte     : {stats['empreinte_contenu']}")
    print(f"Lignes        : {stats['lignes']}")
    print(f"Période       : {stats['periode_debut']} → {stats['periode_fin']}")
    print()
    print(f"R4 — NRT écartées par recouvrement : {stats['nrt_ecartees_recouvrement_standard']}")
    for satellite, borne in stats["bornes_standard"].items():
        print(f"     borne standard {satellite} : {borne}")
    if stats["satellites_sans_standard"]:
        print(
            "     sans corpus standard, donc rien à écarter : "
            + ", ".join(stats["satellites_sans_standard"])
        )
    print(f"R5 — doublons exacts supprimés     : {stats['doublons_exacts_supprimes']}")
    print()
    print(
        f"Sources statiques (type 2) : {stats['sources_statiques']} "
        f"({stats['sources_statiques_pct']} pour cent)"
    )
    print(f"Sans type (corpus NRT)     : {stats['sans_type']}")
    print()
    for cle, valeur in sorted(stats["par_satellite_corpus"].items()):
        print(f"  {cle:<18} {valeur}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
