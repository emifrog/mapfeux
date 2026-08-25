"""Tests de la palette versionnée de la qualité de l'air — cahier §19.1.

La palette est un contrat public : les seuils sont ceux de l'indice ATMO,
les bornes supérieures sont incluses, et la version accompagne chaque actif.
Ce qui se vérifie ici, c'est la sémantique des bornes — l'endroit exact où
une couleur ment si on se trompe d'un côté.
"""

from __future__ import annotations

import numpy as np
import pytest

from geo_worker.air_palette import (
    BANDS,
    PALETTE_VERSION,
    band_for,
    color_rgb,
    legend,
    thresholds,
)
from geo_worker.providers.cams import POLLUTANTS


class TestBands:
    def test_les_polluants_du_connecteur_exactement(self) -> None:
        # La palette couvre ce que CAMS importe, ni plus ni moins : un
        # polluant sans palette ne pourrait pas être tuilé.
        assert set(BANDS) == set(POLLUTANTS)

    def test_six_bandes_et_seuils_croissants(self) -> None:
        for pollutant, bands in BANDS.items():
            assert len(bands) == 6
            assert bands[-1].upper is None
            finite = list(thresholds(pollutant))
            assert finite == sorted(finite)
            assert len(finite) == 5

    def test_seuils_atmo_pm2_5(self) -> None:
        assert thresholds("pm2_5") == (10.0, 20.0, 25.0, 50.0, 75.0)

    def test_seuils_atmo_pm10(self) -> None:
        assert thresholds("pm10") == (20.0, 40.0, 50.0, 100.0, 150.0)


class TestBandFor:
    def test_borne_superieure_incluse(self) -> None:
        # 10,0 µg/m³ de PM2,5 est encore « bon » ; l'epsilon au-dessus ne
        # l'est plus. C'est la convention de l'indice, pas un choix local.
        assert band_for("pm2_5", 10.0).label == "bon"
        assert band_for("pm2_5", 10.001).label == "moyen"

    def test_bande_ouverte(self) -> None:
        assert band_for("pm10", 10_000.0).label == "extrêmement mauvais"

    def test_coherence_avec_digitize(self) -> None:
        # Le rendu des tuiles classe par `numpy.digitize(right=True)` ; la
        # fiche classera par `band_for`. Les deux chemins doivent donner la
        # même bande, bornes comprises — sinon la carte et la fiche se
        # contrediraient sur la même valeur.
        for pollutant in BANDS:
            values = np.array(
                [0.0, *thresholds(pollutant), *(t + 0.001 for t in thresholds(pollutant)), 999.0]
            )
            by_digitize = np.digitize(values, thresholds(pollutant), right=True)
            by_band_for = [BANDS[pollutant].index(band_for(pollutant, v)) for v in values]
            assert list(by_digitize) == by_band_for


class TestLegend:
    def test_versionnee_et_sourcee(self) -> None:
        serialized = legend("pm10")
        assert serialized["version"] == PALETTE_VERSION
        assert "ATMO" in serialized["source"]
        assert serialized["unite"] == "µg/m³"
        assert len(serialized["bandes"]) == 6
        assert serialized["bandes"][-1]["jusqu_a"] is None

    def test_couleurs_hexadecimales_decodables(self) -> None:
        for bands in BANDS.values():
            for band in bands:
                r, g, b = color_rgb(band)
                assert 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255

    def test_polluant_inconnu_refuse(self) -> None:
        with pytest.raises(KeyError):
            legend("o3")
