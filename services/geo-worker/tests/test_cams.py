"""Construction des demandes CAMS et manipulation des bruts.

Une erreur de dialecte ici ne se voit pas : l'ADS répondrait un fichier
valide sur la mauvaise emprise, le mauvais niveau ou le mauvais modèle — un
import réussi en apparence, faux en substance.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

import pytest

from geo_worker.pipelines.cams_import import default_run_at, unwrap_netcdf
from geo_worker.providers.cams import POLLUTANTS, CamsError, CamsRequest

RUN_AT = datetime(2026, 8, 25, 0, tzinfo=UTC)


class TestCamsRequest:
    def test_le_dialecte_du_jeu(self) -> None:
        request = CamsRequest(pollutant="pm2_5", run_at=RUN_AT, lead_hours=(0, 1, 2))
        payload = request.payload()
        assert payload["variable"] == ["particulate_matter_2.5um"]
        assert payload["model"] == ["ensemble"]
        assert payload["level"] == ["0"]
        assert payload["date"] == ["2026-08-25/2026-08-25"]
        assert payload["leadtime_hour"] == ["0", "1", "2"]
        # area est [nord, ouest, sud, est] — l'ordre ADS, pas le nôtre.
        assert payload["area"] == [51.5, -5.8, 41.0, 10.2]

    def test_les_deux_polluants_du_fr_120(self) -> None:
        assert set(POLLUTANTS) == {"pm2_5", "pm10"}

    def test_chemin_de_depot_date_et_lisible(self) -> None:
        request = CamsRequest(pollutant="pm10", run_at=RUN_AT, lead_hours=tuple(range(25)))
        assert request.object_path == (
            "cams/2026/08/25/cams-europe__ensemble__pm10__2026-08-25T000000Z__H0-H24.nc"
        )

    def test_refuse_un_polluant_inconnu(self) -> None:
        with pytest.raises(CamsError, match="Polluant"):
            CamsRequest(pollutant="ozone", run_at=RUN_AT, lead_hours=(0,))

    def test_refuse_une_echeance_hors_produit(self) -> None:
        with pytest.raises(CamsError, match="portée"):
            CamsRequest(pollutant="pm10", run_at=RUN_AT, lead_hours=(0, 120))

    def test_refuse_un_run_hors_grille(self) -> None:
        with pytest.raises(CamsError, match="00 UTC"):
            CamsRequest(
                pollutant="pm10",
                run_at=datetime(2026, 8, 25, 6, tzinfo=UTC),
                lead_hours=(0,),
            )


class TestUnwrapNetcdf:
    def test_un_netcdf_nu_passe_tel_quel(self) -> None:
        payload = b"CDF\x01contenu"
        assert unwrap_netcdf(payload) == payload

    def test_un_zip_rend_son_unique_membre(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("data.nc", b"CDF\x01dedans")
        assert unwrap_netcdf(buffer.getvalue()) == b"CDF\x01dedans"

    def test_un_zip_ambigu_est_refuse(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("a.nc", b"x")
            archive.writestr("b.nc", b"y")
        with pytest.raises(ValueError, match="au lieu d'un"):
            unwrap_netcdf(buffer.getvalue())


class TestDefaultRunAt:
    def test_le_matin_tot_sert_la_veille(self) -> None:
        now = datetime(2026, 8, 25, 6, 30, tzinfo=UTC)
        assert default_run_at(now) == datetime(2026, 8, 24, 0, tzinfo=UTC)

    def test_apres_publication_sert_le_jour(self) -> None:
        now = datetime(2026, 8, 25, 9, 30, tzinfo=UTC)
        assert default_run_at(now) == RUN_AT
