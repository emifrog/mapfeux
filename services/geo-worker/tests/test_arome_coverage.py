"""Couverture de fenêtre : quelles échéances, quelles tranches, quelle couture.

Une erreur de borne ici se paie en silence : une échéance oubliée tronque le
panache d'une heure, une tranche comptée présente à tort le fait calculer sur
du vide.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
import xarray as xr

from geo_worker.pipelines.arome_coverage import (
    coverage_checksum,
    merge_wind_datasets,
    missing_spans,
    spans_for_leads,
    window_leads,
)

RUN_AT = datetime(2026, 8, 25, 0, tzinfo=UTC)


def extrait(hours: list[int], value: float) -> xr.Dataset:
    """Extrait synthétique d'une tranche : quelques pas horaires."""
    shape = (len(hours), 2, 2)
    return xr.Dataset(
        {
            "u10": (("step", "latitude", "longitude"), np.full(shape, value)),
            "v10": (("step", "latitude", "longitude"), np.zeros(shape)),
        },
        coords={
            "step": np.array([h * 3_600_000_000_000 for h in hours], dtype="timedelta64[ns]"),
            "latitude": [45.05, 45.0],
            "longitude": [5.0, 5.05],
        },
    )


class TestWindowLeads:
    def test_fenetre_nominale_bornee_a_l_heure(self) -> None:
        # 02:30 → 08:30 depuis un run de minuit : les échéances 2 à 9,
        # l'heure entamée comptant des deux côtés.
        leads = window_leads(
            RUN_AT,
            RUN_AT + timedelta(hours=2, minutes=30),
            RUN_AT + timedelta(hours=8, minutes=30),
        )
        assert leads == tuple(range(2, 10))

    def test_fenetre_anterieure_au_run_est_ecretee(self) -> None:
        leads = window_leads(RUN_AT, RUN_AT - timedelta(hours=2), RUN_AT + timedelta(hours=1))
        assert leads == (0, 1)

    def test_fenetre_au_dela_de_la_portee_est_ecretee(self) -> None:
        leads = window_leads(RUN_AT, RUN_AT + timedelta(hours=47), RUN_AT + timedelta(hours=60))
        assert leads[0] == 47
        assert leads[-1] == 48

    def test_fenetre_hors_de_portee_est_vide(self) -> None:
        assert (
            window_leads(RUN_AT, RUN_AT + timedelta(hours=50), RUN_AT + timedelta(hours=52)) == ()
        )
        assert window_leads(RUN_AT, RUN_AT - timedelta(hours=5), RUN_AT - timedelta(hours=1)) == ()

    def test_fenetre_inversee_est_vide(self) -> None:
        assert window_leads(RUN_AT, RUN_AT + timedelta(hours=2), RUN_AT + timedelta(hours=1)) == ()


class TestSpansForLeads:
    def test_traverse_les_tranches_sans_doublon(self) -> None:
        # 3..10 traverse la première tranche et la deuxième.
        assert spans_for_leads(tuple(range(3, 11))) == ("00H06H", "07H12H")

    def test_une_seule_tranche_quand_tout_y_tient(self) -> None:
        assert spans_for_leads((19, 20, 24)) == ("19H24H",)


class TestMissingSpans:
    def test_une_tranche_partielle_est_manquante_en_bloc(self) -> None:
        # Le registre tient 0..6 : la première tranche est là, la deuxième
        # manque entière même si rien ne manque « à moitié » — un fichier se
        # dépose entier.
        assert missing_spans(("00H06H", "07H12H"), list(range(0, 7))) == ("07H12H",)

    def test_rien_ne_manque_quand_tout_est_tenu(self) -> None:
        assert missing_spans(("00H06H",), list(range(0, 7))) == ()

    def test_une_echeance_absente_suffit(self) -> None:
        # 0..5 sans le 6 : la tranche 00H06H n'est pas réellement sur disque.
        assert missing_spans(("00H06H",), list(range(0, 6))) == ("00H06H",)


class TestMergeWindDatasets:
    def test_coud_deux_tranches_dans_l_ordre(self) -> None:
        merged = merge_wind_datasets([extrait([7, 8, 9], 2.0), extrait([0, 1, 2], 1.0)])
        hours = [int(s / np.timedelta64(1, "h")) for s in merged["step"].values]
        assert hours == [0, 1, 2, 7, 8, 9]
        # Les valeurs suivent leur tranche d'origine à travers la couture.
        assert (
            float(merged["u10"].sel(step=np.timedelta64(1, "h")).isel(latitude=0, longitude=0))
            == 1.0
        )
        assert (
            float(merged["u10"].sel(step=np.timedelta64(8, "h")).isel(latitude=0, longitude=0))
            == 2.0
        )

    def test_dedouble_une_echeance_en_double(self) -> None:
        merged = merge_wind_datasets([extrait([0, 1], 1.0), extrait([1, 2], 9.0)])
        hours = [int(s / np.timedelta64(1, "h")) for s in merged["step"].values]
        assert hours == [0, 1, 2]
        # La première occurrence fait foi.
        assert (
            float(merged["u10"].sel(step=np.timedelta64(1, "h")).isel(latitude=0, longitude=0))
            == 1.0
        )

    def test_refuse_le_vide(self) -> None:
        with pytest.raises(ValueError, match="Aucun extrait"):
            merge_wind_datasets([])


class TestCoverageChecksum:
    def test_stable_et_ordonnee_par_echeance(self) -> None:
        files = (
            {"checksum": "bbb", "leads": [7, 8]},
            {"checksum": "aaa", "leads": [0, 1]},
        )
        assert coverage_checksum(files) == "aaa|bbb"
        assert coverage_checksum(tuple(reversed(files))) == "aaa|bbb"
