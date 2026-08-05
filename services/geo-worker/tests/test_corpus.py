"""Tests des règles de fusion du corpus FIRMS — cahier §16.7 et §24.8.

R4 n'écarte aucune ligne du corpus réel : la passation entre le corpus retraité
et sa queue temps réel y est nette, le standard s'arrêtant à la mi-journée et le
NRT reprenant le lendemain matin. Une règle qui n'a jamais tourné n'est pas une
règle vérifiée — elle s'exécutera pour la première fois au second
téléchargement, quand les deux corpus se recouvriront, et personne ne pourra
plus comparer. Ces tests la font tourner.
"""

from __future__ import annotations

import pandas as pd
import pytest

from geo_worker.corpus import (
    CORPUS_PRIORITY,
    CorpusError,
    canonical_order,
    content_fingerprint,
    corpus_of,
    drop_exact_duplicates,
    drop_superseded_nrt,
    merge,
    normalise,
    standard_coverage,
)

COLONNES = [
    "latitude",
    "longitude",
    "brightness",
    "scan",
    "track",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
    "confidence",
    "version",
    "bright_t31",
    "frp",
    "daynight",
]


def ligne(
    *,
    lat: str = "43.5",
    lon: str = "6.2",
    date: str = "2026-04-30",
    heure: str = "1205",
    satellite: str = "N20",
    frp: str = "12.5",
    type_: str | None = None,
) -> dict[str, str]:
    row = {
        "latitude": lat,
        "longitude": lon,
        "brightness": "330.1",
        "scan": "0.4",
        "track": "0.4",
        "acq_date": date,
        "acq_time": heure,
        "satellite": satellite,
        "instrument": "SNPP" if satellite == "SNPP" else "VIIRS",
        "confidence": "n",
        "version": "2.0NRT",
        "bright_t31": "290.0",
        "frp": frp,
        "daynight": "D",
    }
    if type_ is not None:
        row["type"] = type_
    return row


def csv(rows: list[dict[str, str]]) -> pd.DataFrame:
    colonnes = COLONNES + (["type"] if any("type" in r for r in rows) else [])
    return pd.DataFrame(rows, columns=colonnes, dtype="object").astype("string")


def prepare(fichiers: dict[str, list[dict[str, str]]]) -> pd.DataFrame:
    parts = []
    for nom, rows in fichiers.items():
        part = csv(rows)
        part["fichier_source"] = nom
        part["corpus"] = corpus_of(nom)
        parts.append(part)
    return normalise(pd.concat(parts, ignore_index=True))


class TestCorpusOf:
    def test_reconnait_le_corpus_retraite(self) -> None:
        assert corpus_of("fire_archive_SV-C2_781728.csv") == "standard"

    def test_reconnait_la_queue_temps_reel(self) -> None:
        assert corpus_of("fire_nrt_SV-C2_781728.csv") == "nrt"

    def test_ignore_le_chemin(self) -> None:
        assert corpus_of("data/firms/brut/fire_archive_J1V-C2_781726.csv") == "standard"

    def test_refuse_un_nom_inattendu(self) -> None:
        # Mieux vaut s'arrêter que classer au hasard : un fichier mal classé
        # ferait primer la donnée non retraitée sans que rien ne le signale.
        with pytest.raises(CorpusError, match="inattendu"):
            corpus_of("detections.csv")


class TestNormalisation:
    def test_reconstruit_l_heure_sans_zero_initial(self) -> None:
        # FIRMS écrit 00 h 58 « 58 ». Lu tel quel, ce serait 58 h 00.
        d = prepare({"fire_nrt_a.csv": [ligne(date="2026-04-30", heure="58")]})
        assert d["detected_at"].iloc[0] == pd.Timestamp("2026-04-30 00:58", tz="UTC")

    def test_horodatage_toujours_en_utc(self) -> None:
        d = prepare({"fire_nrt_a.csv": [ligne()]})
        assert str(d["detected_at"].dt.tz) == "UTC"

    def test_normalise_l_instrument(self) -> None:
        d = prepare({"fire_archive_a.csv": [ligne(satellite="SNPP", type_="0")]})
        assert d["instrument"].tolist() == ["VIIRS"]

    def test_le_drapeau_vegetation_a_trois_etats(self) -> None:
        d = prepare(
            {
                "fire_archive_a.csv": [
                    ligne(type_="0", heure="0100"),
                    ligne(type_="2", heure="0200"),
                ],
                "fire_nrt_a.csv": [ligne(heure="0300")],
            }
        )
        etats = d.set_index("acq_time")["is_vegetation"]
        assert etats["0100"] is True or bool(etats["0100"]) is True
        assert bool(etats["0200"]) is False
        # Le NRT ne porte pas de type : le drapeau doit rester non renseigné, et
        # surtout pas « faux », qui affirmerait que ce n'est pas de la végétation.
        assert pd.isna(etats["0300"])

    def test_refuse_un_corpus_de_rang_inconnu(self) -> None:
        d = csv([ligne()])
        d["fichier_source"] = "fire_nrt_a.csv"
        d["corpus"] = "inconnu"
        with pytest.raises(CorpusError, match="rang de priorité"):
            normalise(d)

    def test_refuse_un_corpus_non_etiquete(self) -> None:
        with pytest.raises(CorpusError, match="étiqueté"):
            normalise(csv([ligne()]))


