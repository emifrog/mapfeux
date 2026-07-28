"""Tests des règles de regroupement — cahier §24.1, §17.2 et §17.3."""

from __future__ import annotations

import pytest

from geo_worker.clustering import (
    ClusteringParams,
    attachment_score,
    confidence_level,
    confidence_score,
    spatial_window_m,
)

PARAMS = ClusteringParams()


class TestClusteringParams:
    def test_refuse_des_rayons_incoherents(self) -> None:
        with pytest.raises(ValueError, match="Rayons"):
            ClusteringParams(base_radius_m=5000, max_radius_m=1000)

    def test_refuse_une_fenetre_nulle(self) -> None:
        with pytest.raises(ValueError, match="Fenêtre"):
            ClusteringParams(attach_window_hours=0)

    def test_refuse_un_seuil_hors_bornes(self) -> None:
        with pytest.raises(ValueError, match="Seuil"):
            ClusteringParams(min_score=0)
        with pytest.raises(ValueError, match="Seuil"):
            ClusteringParams(min_score=1.5)


class TestSpatialWindow:
    def test_rayon_de_base_sans_delai(self) -> None:
        assert spatial_window_m(0, PARAMS) == PARAMS.base_radius_m

    def test_croit_avec_le_temps_ecoule(self) -> None:
        assert spatial_window_m(4, PARAMS) == 2_500 + 4 * 500

    def test_est_plafonne(self) -> None:
        # Sans plafond, deux feux d'une même vallée finiraient confondus.
        assert spatial_window_m(100, PARAMS) == PARAMS.max_radius_m

    def test_refuse_un_delai_negatif(self) -> None:
        with pytest.raises(ValueError, match="Délai négatif"):
            spatial_window_m(-1, PARAMS)


class TestAttachmentScore:
    def test_score_maximal_au_meme_endroit_et_au_meme_instant(self) -> None:
        assert attachment_score(distance_m=0, hours_elapsed=0, params=PARAMS) == 1.0

    def test_nul_au_dela_de_la_fenetre_spatiale(self) -> None:
        assert attachment_score(distance_m=3_000, hours_elapsed=0, params=PARAMS) == 0.0

    def test_nul_au_dela_de_la_fenetre_temporelle(self) -> None:
        assert attachment_score(distance_m=100, hours_elapsed=25, params=PARAMS) == 0.0

    def test_decroit_avec_la_distance(self) -> None:
        proche = attachment_score(distance_m=200, hours_elapsed=1, params=PARAMS)
        loin = attachment_score(distance_m=2_000, hours_elapsed=1, params=PARAMS)
        assert proche > loin

    def test_decroit_avec_le_temps(self) -> None:
        recent = attachment_score(distance_m=500, hours_elapsed=1, params=PARAMS)
        ancien = attachment_score(distance_m=500, hours_elapsed=18, params=PARAMS)
        assert recent > ancien

    def test_la_proximite_ne_compense_pas_l_anciennete(self) -> None:
        # Composantes multipliées et non additionnées : une détection collée
        # mais vieille de 23 heures ne doit pas franchir le seuil.
        collee_et_ancienne = attachment_score(distance_m=10, hours_elapsed=23, params=PARAMS)
        assert collee_et_ancienne < PARAMS.min_score

    def test_refuse_une_distance_negative(self) -> None:
        with pytest.raises(ValueError, match="Distance négative"):
            attachment_score(distance_m=-1, hours_elapsed=0, params=PARAMS)


class TestConfidenceScore:
    def test_detection_isolee_reste_faible(self) -> None:
        score = confidence_score(
            detection_count=1,
            sensor_count=1,
            mean_provider_confidence=0.6,
            known_source_count=0,
            span_hours=0,
        )
        assert confidence_level(score) == "low"

    def test_plusieurs_capteurs_et_passages_elevent_la_fiabilite(self) -> None:
        score = confidence_score(
            detection_count=8,
            sensor_count=2,
            mean_provider_confidence=0.85,
            known_source_count=0,
            span_hours=9,
        )
        assert confidence_level(score) == "high"

    def test_confiance_fournisseur_inconnue_vaut_neutre_et_non_zero(self) -> None:
        inconnue = confidence_score(
            detection_count=4,
            sensor_count=2,
            mean_provider_confidence=None,
            known_source_count=0,
            span_hours=4,
        )
        nulle = confidence_score(
            detection_count=4,
            sensor_count=2,
            mean_provider_confidence=0.0,
            known_source_count=0,
            span_hours=4,
        )
        assert inconnue > nulle

    def test_source_thermique_connue_abaisse_sans_annuler(self) -> None:
        # La classification n'est pas une suppression (§17.7) : le score baisse,
        # l'événement continue d'exister.
        propre = confidence_score(
            detection_count=6,
            sensor_count=2,
            mean_provider_confidence=0.8,
            known_source_count=0,
            span_hours=6,
        )
        torchere = confidence_score(
            detection_count=6,
            sensor_count=2,
            mean_provider_confidence=0.8,
            known_source_count=6,
            span_hours=6,
        )
        assert 0 < torchere < propre

    def test_evenement_sans_detection(self) -> None:
        assert (
            confidence_score(
                detection_count=0,
                sensor_count=0,
                mean_provider_confidence=None,
                known_source_count=0,
                span_hours=0,
            )
            == 0.0
        )

    def test_score_borne_dans_zero_un(self) -> None:
        score = confidence_score(
            detection_count=1_000,
            sensor_count=4,
            mean_provider_confidence=1.0,
            known_source_count=0,
            span_hours=500,
        )
        assert 0.0 <= score <= 1.0


class TestConfidenceLevel:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [(0.0, "low"), (0.44, "low"), (0.45, "medium"), (0.69, "medium"), (0.70, "high")],
    )
    def test_seuils_publics(self, score: float, expected: str) -> None:
        assert confidence_level(score) == expected
