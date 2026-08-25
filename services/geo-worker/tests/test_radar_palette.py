"""Tests de la palette radar versionnée — cahier §19.1."""

from __future__ import annotations

import numpy as np

from geo_worker.radar_palette import (
    BANDS,
    DRAWN_FROM_MM_H,
    RADAR_PALETTE_VERSION,
    band_for,
    color_rgb,
    legend,
    thresholds,
)


class TestBands:
    def test_six_bandes_et_seuils_croissants(self) -> None:
        assert len(BANDS) == 6
        assert BANDS[-1].upper is None
        finite = list(thresholds())
        assert finite == sorted(finite)
        assert len(finite) == 5

    def test_le_seuil_de_trace_reste_sous_la_premiere_bande(self) -> None:
        # Tout ce qui se dessine doit avoir une couleur : un seuil de tracé
        # au-dessus du premier seuil rendrait la première bande invisible.
        assert DRAWN_FROM_MM_H < thresholds()[0]


class TestBandFor:
    def test_borne_superieure_incluse(self) -> None:
        assert band_for(3.0).label == "faible"
        assert band_for(3.001).label == "modérée"

    def test_bande_ouverte(self) -> None:
        assert band_for(500.0).label == "extrême"

    def test_coherence_avec_digitize(self) -> None:
        # Le rendu classe par `numpy.digitize(right=True)` : les deux chemins
        # doivent donner la même bande, bornes comprises.
        values = np.array([0.5, *thresholds(), *(t + 0.001 for t in thresholds()), 999.0])
        by_digitize = np.digitize(values, thresholds(), right=True)
        by_band_for = [BANDS.index(band_for(float(v))) for v in values]
        assert list(by_digitize) == by_band_for


class TestLegend:
    def test_versionnee_et_honnete_sur_sa_source(self) -> None:
        serialized = legend()
        assert serialized["version"] == RADAR_PALETTE_VERSION
        # Pas d'échelle réglementaire des couleurs radar : la légende doit
        # dire que le découpage est éditorial, pas l'habiller d'autorité.
        assert "éditorial" in serialized["source"]
        assert serialized["unite"] == "mm/h"
        assert serialized["seuil_trace"] == DRAWN_FROM_MM_H
        assert len(serialized["bandes"]) == 6

    def test_couleurs_decodables(self) -> None:
        for band in BANDS:
            r, g, b = color_rgb(band)
            assert 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255
