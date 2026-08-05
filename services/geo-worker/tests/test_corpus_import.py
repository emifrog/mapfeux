"""Tests du chargement du corpus dans `fire.detections` — cahier §16.3.

Le point vérifié ici n'est pas l'écriture en base, qui appartient à PostgreSQL,
mais la **normalisation** : le corpus doit produire exactement ce que produit
l'ingestion temps réel. Une divergence — un arrondi, une table de confiance
recopiée, un nom de produit inventé — ferait calibrer sur une donnée que la
production ne produit pas, et le réglage retenu ne se transposerait à rien.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from geo_worker.pipelines.corpus_import import (
    PRODUCT_BY_SATELLITE,
    CorpusImportError,
    months_between,
    normalise_records,
    product_for,
    to_csv_row,
)
from geo_worker.providers.firms import build_provider_key, parse_row


def enregistrement(**surcharges: object) -> dict[str, object]:
    """Ligne du corpus, telle que la rend le Parquet."""
    base: dict[str, object] = {
        "latitude": 43.5123,
        "longitude": 6.2456,
        "brightness": 330.1,
        "scan": 0.4,
        "track": 0.36,
        "acq_date": "2026-04-30",
        "acq_time": "1205",
        "satellite": "N20",
        "instrument": "VIIRS",
        "confidence": "n",
        "version": "2",
        "bright_t31": 290.0,
        "frp": 12.5,
        "daynight": "D",
        "type": 0,
        "corpus": "standard",
        "fichier_source": "fire_archive_J1V-C2_781726.csv",
        "is_vegetation": True,
    }
    base.update(surcharges)
    return base


class TestProduit:
    def test_les_trois_satellites_du_corpus_sont_connus(self) -> None:
        assert set(PRODUCT_BY_SATELLITE) == {"N20", "N21", "SNPP"}

    def test_le_produit_est_celui_du_flux_temps_reel(self) -> None:
        # Délibéré : le produit entre dans la clé d'idempotence. Un nom distinct
        # pour l'archive ferait entrer deux fois toute observation que le corpus
        # et l'ingestion couvrent tous les deux — c'est exactement le cas de la
        # queue NRT du corpus, qui recouvre la période déjà ingérée.
        assert product_for("N20") == "VIIRS_NOAA20_NRT"
        assert product_for("SNPP") == "VIIRS_SNPP_NRT"

    def test_un_satellite_inconnu_arrete_le_chargement(self) -> None:
        with pytest.raises(CorpusImportError, match="sans produit FIRMS connu"):
            product_for("N22")


class TestConversionCsv:
    def test_les_valeurs_absentes_deviennent_la_chaine_vide(self) -> None:
        # L'analyseur FIRMS lit du CSV : c'est la chaîne vide, et non None, qui
        # y signifie « non renseigné ».
        row = to_csv_row(enregistrement(type=None, frp=None))
        assert row["type"] == ""
        assert row["frp"] == ""

    def test_ne_transmet_que_les_colonnes_du_format_firms(self) -> None:
        row = to_csv_row(enregistrement())
        assert "corpus" not in row
        assert "fichier_source" not in row
        assert "is_vegetation" not in row


class TestNormalisation:
    def test_la_cle_est_celle_du_flux_temps_reel(self) -> None:
        # Le test qui compte : la même observation, lue du corpus ou reçue en
        # direct, doit porter la même clé. Sans quoi le rejeu dédoublerait.
        detections, rejets = normalise_records([enregistrement()])
        assert rejets == []

        attendue = build_provider_key(
            product="VIIRS_NOAA20_NRT",
            satellite="N20",
            sensor="VIIRS",
            acquired_at=datetime(2026, 4, 30, 12, 5, tzinfo=UTC),
            latitude=43.5123,
            longitude=6.2456,
            version="2",
        )
        assert detections[0].provider_key == attendue

    def test_identique_a_l_analyseur_sur_la_meme_ligne(self) -> None:
        depuis_corpus, _ = normalise_records([enregistrement()])
        depuis_csv = parse_row(to_csv_row(enregistrement()), product="VIIRS_NOAA20_NRT")
        assert depuis_corpus[0] == depuis_csv

    def test_conserve_le_type_thermique(self) -> None:
        # Les 165 629 lignes `type = 2` sont la matière du masque des sources
        # statiques : les perdre à l'import viderait le corpus de son intérêt.
        detections, _ = normalise_records([enregistrement(type=2)])
        assert detections[0].thermal_type == "2"

    def test_une_ligne_nrt_sans_type_reste_valide(self) -> None:
        detections, rejets = normalise_records(
            [enregistrement(type=None, version="2.0NRT", corpus="nrt")]
        )
        assert rejets == []
        assert detections[0].thermal_type is None

    def test_la_version_distingue_l_archive_du_temps_reel(self) -> None:
        archive, _ = normalise_records([enregistrement(version="2")])
        direct, _ = normalise_records([enregistrement(version="2.0NRT")])
        # Deux enregistrements distincts de la même observation : FIRMS les
        # estampille différemment, et la version entre dans la clé.
        assert archive[0].provider_key != direct[0].provider_key

    def test_la_confiance_qualitative_est_ramenee_au_score_interne(self) -> None:
        detections, _ = normalise_records([enregistrement(confidence="h")])
        assert detections[0].confidence_raw == "h"
        assert detections[0].confidence_score == 0.90

    def test_une_ligne_illisible_est_comptee_et_ecartee(self) -> None:
        detections, rejets = normalise_records(
            [enregistrement(), enregistrement(latitude=None), enregistrement(acq_time="9999")]
        )
        assert len(detections) == 1
        assert len(rejets) == 2

    def test_un_satellite_inconnu_ne_passe_pas_pour_un_rejet_de_ligne(self) -> None:
        # Une ligne mal formée se compte et s'écarte ; un satellite non
        # cartographié est une lacune de configuration, qui doit arrêter.
        with pytest.raises(CorpusImportError):
            normalise_records([enregistrement(satellite="N22")])


class TestPartitions:
    def test_couvre_toutes_les_bornes_incluses(self) -> None:
        mois = list(
            months_between(
                datetime(2026, 1, 15, tzinfo=UTC),
                datetime(2026, 4, 2, tzinfo=UTC),
            )
        )
        assert [m.isoformat() for m in mois] == [
            "2026-01-01",
            "2026-02-01",
            "2026-03-01",
            "2026-04-01",
        ]

    def test_franchit_fevrier_bissextile(self) -> None:
        mois = list(
            months_between(datetime(2024, 1, 31, tzinfo=UTC), datetime(2024, 3, 1, tzinfo=UTC))
        )
        assert [m.isoformat() for m in mois] == ["2024-01-01", "2024-02-01", "2024-03-01"]

    def test_un_seul_mois(self) -> None:
        mois = list(
            months_between(datetime(2026, 6, 1, tzinfo=UTC), datetime(2026, 6, 30, tzinfo=UTC))
        )
        assert [m.isoformat() for m in mois] == ["2026-06-01"]

    def test_le_corpus_complet_couvre_cent_soixante_seize_mois(self) -> None:
        mois = list(
            months_between(
                datetime(2012, 1, 20, 1, 11, tzinfo=UTC),
                datetime(2026, 8, 2, 3, 0, tzinfo=UTC),
            )
        )
        assert len(mois) == 176
        assert mois[0].isoformat() == "2012-01-01"
        assert mois[-1].isoformat() == "2026-08-01"

    def test_refuse_une_periode_inversee(self) -> None:
        with pytest.raises(CorpusImportError, match="précède"):
            list(months_between(datetime(2026, 6, 1, tzinfo=UTC), datetime(2026, 5, 1, tzinfo=UTC)))
