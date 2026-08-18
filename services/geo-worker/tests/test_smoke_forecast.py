"""Panache indicatif : l'algorithme du §18.3 sur vent synthétique.

Sur un vent uniforme et constant, chaque grandeur a une valeur fermée :
distance = vitesse * durée * coefficient, largeur = formule du cône, cap =
aval du vent. Tout écart est une erreur d'algorithme, pas d'atmosphère.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
import xarray as xr

from geo_worker.pipelines.smoke_forecast import (
    PlumeError,
    PlumeParameters,
    _angular_spread_deg,
    compute_plume,
    downwind_bearing_deg,
    inputs_checksum,
    plume_width_m,
    sample_wind,
)

RUN_AT = datetime(2026, 8, 17, 6, tzinfo=UTC)


def vent_uniforme(u: float, v: float, hours: int = 12) -> xr.Dataset:
    """Grille large — le centre du panache doit pouvoir s'y déplacer."""
    lats = np.arange(46.0, 43.9, -0.25)
    lons = np.arange(4.0, 7.1, 0.25)
    shape = (hours + 1, len(lats), len(lons))
    return xr.Dataset(
        {
            "u10": (("step", "latitude", "longitude"), np.full(shape, u)),
            "v10": (("step", "latitude", "longitude"), np.full(shape, v)),
        },
        coords={
            "step": np.array(
                [h * 3_600_000_000_000 for h in range(hours + 1)], dtype="timedelta64[ns]"
            ),
            "latitude": lats,
            "longitude": lons,
        },
    )


class TestGeometriePure:
    def test_cap_aval_oppose_a_la_provenance(self) -> None:
        assert downwind_bearing_deg(270.0) == pytest.approx(90.0)  # d'ouest → vers l'est
        assert downwind_bearing_deg(0.0) == pytest.approx(180.0)  # du nord → vers le sud

    def test_largeur_du_cone(self) -> None:
        # largeur(d) = initiale + d·tan(angle/2), la formule §18.3 telle quelle.
        import math

        attendu = 500.0 + 10_000.0 * math.tan(math.radians(10.0))
        assert plume_width_m(500.0, 10_000.0, 20.0) == pytest.approx(attendu)

    def test_etendue_angulaire_traverse_le_nord(self) -> None:
        # 350° et 10° sont à 20° l'un de l'autre, pas à 340°.
        assert _angular_spread_deg([350.0, 10.0]) == pytest.approx(20.0, abs=0.1)


class TestSampleWind:
    def test_interpole_lineairement_dans_le_temps(self) -> None:
        dataset = vent_uniforme(4.0, 0.0, hours=1)
        # Le champ passe de 4 à 4 (uniforme) : varions-le à la main.
        dataset["u10"][1, :, :] = 6.0
        wind = sample_wind(
            dataset,
            run_at=RUN_AT,
            longitude=5.5,
            latitude=45.0,
            at=RUN_AT + timedelta(minutes=30),
        )
        assert wind is not None
        assert wind[0] == pytest.approx(5.0, abs=0.01)

    def test_rend_none_hors_couverture(self) -> None:
        dataset = vent_uniforme(4.0, 0.0, hours=1)
        assert (
            sample_wind(
                dataset,
                run_at=RUN_AT,
                longitude=5.5,
                latitude=45.0,
                at=RUN_AT + timedelta(hours=2),
            )
            is None
        )


