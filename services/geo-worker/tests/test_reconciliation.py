"""Tests de la réconciliation NRT/standard — cahier §16.3, plan J10.

La partie SQL (temp table, liste blanche, verrou `reconciled_at`) s'exerce
sur la base réelle ; ici se vérifie ce qui décide **quoi** relire : le
découpage en fenêtres de cinq jours, la lecture de la disponibilité, et le
croisement disponibilité x base — y compris ce qui est écarté, qui doit
être dit et non tu.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from geo_worker.pipelines.reconciliation import (
    STANDARD_PRODUCTS,
    fetch_windows,
    parse_availability,
    plan_reconciliation,
)

AVAILABILITY_CSV = """data_id,min_date,max_date
MODIS_NRT,2026-05-01,2026-08-27
MODIS_SP,2000-11-01,2026-04-30
VIIRS_NOAA20_NRT,2026-06-01,2026-08-27
VIIRS_NOAA20_SP,2018-04-01,2026-05-31
VIIRS_NOAA21_NRT,2024-01-17,2026-08-27
VIIRS_SNPP_SP,2012-01-20,2026-04-27
"""


def stamp(day: str) -> datetime:
    return datetime.fromisoformat(f"{day}T12:00:00+00:00").astimezone(UTC)


class TestFetchWindows:
    def test_decoupe_en_fenetres_de_cinq_jours(self) -> None:
        windows = fetch_windows(date(2026, 5, 7), date(2026, 5, 31))
        assert windows == [
            (date(2026, 5, 7), 5),
            (date(2026, 5, 12), 5),
            (date(2026, 5, 17), 5),
            (date(2026, 5, 22), 5),
            (date(2026, 5, 27), 5),
        ]

    def test_le_reliquat_ne_deborde_jamais_la_borne(self) -> None:
        windows = fetch_windows(date(2026, 5, 1), date(2026, 5, 13))
        assert windows == [(date(2026, 5, 1), 5), (date(2026, 5, 6), 5), (date(2026, 5, 11), 3)]

    def test_un_seul_jour(self) -> None:
        assert fetch_windows(date(2026, 5, 1), date(2026, 5, 1)) == [(date(2026, 5, 1), 1)]

    def test_bornes_inversees(self) -> None:
        assert fetch_windows(date(2026, 5, 2), date(2026, 5, 1)) == []


class TestParseAvailability:
    def test_lit_le_csv_reel(self) -> None:
        availability = parse_availability(AVAILABILITY_CSV)
        assert availability["VIIRS_NOAA20_SP"] == (date(2018, 4, 1), date(2026, 5, 31))
        assert "VIIRS_NOAA21_SP" not in availability

    def test_ligne_illisible_ecartee_sans_bruit(self) -> None:
        availability = parse_availability("data_id,min_date,max_date\nX,pas-une-date,2026-01-01\n")
        assert availability == {}


class TestPlanReconciliation:
    def test_le_recouvrement_reel_du_26_aout(self) -> None:
        # La base du 26 août : N20 depuis le 1ᵉʳ mai, SNPP (N) depuis le
        # 1ᵉʳ mai, N21 depuis le 29 avril. Seul N20 a un standard qui
        # recouvre (jusqu'au 31 mai) ; SNPP s'arrête au 27 avril, N21 n'a
        # pas de produit standard du tout.
        plans, skipped = plan_reconciliation(
            parse_availability(AVAILABILITY_CSV),
            {
                "N20": (stamp("2026-05-01"), stamp("2026-08-26")),
                "N": (stamp("2026-05-01"), stamp("2026-08-26")),
                "N21": (stamp("2026-04-29"), stamp("2026-08-26")),
            },
        )
        assert len(plans) == 1
        plan = plans[0]
        assert plan.product == "VIIRS_NOAA20_SP"
        assert plan.satellites == ("N20",)
        assert (plan.start, plan.end) == (date(2026, 5, 1), date(2026, 5, 31))
        assert len(plan.windows) == 7  # 31 jours → 6x5 + 1
        assert any("VIIRS_NOAA21_SP" in reason for reason in skipped)
        assert any("VIIRS_SNPP_SP" in reason for reason in skipped)

    def test_modis_regroupe_ses_deux_satellites(self) -> None:
        plans, _ = plan_reconciliation(
            parse_availability(AVAILABILITY_CSV),
            {
                "Terra": (stamp("2026-04-01"), stamp("2026-04-20")),
                "Aqua": (stamp("2026-04-05"), stamp("2026-04-25")),
            },
        )
        assert len(plans) == 1
        assert plans[0].satellites == ("Aqua", "Terra")
        # La fenêtre englobe les deux satellites et s'arrête à la borne SP.
        assert (plans[0].start, plans[0].end) == (date(2026, 4, 1), date(2026, 4, 25))

    def test_satellite_inconnu_dit_pas_tu(self) -> None:
        plans, skipped = plan_reconciliation(
            parse_availability(AVAILABILITY_CSV),
            {"GOES-16": (stamp("2026-05-01"), stamp("2026-05-02"))},
        )
        assert plans == []
        assert any("GOES-16" in reason for reason in skipped)

    def test_correspondances_connues(self) -> None:
        assert STANDARD_PRODUCTS["N20"] == "VIIRS_NOAA20_SP"
        assert STANDARD_PRODUCTS["Terra"] == STANDARD_PRODUCTS["Aqua"] == "MODIS_SP"
