"""Tests de la dérivation du registre des sources statiques — J10, FR-035.

Les règles G1 à G5 s'éprouvent sur des corpus synthétiques : récurrence
exigée, fusion du jitter de pixel, séparation des sites distincts, clé et
empreinte indifférentes à l'ordre de lecture.
"""

from __future__ import annotations

import pandas as pd
import pytest

from geo_worker.static_sources import (
    MASK_VERSION,
    MIN_DETECTIONS,
    StaticSourceError,
    derive_static_sources,
)


def detection(*, lat: float, lon: float, quand: str, type_: int | None = 2) -> dict[str, object]:
    return {
        "latitude": lat,
        "longitude": lon,
        "type": type_,
        "detected_at": pd.Timestamp(quand, tz="UTC"),
    }


def corpus(*rows: dict[str, object]) -> pd.DataFrame:
    frame = pd.DataFrame(list(rows))
    frame["type"] = frame["type"].astype("Int8")
    return frame


def torchere(lat: float, lon: float, months: int, per_month: int) -> list[dict[str, object]]:
    """Site récurrent : `per_month` détections sur `months` mois, jitter ±200 m."""
    rows: list[dict[str, object]] = []
    for m in range(months):
        for i in range(per_month):
            jitter = ((i % 5) - 2) * 0.0008
            rows.append(
                detection(
                    lat=lat + jitter,
                    lon=lon - jitter,
                    quand=f"{2020 + m // 12}-{m % 12 + 1:02d}-10T0{i % 10}:00:00Z",
                )
            )
    return rows


class TestRecurrence:
    def test_site_recurrent_retenu(self) -> None:
        sources, stats = derive_static_sources(
            corpus(*torchere(43.44, 4.89, months=8, per_month=4))
        )
        assert len(sources) == 1
        assert sources[0].month_count == 8
        assert stats["couverture_pct"] == 100.0

    def test_feu_d_une_saison_rejete(self) -> None:
        # Beaucoup de détections mais deux mois : un feu, pas une usine (G2).
        sources, stats = derive_static_sources(
            corpus(*torchere(44.5, -0.5, months=2, per_month=30))
        )
        assert sources == []
        assert stats["sources_retenues"] == 0

    def test_seuil_de_detections(self) -> None:
        rows = torchere(43.44, 4.89, months=7, per_month=2)  # 14 < MIN_DETECTIONS
        assert len(rows) < MIN_DETECTIONS
        sources, _ = derive_static_sources(corpus(*rows))
        assert sources == []


class TestGeometrie:
    def test_jitter_fusionne_sites_distincts_separes(self) -> None:
        proche = torchere(43.440, 4.890, months=8, per_month=4)
        lointain = torchere(43.520, 4.890, months=8, per_month=4)  # ~9 km au nord
        sources, _ = derive_static_sources(corpus(*proche, *lointain))
        assert len(sources) == 2

    def test_rayon_borne_et_couvrant(self) -> None:
        sources, _ = derive_static_sources(corpus(*torchere(43.44, 4.89, months=8, per_month=4)))
        assert 500 <= sources[0].match_radius_m <= 5000


class TestDeterminisme:
    def test_ordre_de_lecture_indifferent(self) -> None:
        rows = torchere(43.44, 4.89, months=8, per_month=4) + torchere(
            48.1, 6.2, months=12, per_month=3
        )
        avant, stats_1 = derive_static_sources(corpus(*rows))
        apres, stats_2 = derive_static_sources(corpus(*reversed(rows)))
        assert [s.source_key for s in avant] == [s.source_key for s in apres]
        assert stats_1["empreinte"] == stats_2["empreinte"]
        assert all(s.source_key.startswith(f"{MASK_VERSION}:") for s in avant)


class TestRefus:
    def test_type_absent_ignore(self) -> None:
        # Les lignes NRT n'ont pas de type : elles ne fondent jamais une source.
        rows = torchere(43.44, 4.89, months=8, per_month=4)
        nrt = [detection(lat=43.44, lon=4.89, quand="2026-07-01T01:00:00Z", type_=None)]
        sources, stats = derive_static_sources(corpus(*rows, *nrt))
        assert stats["detections_type2"] == len(rows)
        assert len(sources) == 1

    def test_corpus_sans_type2_refuse(self) -> None:
        with pytest.raises(StaticSourceError):
            derive_static_sources(
                corpus(detection(lat=43.4, lon=4.9, quand="2022-07-01T01:00:00Z", type_=0))
            )

    def test_colonnes_manquantes_refusees(self) -> None:
        frame = corpus(*torchere(43.44, 4.89, months=8, per_month=4)).drop(columns=["type"])
        with pytest.raises(StaticSourceError, match="type"):
            derive_static_sources(frame)
