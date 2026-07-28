"""Tests du transport FIRMS — cahier §24.4 (tests de contrats fournisseurs)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from geo_worker.providers.firms import (
    FirmsClient,
    FirmsQuotaError,
    FirmsUnavailableError,
    is_stale,
    looks_like_csv,
    most_recent_acquisition,
    parse_csv,
    split_bbox,
)
from geo_worker.providers.models import BoundingBox

CSV_BODY = """latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight
43.75210,7.12043,331.2,0.39,0.36,2026-07-27,1218,N20,VIIRS,n,2.0NRT,289.4,6.21,D
"""

FRANCE = BoundingBox(min_lon=-5.5, min_lat=41.2, max_lon=9.8, max_lat=51.2)


def client_with(handler: object) -> FirmsClient:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return FirmsClient(httpx.Client(transport=transport), map_key="clé-de-test")


class TestLooksLikeCsv:
    def test_reconnait_un_export_firms(self) -> None:
        assert looks_like_csv(CSV_BODY) is True

    def test_rejette_un_message_d_erreur(self) -> None:
        # FIRMS répond parfois 200 avec un texte d'erreur. Sans ce contrôle,
        # l'import serait déclaré réussi en n'ayant rien importé.
        assert looks_like_csv("Invalid MAP_KEY.") is False

    def test_rejette_une_reponse_vide(self) -> None:
        assert looks_like_csv("") is False


class TestFirmsClient:
    def test_refuse_une_cle_vide(self) -> None:
        with pytest.raises(ValueError, match="Clé FIRMS absente"):
            FirmsClient(httpx.Client(), map_key="   ")

    def test_recupere_le_csv_brut(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert "VIIRS_NOAA20_NRT" in str(request.url)
            assert "-5.5,41.2,9.8,51.2" in str(request.url)
            return httpx.Response(200, text=CSV_BODY)

        body = client_with(handler).fetch_area(product="VIIRS_NOAA20_NRT", bbox=FRANCE)
        assert body == CSV_BODY

    def test_signale_le_quota_avec_son_delai(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "600"}, text="quota")

        with pytest.raises(FirmsQuotaError) as excinfo:
            client_with(handler).fetch_area(product="MODIS_NRT", bbox=FRANCE)
        assert excinfo.value.retry_after_seconds == 600

    def test_quota_sans_entete_retry_after(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="quota")

        with pytest.raises(FirmsQuotaError) as excinfo:
            client_with(handler).fetch_area(product="MODIS_NRT", bbox=FRANCE)
        assert excinfo.value.retry_after_seconds is None

    def test_signale_une_erreur_serveur(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="indisponible")

        with pytest.raises(FirmsUnavailableError):
            client_with(handler).fetch_area(product="MODIS_NRT", bbox=FRANCE)

    def test_rejette_un_200_qui_n_est_pas_un_csv(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="Invalid MAP_KEY.")

        with pytest.raises(FirmsUnavailableError, match="non CSV"):
            client_with(handler).fetch_area(product="MODIS_NRT", bbox=FRANCE)

    def test_rejette_une_plage_de_jours_hors_bornes(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=CSV_BODY)

        firms = client_with(handler)
        with pytest.raises(ValueError, match="day_range"):
            firms.fetch_area(product="MODIS_NRT", bbox=FRANCE, day_range=0)
        # L'API répond 400 « Invalid day range. Expects [1..5] » au-delà de cinq.
        # La borne est vérifiée ici pour éviter un aller-retour réseau inutile.
        with pytest.raises(ValueError, match="day_range"):
            firms.fetch_area(product="MODIS_NRT", bbox=FRANCE, day_range=6)
        firms.fetch_area(product="MODIS_NRT", bbox=FRANCE, day_range=5)

    def test_ajoute_la_date_de_debut(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url).endswith("/5/2026-06-15")
            return httpx.Response(200, text=CSV_BODY)

        client_with(handler).fetch_area(
            product="VIIRS_NOAA20_NRT",
            bbox=FRANCE,
            day_range=5,
            start_date=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
        )

    def test_parcourt_tous_les_produits_configures(self) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url).split("/")[-3])
            return httpx.Response(200, text=CSV_BODY)

        results = list(
            client_with(handler).fetch_detections(
                bbox=FRANCE, products=("VIIRS_NOAA20_NRT", "MODIS_NRT")
            )
        )
        assert [product for product, _ in results] == ["VIIRS_NOAA20_NRT", "MODIS_NRT"]
        assert seen == ["VIIRS_NOAA20_NRT", "MODIS_NRT"]


class TestSplitBbox:
    def test_ne_decoupe_pas_une_petite_emprise(self) -> None:
        small = BoundingBox(min_lon=6.6, min_lat=43.4, max_lon=7.8, max_lat=44.4)
        assert len(split_bbox(small, max_span_deg=10)) == 1

    def test_decoupe_la_france_metropolitaine(self) -> None:
        # 15,3° de longitude sur 10,0° de latitude : deux colonnes, une rangée.
        assert len(split_bbox(FRANCE, max_span_deg=10)) == 2
        # À 5°, quatre colonnes et deux rangées.
        assert len(split_bbox(FRANCE, max_span_deg=5)) == 8

    def test_les_tuiles_couvrent_l_emprise_sans_trou(self) -> None:
        tiles = split_bbox(FRANCE, max_span_deg=8)
        assert min(t.min_lon for t in tiles) == pytest.approx(FRANCE.min_lon)
        assert max(t.max_lon for t in tiles) == pytest.approx(FRANCE.max_lon)
        assert min(t.min_lat for t in tiles) == pytest.approx(FRANCE.min_lat)
        assert max(t.max_lat for t in tiles) == pytest.approx(FRANCE.max_lat)

    def test_refuse_un_pas_nul(self) -> None:
        with pytest.raises(ValueError, match="max_span_deg"):
            split_bbox(FRANCE, max_span_deg=0)


class TestFreshness:
    def test_retient_l_acquisition_la_plus_recente(self) -> None:
        detections, _ = parse_csv(CSV_BODY, product="VIIRS_NOAA20_NRT")
        assert most_recent_acquisition(detections) == datetime(2026, 7, 27, 12, 18, tzinfo=UTC)

    def test_lot_vide(self) -> None:
        assert most_recent_acquisition([]) is None

    def test_latence_normale_de_firms(self) -> None:
        now = datetime(2026, 7, 27, 15, 0, tzinfo=UTC)
        # FIRMS annonce une disponibilité en général sous trois heures.
        assert is_stale(now - timedelta(hours=2), now) is False
        assert is_stale(now - timedelta(hours=8), now) is True
