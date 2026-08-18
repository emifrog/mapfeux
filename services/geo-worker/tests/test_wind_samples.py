"""Extraction du vent aux points des événements.

Une erreur de convention ici ne se voit pas : un panache calculé sur une
direction inversée s'éloignerait du feu du mauvais côté, avec des communes
« potentiellement concernées » qui ne le sont pas — et celles qui le sont,
absentes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
import xarray as xr

from geo_worker.pipelines.wind_samples import (
    WindExtractionError,
    cell_distance_m,
    extract_samples,
    meteo_direction_deg,
    wind_speed_ms,
)

RUN_AT = datetime(2026, 8, 17, 6, tzinfo=UTC)


def grille(u_values: np.ndarray, v_values: np.ndarray) -> xr.Dataset:
    """Grille synthétique aux latitudes **décroissantes**, comme AROME."""
    return xr.Dataset(
        {
            "u10": (("step", "latitude", "longitude"), u_values),
            "v10": (("step", "latitude", "longitude"), v_values),
        },
        coords={
            "step": np.array([0, 3_600_000_000_000], dtype="timedelta64[ns]"),
            "latitude": [45.05, 45.025, 45.0],
            "longitude": [5.0, 5.025, 5.05],
        },
    )


def plan(a: float, b: float, c: float) -> np.ndarray:
    """Champ affine en (lat, lon) : l'interpolation bilinéaire y est exacte."""
    lats = np.array([45.05, 45.025, 45.0])
    lons = np.array([5.0, 5.025, 5.05])
    field = a + b * lons[None, :] + c * lats[:, None]
    return np.stack([field, field + 1.0])


class TestConventions:
    def test_vitesse(self) -> None:
        assert wind_speed_ms(3.0, 4.0) == pytest.approx(5.0)

    @pytest.mark.parametrize(
        ("u", "v", "attendu"),
        [
            (1.0, 0.0, 270.0),  # souffle vers l'est : vient de l'ouest
            (0.0, 1.0, 180.0),  # vers le nord : vient du sud
            (-1.0, 0.0, 90.0),  # vers l'ouest : vient de l'est
            (0.0, -1.0, 0.0),  # vers le sud : vient du nord
        ],
    )
    def test_direction_meteorologique(self, u: float, v: float, attendu: float) -> None:
        assert meteo_direction_deg(u, v) == pytest.approx(attendu)

    def test_direction_toujours_dans_la_rose(self) -> None:
        for angle in range(0, 360, 15):
            u = float(np.cos(np.radians(angle)))
            v = float(np.sin(np.radians(angle)))
            assert 0.0 <= meteo_direction_deg(u, v) < 360.0


class TestExtractSamples:
    def test_bilineaire_exacte_sur_un_champ_affine(self) -> None:
        # Sur un plan, la bilinéaire restitue la valeur exacte : tout écart
        # serait une erreur d'axes — latitudes croissantes supposées, par
        # exemple, le piège de la grille AROME. Les coefficients gardent le
        # champ dans le physique : le garde-fou d'aberration veille aussi ici.
        dataset = grille(plan(-160.0, 3.0, 3.5), plan(100.0, -1.0, -2.0))
        lon, lat = 5.0125, 45.0375
        samples = extract_samples(
            dataset, run_at=RUN_AT, longitude=lon, latitude=lat, method="bilinear"
        )
        assert len(samples) == 2
        assert samples[0].u_ms == pytest.approx(-160.0 + 3.0 * lon + 3.5 * lat, abs=0.01)
        assert samples[1].u_ms == pytest.approx(samples[0].u_ms + 1.0, abs=0.01)

    def test_voisin_rend_la_valeur_du_noeud(self) -> None:
        u = plan(-160.0, 3.0, 3.5)
        dataset = grille(u, plan(100.0, -1.0, -2.0))
        samples = extract_samples(
            # Tout près du nœud (45.025, 5.025), au centre de la grille.
            dataset,
            run_at=RUN_AT,
            longitude=5.026,
            latitude=45.024,
            method="nearest",
        )
        assert samples[0].u_ms == pytest.approx(float(u[0, 1, 1]), abs=0.01)
        assert samples[0].interpolation == "nearest"

    def test_les_echeances_suivent_le_run(self) -> None:
        dataset = grille(plan(1.0, 0.0, 0.0), plan(0.0, 0.0, 0.0))
        samples = extract_samples(
            dataset, run_at=RUN_AT, longitude=5.02, latitude=45.02, method="bilinear"
        )
        assert [s.valid_at for s in samples] == [RUN_AT, RUN_AT + timedelta(hours=1)]
        assert all(s.level == "10m" for s in samples)

    def test_distance_a_la_cellule_bornee_par_la_grille(self) -> None:
        dataset = grille(plan(1.0, 0.0, 0.0), plan(0.0, 0.0, 0.0))
        distance = cell_distance_m(dataset, 5.0125, 45.0375)
        # Un demi-pas de grille à 0,025° vaut au plus ~2 km : au-delà, le
        # calcul ne mesure pas ce qu'il croit.
        assert 0.0 < distance < 2_500.0

    def test_refuse_un_point_hors_emprise(self) -> None:
        dataset = grille(plan(1.0, 0.0, 0.0), plan(0.0, 0.0, 0.0))
        with pytest.raises(WindExtractionError, match="hors de l'emprise"):
            extract_samples(
                dataset, run_at=RUN_AT, longitude=6.5, latitude=45.02, method="bilinear"
            )

    def test_refuse_une_composante_aberrante(self) -> None:
        u = plan(1.0, 0.0, 0.0)
        u[0, 1, 1] = 3.0e4  # un GRIB corrompu, pas un vent
        dataset = grille(u, plan(0.0, 0.0, 0.0))
        with pytest.raises(WindExtractionError, match="aberrante"):
            extract_samples(
                dataset, run_at=RUN_AT, longitude=5.025, latitude=45.025, method="nearest"
            )

    def test_refuse_une_methode_inconnue(self) -> None:
        dataset = grille(plan(1.0, 0.0, 0.0), plan(0.0, 0.0, 0.0))
        with pytest.raises(WindExtractionError, match="Méthode"):
            extract_samples(dataset, run_at=RUN_AT, longitude=5.02, latitude=45.02, method="cubic")