class TestR4Recouvrement:
    """La règle qui n'a jamais tourné sur données réelles."""

    def test_ecarte_le_nrt_couvert_par_le_standard(self) -> None:
        d = prepare(
            {
                "fire_archive_a.csv": [ligne(date="2026-04-30", heure="1205")],
                # Même satellite, antérieure à la borne : le retraitement fait foi.
                "fire_nrt_a.csv": [ligne(date="2026-04-29", heure="1300", lat="44.0")],
            }
        )
        garde, stats = drop_superseded_nrt(d)
        assert stats["nrt_ecartees_recouvrement_standard"] == 1
        assert garde["corpus"].tolist() == ["standard"]

    def test_ecarte_le_nrt_exactement_sur_la_borne(self) -> None:
        # Borne incluse : à horodatage égal, le standard couvre déjà l'instant.
        d = prepare(
            {
                "fire_archive_a.csv": [ligne(date="2026-04-30", heure="1205")],
                "fire_nrt_a.csv": [ligne(date="2026-04-30", heure="1205", lat="44.0")],
            }
        )
        _, stats = drop_superseded_nrt(d)
        assert stats["nrt_ecartees_recouvrement_standard"] == 1

    def test_conserve_le_nrt_au_dela_de_la_borne(self) -> None:
        # Le cas du corpus réel : le NRT reprend là où le standard s'arrête. Ces
        # lignes ne font pas double emploi, ce sont les seules à couvrir la
        # période. Les écarter perdrait la saison en cours.
        d = prepare(
            {
                "fire_archive_a.csv": [ligne(date="2026-04-30", heure="1205")],
                "fire_nrt_a.csv": [ligne(date="2026-05-01", heure="0158", lat="44.0")],
            }
        )
        garde, stats = drop_superseded_nrt(d)
        assert stats["nrt_ecartees_recouvrement_standard"] == 0
        assert len(garde) == 2

    def test_la_borne_est_propre_a_chaque_satellite(self) -> None:
        # SNPP s'arrête le 27 avril, N20 le 30. Une borne globale écarterait
        # trois jours de NRT de N20 qui n'ont jamais été retraités.
        d = prepare(
            {
                "fire_archive_a.csv": [
                    ligne(satellite="SNPP", date="2026-04-27", heure="1243"),
                    ligne(satellite="N20", date="2026-04-30", heure="1205"),
                ],
                "fire_nrt_a.csv": [
                    ligne(satellite="SNPP", date="2026-04-28", heure="0058", lat="44.0"),
                    ligne(satellite="N20", date="2026-04-29", heure="0058", lat="44.1"),
                ],
            }
        )
        garde, stats = drop_superseded_nrt(d)
        # Seule la ligne N20 du 29 tombe sous la borne N20 du 30.
        assert stats["nrt_ecartees_recouvrement_standard"] == 1
        assert garde.loc[garde["corpus"] == "nrt", "satellite"].tolist() == ["SNPP"]

    def test_un_satellite_sans_standard_garde_tout(self) -> None:
        # N21 : FIRMS n'en publie pas l'archive. Rien ne peut primer sur sa queue
        # temps réel, qui porte à elle seule deux saisons et demie.
        d = prepare(
            {
                "fire_archive_a.csv": [ligne(satellite="N20", date="2026-04-30")],
                "fire_nrt_a.csv": [
                    ligne(satellite="N21", date="2024-06-01", heure="0143", lat="44.0")
                ],
            }
        )
        garde, stats = drop_superseded_nrt(d)
        assert stats["nrt_ecartees_recouvrement_standard"] == 0
        assert stats["satellites_sans_standard"] == ["N21"]
        assert "N21" in garde["satellite"].tolist()

    def test_rapporte_la_borne_employee(self) -> None:
        d = prepare({"fire_archive_a.csv": [ligne(date="2026-04-30", heure="1205")]})
        _, stats = drop_superseded_nrt(d)
        assert stats["bornes_standard"]["N20"].startswith("2026-04-30T12:05")

    def test_sans_corpus_standard_la_regle_ne_fait_rien(self) -> None:
        d = prepare({"fire_nrt_a.csv": [ligne(), ligne(heure="0300")]})
        garde, stats = drop_superseded_nrt(d)
        assert stats["nrt_ecartees_recouvrement_standard"] == 0
        assert standard_coverage(d) == {}
        assert len(garde) == 2


