"""Tests du connecteur FIRMS — cahier §24.1 et §24.4."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from geo_worker.providers.firms import (
    FirmsParseError,
    build_provider_key,
    deduplicate,
    normalize_confidence,
    parse_acquisition_time,
    parse_csv,
)

VIIRS_CSV = """latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight
43.75210,7.12043,331.2,0.39,0.36,2026-07-27,1218,N20,VIIRS,n,2.0NRT,289.4,6.21,D
43.75310,7.12143,345.9,0.39,0.36,2026-07-27,1218,N20,VIIRS,h,2.0NRT,291.0,11.80,D
"""

MODIS_CSV = """latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_t31,frp,daynight,type
43.7521,7.1204,320.5,1.1,1.0,2026-07-27,45,Terra,MODIS,78,6.1NRT,295.1,15.3,N,0
"""


class TestParseAcquisitionTime:
    def test_combine_date_et_heure_en_utc(self) -> None:
        result = parse_acquisition_time("2026-07-27", "1218")
        assert result == datetime(2026, 7, 27, 12, 18, tzinfo=UTC)

    def test_complete_les_heures_sans_zero_initial(self) -> None:
        # FIRMS transmet « 45 » pour 00:45.
        assert parse_acquisition_time("2026-07-27", "45") == datetime(
            2026, 7, 27, 0, 45, tzinfo=UTC
        )

    def test_rejette_une_heure_hors_bornes(self) -> None:
        with pytest.raises(FirmsParseError):
            parse_acquisition_time("2026-07-27", "2599")

    def test_rejette_une_date_illisible(self) -> None:
        with pytest.raises(FirmsParseError):
            parse_acquisition_time("27/07/2026", "1218")


class TestNormalizeConfidence:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("l", 0.25), ("n", 0.60), ("h", 0.90), ("H", 0.90)],
    )
    def test_viirs_qualitatif(self, raw: str, expected: float) -> None:
        assert normalize_confidence(raw, "VIIRS") == (raw, expected)

    def test_modis_pourcentage(self) -> None:
        assert normalize_confidence("78", "MODIS") == ("78", 0.78)

    def test_valeur_absente(self) -> None:
        assert normalize_confidence(None, "VIIRS") == (None, None)
        assert normalize_confidence("  ", "MODIS") == (None, None)

    def test_format_inattendu_conserve_la_valeur_brute(self) -> None:
        # La détection reste valide : seule sa pondération devient inconnue.
        assert normalize_confidence("très forte", "MODIS") == ("très forte", None)

    def test_pourcentage_hors_bornes(self) -> None:
        assert normalize_confidence("140", "MODIS") == ("140", None)


class TestProviderKey:
    def _key(self, **overrides: object) -> str:
        params: dict[str, object] = {
            "product": "VIIRS_NOAA20_NRT",
            "satellite": "N20",
            "sensor": "VIIRS",
            "acquired_at": datetime(2026, 7, 27, 12, 18, tzinfo=UTC),
            "latitude": 43.75210,
            "longitude": 7.12043,
            "version": "2.0NRT",
        }
        params.update(overrides)
        return build_provider_key(**params)  # type: ignore[arg-type]

    def test_est_stable_entre_deux_appels(self) -> None:
        assert self._key() == self._key()

    def test_change_avec_la_position(self) -> None:
        assert self._key() != self._key(latitude=43.75310)

    def test_change_avec_l_heure(self) -> None:
        assert self._key() != self._key(acquired_at=datetime(2026, 7, 27, 12, 19, tzinfo=UTC))

    def test_change_avec_le_produit(self) -> None:
        assert self._key() != self._key(product="VIIRS_SNPP_NRT")

    def test_ignore_le_bruit_de_formatage_des_coordonnees(self) -> None:
        # 43.75210 et 43.752100000001 désignent la même observation.
        assert self._key() == self._key(latitude=43.752100000001)

    def test_refuse_une_date_naive(self) -> None:
        with pytest.raises(FirmsParseError):
            self._key(acquired_at=datetime(2026, 7, 27, 12, 18))  # noqa: DTZ001


class TestParseCsv:
    def test_normalise_un_export_viirs(self) -> None:
        detections, rejections = parse_csv(VIIRS_CSV, product="VIIRS_NOAA20_NRT")

        assert rejections == []
        assert len(detections) == 2

        first = detections[0]
        assert first.sensor == "VIIRS"
        assert first.satellite == "N20"
        assert first.acquired_at == datetime(2026, 7, 27, 12, 18, tzinfo=UTC)
        assert first.confidence_score == 0.60
        assert first.frp_mw == 6.21
        assert first.day_night == "D"
        assert first.brightness == 331.2
        # Le payload fournisseur est conservé intact (ADR-004).
        assert first.raw_payload["bright_ti5"] == "289.4"

    def test_normalise_un_export_modis(self) -> None:
        detections, rejections = parse_csv(MODIS_CSV, product="MODIS_NRT")

        assert rejections == []
        assert len(detections) == 1
        detection = detections[0]
        assert detection.sensor == "MODIS"
        assert detection.confidence_score == 0.78
        assert detection.thermal_type == "0"
        assert detection.acquired_at == datetime(2026, 7, 27, 0, 45, tzinfo=UTC)

    def test_rejette_les_lignes_invalides_sans_interrompre(self) -> None:
        corrupted = VIIRS_CSV + "999,7.12,331,0.4,0.4,2026-07-27,1218,N20,VIIRS,n,2.0NRT,289,6,D\n"
        detections, rejections = parse_csv(corrupted, product="VIIRS_NOAA20_NRT")

        assert len(detections) == 2
        assert len(rejections) == 1
        assert "ligne 4" in rejections[0]

    def test_export_vide(self) -> None:
        header = VIIRS_CSV.splitlines()[0] + "\n"
        detections, rejections = parse_csv(header, product="VIIRS_NOAA20_NRT")
        assert detections == []
        assert rejections == []


class TestDeduplicate:
    def test_supprime_les_republications_dans_un_meme_lot(self) -> None:
        detections, _ = parse_csv(VIIRS_CSV + VIIRS_CSV.splitlines()[1] + "\n", product="X")
        assert len(detections) == 3

        unique = list(deduplicate(detections))
        assert len(unique) == 2
