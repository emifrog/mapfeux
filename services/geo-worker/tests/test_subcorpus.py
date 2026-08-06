"""Tests du sous-corpus de calibration — cahier §17.2 et §24.8.

Les strates réelles sont bornées sur le corpus 2012-2026 ; les tester
demanderait le Parquet. Ces tests éprouvent la mécanique — sélection, union
sans doublon, refus des strates vides, reproductibilité — sur des strates
synthétiques, et la cohérence interne des strates réelles sans données.
"""

from __future__ import annotations

import pandas as pd
import pytest

from geo_worker.corpus import CorpusError, content_fingerprint
from geo_worker.subcorpus import (
    REQUIRED_COLUMNS,
    STRATA,
    Stratum,
    extract,
    stratum_mask,
)

ZONE = Stratum(
    key="zone-test",
    reason="fenêtre de test",
    lon_min=5.0,
    lon_max=6.0,
    lat_min=43.0,
    lat_max=44.0,
    start="2022-07-01",
    end="2022-08-01",
)

AUTRE_ZONE = Stratum(
    key="autre-zone",
    reason="seconde fenêtre, chevauchant la première",
    lon_min=5.5,
    lon_max=7.0,
    lat_min=43.0,
    lat_max=44.0,
    start="2022-07-01",
    end="2022-09-01",
)


def ligne(
    *,
    lat: float = 43.5,
    lon: float = 5.5,
    quand: str = "2022-07-15T12:00:00Z",
    satellite: str = "N20",
    type_: int | None = None,
) -> dict[str, object]:
    return {
        "latitude": lat,
        "longitude": lon,
        "detected_at": pd.Timestamp(quand),
        "satellite": satellite,
        "type": type_,
        "corpus": "standard",
        "fichier_source": "fire_archive_test.csv",
        "frp": 10.0,
    }


def corpus(*lignes: dict[str, object]) -> pd.DataFrame:
    frame = pd.DataFrame(list(lignes))
    frame["type"] = frame["type"].astype("Int8")
    return frame


def test_selection_dans_la_fenetre_spatiale_et_temporelle() -> None:
    frame = corpus(
        ligne(),
        ligne(lon=6.5),  # hors bbox
        ligne(quand="2022-08-15T12:00:00Z"),  # hors période
        ligne(lat=42.5),  # hors bbox
    )
    selection, stats = extract(frame, strata=(ZONE,))
    assert len(selection) == 1
    assert stats["strates"]["zone-test"]["lignes"] == 1
    assert stats["lignes_corpus"] == 4


def test_borne_de_fin_exclue() -> None:
    frame = corpus(ligne(), ligne(quand="2022-08-01T00:00:00Z"))
    selection, _ = extract(frame, strata=(ZONE,))
    assert len(selection) == 1


def test_union_sans_doublon_et_recouvrement_compte() -> None:
    # 5.7 tombe dans les deux fenêtres : sélectionnée une fois, comptée deux.
    frame = corpus(ligne(lon=5.2), ligne(lon=5.7), ligne(lon=6.5))
    selection, stats = extract(frame, strata=(ZONE, AUTRE_ZONE))
    assert len(selection) == 3
    assert stats["strates"]["zone-test"]["lignes"] == 2
    assert stats["strates"]["autre-zone"]["lignes"] == 2
    assert stats["recouvrement_strates"] == 1


def test_strate_vide_refusee() -> None:
    frame = corpus(ligne(lon=6.5))
    with pytest.raises(CorpusError, match="zone-test"):
        extract(frame, strata=(ZONE,))


def test_cles_de_strates_dupliquees_refusees() -> None:
    frame = corpus(ligne())
    with pytest.raises(CorpusError, match="même clé"):
        extract(frame, strata=(ZONE, ZONE))


def test_colonnes_manquantes_refusees() -> None:
    frame = corpus(ligne()).drop(columns=["satellite"])
    with pytest.raises(CorpusError, match="satellite"):
        extract(frame, strata=(ZONE,))


def test_colonnes_conservees_telles_quelles() -> None:
    frame = corpus(ligne())
    selection, _ = extract(frame, strata=(ZONE,))
    assert list(selection.columns) == list(frame.columns)


def test_extraction_reproductible_empreinte_comprise() -> None:
    frame = corpus(ligne(), ligne(lon=5.2), ligne(lat=43.9))
    premiere, stats_1 = extract(frame, strata=(ZONE,))
    # L'ordre de lecture ne doit rien changer : mêmes lignes, autre ordre.
    seconde, stats_2 = extract(frame.iloc[::-1].reset_index(drop=True), strata=(ZONE,))
    assert stats_1["empreinte_contenu"] == stats_2["empreinte_contenu"]
    assert stats_1["empreinte_contenu"] == content_fingerprint(premiere)
    assert premiere.reset_index(drop=True).equals(seconde.reset_index(drop=True))


def test_masque_est_booleen() -> None:
    frame = corpus(ligne(), ligne(lon=9.9))
    mask = stratum_mask(frame, ZONE)
    assert mask.dtype == bool
    assert mask.tolist() == [True, False]


def test_strates_reelles_coherentes_sans_donnees() -> None:
    """Les strates v1 se vérifient sans corpus : clés uniques, bornes ordonnées.

    Leur contenu, lui, ne se vérifie qu'à l'extraction — c'est le rôle du refus
    des strates vides.
    """
    keys = [stratum.key for stratum in STRATA]
    assert len(set(keys)) == len(keys)
    for stratum in STRATA:
        assert stratum.lon_min < stratum.lon_max, stratum.key
        assert stratum.lat_min < stratum.lat_max, stratum.key
        assert pd.Timestamp(stratum.start) < pd.Timestamp(stratum.end), stratum.key
        assert stratum.reason.strip(), stratum.key
    assert set(REQUIRED_COLUMNS) >= {"latitude", "longitude", "detected_at"}
