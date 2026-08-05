#!/usr/bin/env python3
"""Fusion et normalisation du corpus d'archives NASA FIRMS (VIIRS, France).

Entrée  : les CSV extraits des zips d'Archive Download FIRMS
          (fire_archive_*.csv = corpus standard, fire_nrt_*.csv = queue NRT).
Sortie  : un Parquet unique normalisé + un rapport de synthèse.

Règles appliquées (documentées pour la recette) :
  R1. Chaque ligne est étiquetée corpus=standard|nrt et fichier source.
  R2. `instrument` est normalisé à "VIIRS" (les fichiers S-NPP portent "SNPP").
  R3. `detected_at` (UTC) est reconstruit depuis acq_date + acq_time (HHMM).
  R4. Priorité au standard : pour un satellite donné, toute ligne NRT datée
      avant ou au dernier jour standard de ce satellite est écartée
      (le retraitement scientifique fait foi).
  R5. Doublons exacts (satellite, detected_at, lat, lon) supprimés,
      standard conservé en priorité.
  R6. `type` (0 végétation, 1 volcan, 2 source statique, 3 offshore)
      n'existe que dans le corpus standard ; conservé en nullable, avec
      un drapeau dérivé is_vegetation (True/False/NA).
  R7. Aucune ligne n'est filtrée sur type/qualité : le Parquet est le
      corpus complet ; les filtres appartiennent aux usages en aval.

Usage : python fusion_corpus_firms.py <dossier_csv> <sortie.parquet>
"""

from __future__ import annotations

import glob
import os
import sys

import pandas as pd

COLONNES_CLES = ["satellite", "detected_at", "latitude", "longitude"]


def charger(dossier: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    fichiers = sorted(glob.glob(os.path.join(dossier, "fire_*.csv")))
    if not fichiers:
        raise SystemExit(f"Aucun fire_*.csv dans {dossier}")
    for f in fichiers:
        df = pd.read_csv(f, dtype=str)
        df["fichier_source"] = os.path.basename(f)
        df["corpus"] = "standard" if "archive" in os.path.basename(f) else "nrt"
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def normaliser(d: pd.DataFrame) -> pd.DataFrame:
    # R2 — instrument
    d["instrument"] = "VIIRS"
    # Types numériques
    for col in ("latitude", "longitude", "brightness", "bright_t31", "frp", "scan", "track"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    # R3 — horodatage UTC
    hhmm = d["acq_time"].str.zfill(4)
    d["detected_at"] = pd.to_datetime(
        d["acq_date"] + " " + hhmm.str[:2] + ":" + hhmm.str[2:], utc=True
    )
    # R6 — type nullable + drapeau végétation
    if "type" not in d.columns:
        d["type"] = pd.NA
    d["type"] = d["type"].astype("Int8")
    d["is_vegetation"] = d["type"].map({0: True, 1: False, 2: False, 3: False})
    return d


def deduper(d: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    stats: dict[str, int] = {}
    # R4 — priorité au standard par satellite
    fin_standard = (
        d[d.corpus == "standard"].groupby("satellite")["detected_at"].max().to_dict()
    )
    def nrt_obsolete(row) -> bool:
        fin = fin_standard.get(row["satellite"])
        return row["corpus"] == "nrt" and fin is not None and row["detected_at"] <= fin
    masque = d.apply(nrt_obsolete, axis=1)
    stats["nrt_ecartees_recouvrement_standard"] = int(masque.sum())
    d = d[~masque]
    # R5 — doublons exacts, standard d'abord
    d = d.sort_values("corpus", ascending=False)  # "standard" > "nrt"
    avant = len(d)
    d = d.drop_duplicates(subset=COLONNES_CLES, keep="first")
    stats["doublons_exacts_supprimes"] = avant - len(d)
    return d.sort_values(["detected_at", "satellite"]).reset_index(drop=True), stats


def main() -> None:
    dossier = sys.argv[1] if len(sys.argv) > 1 else "."
    sortie = sys.argv[2] if len(sys.argv) > 2 else "firms_france_viirs.parquet"
    d = normaliser(charger(dossier))
    d, stats = deduper(d)
    d.to_parquet(sortie, index=False)

    print(f"Corpus écrit : {sortie} ({os.path.getsize(sortie)/1e6:.1f} Mo)")
    print(f"Lignes : {len(d)}  |  période : {d.detected_at.min()} → {d.detected_at.max()}")
    for k, v in stats.items():
        print(f"  {k} : {v}")
    print("\nPar satellite / corpus :")
    print(d.groupby(["satellite", "corpus"]).size().to_string())
    print("\nDrapeau végétation (type 0) :")
    print(d["is_vegetation"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