class TestComputePlume:
    def test_vent_d_ouest_pousse_le_panache_vers_l_est(self) -> None:
        dataset = vent_uniforme(5.0, 0.0)  # d'ouest, 5 m/s
        result = compute_plume(
            dataset,
            run_at=RUN_AT,
            longitude=5.0,
            latitude=45.0,
            started_at=RUN_AT + timedelta(hours=1),
            parameters=PlumeParameters(horizon_minutes=60),
        )
        assert result is not None
        assert len(result.steps) == 4
        # distance = vitesse * durée * coefficient, au pas près.
        assert result.steps[-1].distance_m == pytest.approx(5.0 * 3600 * 0.9, rel=1e-3)
        # Le centre s'est déplacé vers l'est, pas ailleurs.
        assert result.steps[-1].center_lon > 5.1
        assert result.steps[-1].center_lat == pytest.approx(45.0, abs=0.01)
        assert all(s.direction_deg == pytest.approx(270.0) for s in result.steps)
        assert result.area_km2 > 0
        assert "coefficients_non_calibres" in result.quality_flags

    def test_resultat_vide_si_aucun_vent_sur_l_horizon(self) -> None:
        dataset = vent_uniforme(5.0, 0.0, hours=2)
        result = compute_plume(
            dataset,
            run_at=RUN_AT,
            longitude=5.0,
            latitude=45.0,
            started_at=RUN_AT + timedelta(hours=6),  # après la fin de couverture
        )
        assert result is None

    def test_horizon_tronque_quand_le_vent_s_arrete(self) -> None:
        dataset = vent_uniforme(5.0, 0.0, hours=1)
        result = compute_plume(
            dataset,
            run_at=RUN_AT,
            longitude=5.0,
            latitude=45.0,
            started_at=RUN_AT + timedelta(minutes=30),
            parameters=PlumeParameters(horizon_minutes=120),
        )
        assert result is not None
        # Couverture jusqu'à H+1, vent lu au début de chaque pas : les pas
        # démarrant à 6 h 30, 6 h 45 et 7 h 00 se calculent, pas les huit
        # demandés — et le dernier porte l'advection jusqu'à 7 h 15.
        assert len(result.steps) == 3
        assert "horizon_tronque" in result.quality_flags
        assert result.valid_to == RUN_AT + timedelta(minutes=75)

    def test_distance_maximale_tronque_et_le_dit(self) -> None:
        dataset = vent_uniforme(5.0, 0.0)
        result = compute_plume(
            dataset,
            run_at=RUN_AT,
            longitude=5.0,
            latitude=45.0,
            started_at=RUN_AT + timedelta(hours=1),
            parameters=PlumeParameters(horizon_minutes=60, max_distance_km=10.0),
        )
        assert result is not None
        # 4,05 km par pas : le troisième franchirait 12,15 km > 10 km.
        assert len(result.steps) == 2
        assert "distance_maximale_atteinte" in result.quality_flags

    def test_vent_faible_est_drapeaute_pas_masque(self) -> None:
        dataset = vent_uniforme(0.2, 0.0)
        result = compute_plume(
            dataset,
            run_at=RUN_AT,
            longitude=5.0,
            latitude=45.0,
            started_at=RUN_AT + timedelta(hours=1),
            parameters=PlumeParameters(horizon_minutes=60),
        )
        assert result is not None
        assert "vent_faible" in result.quality_flags
        assert result.confidence_factors["vent_faible"] is True
        assert result.confidence_level in ("medium", "low")

    def test_vitesse_aberrante_arrete_le_calcul(self) -> None:
        dataset = vent_uniforme(100.0, 0.0)
        with pytest.raises(PlumeError, match="aberrante"):
            compute_plume(
                dataset,
                run_at=RUN_AT,
                longitude=5.0,
                latitude=45.0,
                started_at=RUN_AT + timedelta(hours=1),
            )

    def test_refuse_un_horizon_hors_cadre(self) -> None:
        with pytest.raises(PlumeError, match="Horizon"):
            PlumeParameters(horizon_minutes=1440)


class TestInputsChecksum:
    def test_memes_entrees_meme_empreinte(self) -> None:
        kwargs = {
            "extract_checksum": "abc",
            "public_id": "MPF-TEST0000",
            "started_at": RUN_AT,
            "longitude": 5.0,
            "latitude": 45.0,
            "parameters": PlumeParameters(),
        }
        assert inputs_checksum(**kwargs) == inputs_checksum(**kwargs)

    def test_un_parametre_change_change_l_empreinte(self) -> None:
        base = inputs_checksum(
            extract_checksum="abc",
            public_id="MPF-TEST0000",
            started_at=RUN_AT,
            longitude=5.0,
            latitude=45.0,
            parameters=PlumeParameters(),
        )
        autre = inputs_checksum(
            extract_checksum="abc",
            public_id="MPF-TEST0000",
            started_at=RUN_AT,
            longitude=5.0,
            latitude=45.0,
            parameters=PlumeParameters(dispersion_angle_deg=25.0),
        )
        assert base != autre
