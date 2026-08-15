"""Registre des runs météo : lecture des chemins, fusion des états.

Une erreur ici écrit une provenance fausse dans `meteo.model_runs` — et le
panache choisira son run sur la foi de ce registre.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from geo_worker.pipelines.meteo_runs import (
    MeteoRunError,
    merge_files,
    merge_leads,
    parse_extract_path,
    span_leads,
)


class TestSpanLeads:
    def test_premiere_tranche_analyse_comprise(self) -> None:
        # Vérifié sur l'extrait réel du 7 août : sept pas, heures 0 à 6.
        assert span_leads("00H06H") == (0, 1, 2, 3, 4, 5, 6)

    def test_tranche_courante_six_pas(self) -> None:
        # Vérifié sur l'extrait réel du 5 août : six pas, heures 19 à 24.
        assert span_leads("19H24H") == (19, 20, 21, 22, 23, 24)

    def test_refuse_une_tranche_illisible(self) -> None:
        with pytest.raises(MeteoRunError, match="illisible"):
            span_leads("0H6H")

    def test_refuse_une_tranche_inversee(self) -> None:
        with pytest.raises(MeteoRunError, match="inversée"):
            span_leads("18H13H")


class TestParseExtractPath:
    def test_lit_run_et_tranche_d_un_chemin_reel(self) -> None:
        run_at, span = parse_extract_path(
            "cold/arome/2026/08/05/2026-08-05T150000Z__19H24H__fwi.nc"
        )
        assert run_at == datetime(2026, 8, 5, 15, tzinfo=UTC)
        assert span == "19H24H"

    def test_refuse_un_chemin_sans_horodatage(self) -> None:
        with pytest.raises(MeteoRunError, match="illisible"):
            parse_extract_path("cold/arome/2026/08/05/fwi.nc")


class TestMergeLeads:
    def test_union_triee_sans_doublon(self) -> None:
        assert merge_leads([5, 6, 0], (4, 5, 7)) == [0, 4, 5, 6, 7]

    def test_les_echeances_acquises_ne_se_perdent_pas(self) -> None:
        assert merge_leads([19, 20], ()) == [19, 20]


class TestMergeFiles:
    def test_redeposer_remplace_l_entree(self) -> None:
        # `x-upsert` écrase l'objet dans le stockage : l'inventaire suit,
        # sinon il compterait deux fois un fichier qui n'existe qu'une.
        existing = [{"path": "cold/a.nc", "checksum": "ancien"}]
        merged = merge_files(existing, {"path": "cold/a.nc", "checksum": "nouveau"})
        assert merged == [{"path": "cold/a.nc", "checksum": "nouveau"}]

    def test_un_nouveau_fichier_s_ajoute(self) -> None:
        existing = [{"path": "cold/a.nc", "checksum": "x"}]
        merged = merge_files(existing, {"path": "cold/b.nc", "checksum": "y"})
        assert [item["path"] for item in merged] == ["cold/a.nc", "cold/b.nc"]
