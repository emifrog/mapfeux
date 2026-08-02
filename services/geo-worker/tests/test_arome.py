"""Construction des références de paquets AROME.

Une erreur ici ne se voit pas : elle produit une URL absente, donc un jour de
corpus manquant, sur une donnée qui ne se rattrape pas.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from geo_worker.providers.arome import (
    ARCHIVE_EXTENT,
    RUN_HOURS,
    SPANS,
    AromeError,
    PackageRef,
    latest_run,
    next_reachable_noon,
    noon_lead_time,
    span_for_lead_time,
)


class TestPackageRef:
    def test_construit_le_nom_publie(self) -> None:
        reference = PackageRef(run=datetime(2026, 8, 2, 12, tzinfo=UTC), span="00H06H")
        assert reference.filename == "arome__0025__SP1__00H06H__2026-08-02T12:00:00Z.grib2"

    def test_construit_l_url_du_depot(self) -> None:
        reference = PackageRef(run=datetime(2026, 8, 2, 12, tzinfo=UTC), span="07H12H")
        assert reference.url == (
            "https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net/pnt/"
            "2026-08-02T12:00:00Z/arome/0025/SP1/"
            "arome__0025__SP1__07H12H__2026-08-02T12:00:00Z.grib2"
        )


class TestLatestRun:
    def test_recule_du_delai_de_diffusion(self) -> None:
        """Le run de l'heure courante n'est pas encore publié.

        À 13 h UTC, le run de 12 h est en cours de diffusion : demander celui-là
        retournerait un 404. Le retrait de trois heures et demie ramène sur
        celui de 9 h.
        """
        assert latest_run(datetime(2026, 8, 2, 13, tzinfo=UTC)) == datetime(
            2026, 8, 2, 9, tzinfo=UTC
        )

    def test_retient_un_run_effectivement_diffuse(self) -> None:
        assert latest_run(datetime(2026, 8, 2, 16, tzinfo=UTC)) == datetime(
            2026, 8, 2, 12, tzinfo=UTC
        )

    def test_repasse_sur_la_veille_en_debut_de_nuit(self) -> None:
        # À 2 h UTC, le retrait ramène avant minuit : le run du jour n'existe
        # pas encore, celui de 21 h la veille est le dernier publié.
        assert latest_run(datetime(2026, 8, 2, 2, tzinfo=UTC)) == datetime(
            2026, 8, 1, 21, tzinfo=UTC
        )


class TestSpanForLeadTime:
    @pytest.mark.parametrize(
        ("lead", "span"),
        [
            (0, "00H06H"),
            (6, "00H06H"),
            (7, "07H12H"),
            (12, "07H12H"),
            (13, "13H18H"),
            (48, "43H48H"),
        ],
    )
    def test_place_l_echeance_dans_sa_tranche(self, lead: int, span: str) -> None:
        assert span_for_lead_time(lead) == span

    def test_refuse_une_echeance_negative(self) -> None:
        with pytest.raises(AromeError, match="négative"):
            span_for_lead_time(-1)

    def test_refuse_au_dela_de_la_portee_du_modele(self) -> None:
        with pytest.raises(AromeError, match="hors de portée"):
            span_for_lead_time(60)


class TestNoonLeadTime:
    def test_vise_la_mi_journee_du_jour_courant(self) -> None:
        run = datetime(2026, 8, 2, 0, tzinfo=UTC)
        assert noon_lead_time(run, datetime(2026, 8, 2, 0, tzinfo=UTC)) == 11

    def test_vise_la_mi_journee_du_lendemain(self) -> None:
        run = datetime(2026, 8, 2, 0, tzinfo=UTC)
        assert noon_lead_time(run, datetime(2026, 8, 3, 0, tzinfo=UTC)) == 35

    def test_refuse_une_mi_journee_anterieure_au_run(self) -> None:
        run = datetime(2026, 8, 2, 18, tzinfo=UTC)
        with pytest.raises(AromeError, match="précède"):
            noon_lead_time(run, datetime(2026, 8, 1, 0, tzinfo=UTC))


class TestNextReachableNoon:
    def test_vise_le_jour_meme_quand_le_run_le_precede(self) -> None:
        run = datetime(2026, 8, 2, 6, tzinfo=UTC)
        assert next_reachable_noon(run) == datetime(2026, 8, 2, 11, tzinfo=UTC)

    def test_bascule_au_lendemain_l_apres_midi(self) -> None:
        """Le défaut trouvé en conditions réelles : à 15 h, midi est passé.

        Viser le jour courant sans le vérifier faisait échouer toute exécution
        d'après-midi, soit la moitié des créneaux, sur une donnée qui ne se
        rattrape pas.
        """
        run = datetime(2026, 8, 2, 15, tzinfo=UTC)
        assert next_reachable_noon(run) == datetime(2026, 8, 3, 11, tzinfo=UTC)

    def test_l_echeance_qui_en_decoule_reste_dans_la_portee(self) -> None:
        for hour in RUN_HOURS:
            run = datetime(2026, 8, 2, hour, tzinfo=UTC)
            lead = noon_lead_time(run, next_reachable_noon(run))
            assert 0 <= lead <= 48
            assert span_for_lead_time(lead) in SPANS


class TestArchiveExtent:
    def test_couvre_la_france_metropolitaine_et_la_corse(self) -> None:
        """L'emprise nationale est un choix irréversible dans un sens.

        La réduire plus tard reste possible ; l'élargir rétroactivement, non —
        ce qui n'a pas été capté n'existera jamais.
        """
        assert ARCHIVE_EXTENT.min_lon <= -5.0
        assert ARCHIVE_EXTENT.max_lon >= 9.6  # Corse orientale
        assert ARCHIVE_EXTENT.min_lat <= 41.4  # pointe sud de la Corse
        assert ARCHIVE_EXTENT.max_lat >= 51.1  # Dunkerque

    def test_englobe_les_departements_du_pilote(self) -> None:
        for lon, lat in ((6.08, 43.53), (7.26, 43.71)):  # Var, Alpes-Maritimes
            assert ARCHIVE_EXTENT.min_lon <= lon <= ARCHIVE_EXTENT.max_lon
            assert ARCHIVE_EXTENT.min_lat <= lat <= ARCHIVE_EXTENT.max_lat