class TestR5Doublons:
    def test_supprime_le_doublon_exact(self) -> None:
        d = prepare(
            {
                "fire_archive_a.csv": [ligne(frp="12.5", type_="0")],
                "fire_archive_b.csv": [ligne(frp="99.9", type_="0")],
            }
        )
        garde, stats = drop_exact_duplicates(d)
        assert stats["doublons_exacts_supprimes"] == 1
        assert len(garde) == 1

    def test_le_standard_l_emporte_sur_le_nrt(self) -> None:
        d = prepare(
            {
                "fire_archive_a.csv": [ligne(frp="12.5", type_="0")],
                "fire_nrt_b.csv": [ligne(frp="99.9")],
            }
        )
        garde, _ = drop_exact_duplicates(d)
        assert garde["corpus"].tolist() == ["standard"]
        assert garde["frp"].tolist() == [12.5]

    def test_la_priorite_ne_repose_pas_sur_l_alphabet(self) -> None:
        # Le tri d'origine s'appuyait sur « standard » > « nrt » dans l'ordre
        # alphabétique. Le rang explicite doit dire la même chose sans en
        # dépendre : renommer un corpus ne doit pas inverser la priorité.
        assert CORPUS_PRIORITY["standard"] < CORPUS_PRIORITY["nrt"]

    def test_departage_deux_fichiers_de_meme_rang(self) -> None:
        # À rang égal, le nom du fichier tranche — un critère fixe, là où
        # l'ordre de lecture aurait laissé le hasard décider.
        d = prepare(
            {
                "fire_archive_z.csv": [ligne(frp="99.9", type_="0")],
                "fire_archive_a.csv": [ligne(frp="12.5", type_="0")],
            }
        )
        garde, _ = drop_exact_duplicates(d)
        assert garde["fichier_source"].tolist() == ["fire_archive_a.csv"]


class TestOrdreEtEmpreinte:
    def test_l_ordre_ne_depend_pas_de_l_ordre_de_lecture(self) -> None:
        # Deux pixels acquis à la même minute par le même satellite : les seules
        # colonnes de l'ancien tri ne les départageaient pas, et leur ordre
        # suivait celui des fichiers.
        a = [ligne(lat="43.5", heure="1205"), ligne(lat="43.9", heure="1205")]
        b = list(reversed(a))
        premier = canonical_order(prepare({"fire_nrt_a.csv": a}))
        second = canonical_order(prepare({"fire_nrt_a.csv": b}))
        assert premier["latitude"].tolist() == second["latitude"].tolist()

    def test_l_empreinte_ne_depend_pas_de_l_ordre_de_lecture(self) -> None:
        a = [ligne(lat="43.5", heure="1205"), ligne(lat="43.9", heure="1205")]
        corpus_a, _ = merge({"fire_nrt_a.csv": csv(a)})
        corpus_b, _ = merge({"fire_nrt_a.csv": csv(list(reversed(a)))})
        assert content_fingerprint(corpus_a) == content_fingerprint(corpus_b)

    def test_l_empreinte_change_avec_la_donnee(self) -> None:
        base, _ = merge({"fire_nrt_a.csv": csv([ligne(frp="12.5")])})
        autre, _ = merge({"fire_nrt_a.csv": csv([ligne(frp="12.6")])})
        assert content_fingerprint(base) != content_fingerprint(autre)


class TestFusionComplete:
    def test_enchaine_les_regles_et_rend_compte(self) -> None:
        corpus, stats = merge(
            {
                "fire_archive_a.csv": csv(
                    [
                        ligne(date="2026-04-30", heure="1205", type_="0"),
                        ligne(date="2026-04-29", heure="1100", lat="43.7", type_="2"),
                    ]
                ),
                "fire_nrt_a.csv": csv(
                    [
                        # Couverte par le standard : écartée par R4.
                        ligne(date="2026-04-28", heure="0300", lat="43.8"),
                        # Au-delà de la borne : conservée.
                        ligne(date="2026-05-01", heure="0158", lat="43.9"),
                    ]
                ),
            }
        )
        assert stats["nrt_ecartees_recouvrement_standard"] == 1
        assert stats["lignes"] == 3
        assert stats["sources_statiques"] == 1
        assert stats["sans_type"] == 1
        assert len(stats["empreinte_contenu"]) == 16
        # R7 — rien n'est filtré sur le type : la source statique reste au corpus.
        assert 2 in corpus["type"].dropna().tolist()
        # La colonne de travail ne fuit pas dans le corpus publié.
        assert "corpus_rank" not in corpus.columns

    def test_refuse_un_corpus_vide(self) -> None:
        with pytest.raises(CorpusError, match="Aucun fichier"):
            merge({})
