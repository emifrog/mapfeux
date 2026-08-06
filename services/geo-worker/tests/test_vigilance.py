"""Analyse du format Vigilance V6.

Les correspondances de codes viennent du descriptif technique Météo-France. Une
erreur ici publierait « orange » pour le mauvais phénomène ou le mauvais
département — exactement la désinformation que le cahier §2.4 interdit.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from geo_worker.providers.vigilance import (
    ACCESS_LIVE,
    LIVE_CARTE_URL,
    BulletinRef,
    Level,
    VigilanceClient,
    VigilanceError,
    VigilanceUnavailableError,
    api_key_from,
    department_of,
    highest_colour,
    latest_reference,
    parse_carte,
    parse_timestamp,
)


def carte(**overrides: object) -> dict[str, object]:
    """Bulletin minimal conforme, calqué sur une diffusion réelle."""
    product: dict[str, object] = {
        "warning_type": "vigilance",
        "type_cdp": "cdp_carte_externe",
        "version_vigilance": "V6",
        "version_cdp": "1.0.0",
        "update_time": "2026-07-29T14:01:05Z",
        "domain_id": "FRA",
        "global_max_color_id": "3",
        "periods": [
            {
                "echeance": "J",
                "begin_validity_time": "2026-07-29T14:00:00Z",
                "end_validity_time": "2026-07-29T22:00:00Z",
                "timelaps": {
                    "domain_ids": [
                        {
                            "domain_id": "83",
                            "max_color_id": 3,
                            "phenomenon_items": [
                                {
                                    "phenomenon_id": "1",
                                    "phenomenon_max_color_id": 3,
                                    "timelaps_items": [
                                        {
                                            "begin_time": "2026-07-29T14:00:00Z",
                                            "end_time": "2026-07-29T22:00:00Z",
                                            "color_id": 3,
                                        }
                                    ],
                                },
                                # Les crues n'ont jamais de chronologie : le
                                # descriptif l'énonce. Le niveau doit malgré
                                # tout être retenu.
                                {
                                    "phenomenon_id": "4",
                                    "phenomenon_max_color_id": 2,
                                    "timelaps_items": [],
                                },
                            ],
                        },
                        {
                            "domain_id": "8310",
                            "max_color_id": 1,
                            "phenomenon_items": [
                                {"phenomenon_id": "9", "phenomenon_max_color_id": 1}
                            ],
                        },
                    ]
                },
            }
        ],
    }
    product.update(overrides)
    return {"product": product, "meta": {"snapshot_id": "abc123"}}


class TestParseTimestamp:
    def test_accepte_le_suffixe_z(self) -> None:
        assert parse_timestamp("2026-07-29T14:01:05Z") == datetime(
            2026, 7, 29, 14, 1, 5, tzinfo=UTC
        )

    def test_accepte_le_decalage_explicite(self) -> None:
        assert parse_timestamp("2026-07-29T14:01:05+00:00") == datetime(
            2026, 7, 29, 14, 1, 5, tzinfo=UTC
        )


class TestDepartmentOf:
    def test_reconnait_un_departement(self) -> None:
        assert department_of("06") == ("06", False)

    def test_reconnait_la_corse(self) -> None:
        assert department_of("2A") == ("2A", False)
        assert department_of("2B") == ("2B", False)

    def test_reconnait_un_littoral(self) -> None:
        assert department_of("8310") == ("83", True)
        assert department_of("2A10") == ("2A", True)

    def test_le_national_ne_designe_aucun_departement(self) -> None:
        # Forcer une valeur y inventerait un rattachement.
        assert department_of("FRA") == (None, False)

    def test_une_zone_de_defense_non_plus(self) -> None:
        assert department_of("ZDF_PARIS") == (None, False)


class TestLatestReference:
    def test_retient_le_bulletin_le_plus_recent(self) -> None:
        tree = {
            "2026": {
                "07": {
                    "28": {"140100": ["CDP_CARTE_EXTERNE.json"]},
                    "29": {
                        "060100": ["CDP_CARTE_EXTERNE.json"],
                        "140100": ["CDP_CARTE_EXTERNE.json"],
                    },
                }
            }
        }
        assert latest_reference(tree) == BulletinRef("2026", "07", "29", "140100")

    def test_refuse_une_arborescence_vide(self) -> None:
        with pytest.raises(VigilanceUnavailableError, match="vide"):
            latest_reference({})

    def test_remonte_au_dernier_bulletin_portant_la_carte(self) -> None:
        """Cas rencontré en production, que les fixtures n'avaient pas prévu.

        Le produit « textes » est diffusé seul lorsque la situation l'exige, et
        il apparaît dans l'arborescence comme n'importe quelle autre diffusion.
        Exiger la carte dans la plus récente faisait échouer l'import à chaque
        bulletin de suivi, alors que la carte précédente reste valide.
        """
        tree = {
            "2026": {
                "08": {
                    "02": {
                        "141318": ["CDP_TEXTES_VIGILANCE.json"],
                        "140100": ["CDP_CARTE_EXTERNE.json"],
                    }
                }
            }
        }
        assert latest_reference(tree) == BulletinRef("2026", "08", "02", "140100")

    def test_traverse_les_jours_pour_trouver_une_carte(self) -> None:
        tree = {
            "2026": {
                "08": {"02": {"060100": ["CDP_TEXTES_VIGILANCE.json"]}},
                "07": {"31": {"140100": ["CDP_CARTE_EXTERNE.json"]}},
            }
        }
        assert latest_reference(tree) == BulletinRef("2026", "07", "31", "140100")

    def test_abandonne_apres_une_serie_sans_carte(self) -> None:
        # La carte paraît au moins deux fois par jour : n'en trouver aucune sur
        # une vingtaine de diffusions signale une panne de la source.
        tree = {
            "2026": {
                "08": {"02": {f"{hour:06d}": ["CDP_TEXTES_VIGILANCE.json"] for hour in range(25)}}
            }
        }
        with pytest.raises(VigilanceUnavailableError, match="Aucune carte"):
            latest_reference(tree)


class TestParseCarte:
    def test_lit_les_metadonnees(self) -> None:
        bulletin, _, _ = parse_carte(carte())
        assert bulletin.domain_id == "FRA"
        assert bulletin.vigilance_version == "V6"
        assert bulletin.published_at == datetime(2026, 7, 29, 14, 1, 5, tzinfo=UTC)
        assert bulletin.snapshot_id == "abc123"

    def test_retient_les_crues_malgre_une_chronologie_vide(self) -> None:
        """Le piège du format : sans cela, toute vigilance crue disparaîtrait."""
        _, levels, _ = parse_carte(carte())
        crues = [level for level in levels if level.phenomenon_id == 4]
        assert len(crues) == 1
        assert crues[0].colour == "jaune"

    def test_traduit_les_couleurs(self) -> None:
        _, levels, _ = parse_carte(carte())
        vent = next(level for level in levels if level.phenomenon_id == 1)
        assert vent.colour == "orange"
        assert vent.department_code == "83"
        assert vent.is_coastal is False

    def test_distingue_le_littoral(self) -> None:
        _, levels, _ = parse_carte(carte())
        littoral = next(level for level in levels if level.domain_id == "8310")
        assert littoral.department_code == "83"
        assert littoral.is_coastal is True

    def test_reporte_la_fenetre_de_validite(self) -> None:
        _, levels, _ = parse_carte(carte())
        assert levels[0].begin_at == datetime(2026, 7, 29, 14, 0, tzinfo=UTC)
        assert levels[0].end_at == datetime(2026, 7, 29, 22, 0, tzinfo=UTC)

    def test_rejette_une_couleur_inconnue_sans_perdre_le_reste(self) -> None:
        payload = carte()
        domains = payload["product"]["periods"][0]["timelaps"]["domain_ids"]  # type: ignore[index]
        domains[0]["phenomenon_items"][0]["phenomenon_max_color_id"] = 7

        _, levels, rejections = parse_carte(payload)

        assert any("couleur inconnue 7" in r for r in rejections)
        # Les autres niveaux du même bulletin restent lus.
        assert {level.phenomenon_id for level in levels} == {4, 9}

    def test_rejette_une_echeance_inconnue(self) -> None:
        payload = carte()
        payload["product"]["periods"].append(  # type: ignore[index]
            {
                "echeance": "J2",
                "begin_validity_time": "2026-07-30T14:00:00Z",
                "end_validity_time": "2026-07-30T22:00:00Z",
                "timelaps": {"domain_ids": []},
            }
        )
        _, _, rejections = parse_carte(payload)
        assert any("J2" in r for r in rejections)

    def test_refuse_un_produit_qui_n_est_pas_une_vigilance(self) -> None:
        payload = carte()
        payload["product"]["warning_type"] = "autre"  # type: ignore[index]
        with pytest.raises(VigilanceError, match="Produit inattendu"):
            parse_carte(payload)

    def test_refuse_un_bulletin_sans_niveau(self) -> None:
        # Un bulletin vide n'est pas « tout vert » : c'est un import à
        # diagnostiquer, pas une absence de danger à publier.
        payload = carte(periods=[])
        with pytest.raises(VigilanceError, match="sans aucun niveau"):
            parse_carte(payload)

    def test_refuse_un_champ_obligatoire_absent(self) -> None:
        payload = carte()
        del payload["product"]["update_time"]  # type: ignore[attr-defined]
        with pytest.raises(VigilanceError, match="update_time"):
            parse_carte(payload)

    def test_avant_six_heures_seul_j_est_present(self) -> None:
        """Le descriptif : pas de composante J+1 avant 06:00 locales."""
        _, levels, rejections = parse_carte(carte())
        assert {level.echeance for level in levels} == {"J"}
        assert rejections == []


class TestHighestColour:
    def make(self, colour: str) -> Level:
        moment = datetime(2026, 7, 29, 14, 0, tzinfo=UTC)
        return Level(
            domain_id="83",
            department_code="83",
            is_coastal=False,
            echeance="J",
            phenomenon_id=1,
            colour=colour,
            begin_at=moment,
            end_at=moment,
        )

    def test_suit_l_ordre_officiel(self) -> None:
        levels = [self.make("jaune"), self.make("rouge"), self.make("orange")]
        assert highest_colour(levels) == "rouge"

    def test_sans_niveau_reste_vert(self) -> None:
        assert highest_colour([]) == "vert"


class TestVoieDAcces:
    """Temps réel avec clé, dépôt d'archive sans — et jamais en silence.

    Le dépôt objet a été la voie unique jusqu'au 6 août. Sondé ce jour-là à
    9 h UTC, il s'arrêtait au bulletin du 5 août 4 h : vingt-neuf heures de
    retard, contre un seuil de péremption à vingt. La vigilance affichait donc
    « trop ancienne » en permanence — un signal exact et faux, qui apprend à
    ignorer l'indicateur.
    """

    def client(self, status: int, body: str, api_key: str | None) -> tuple[Any, list[Any]]:
        recues: list[httpx.Request] = []

        def transport(request: httpx.Request) -> httpx.Response:
            recues.append(request)
            return httpx.Response(status, text=body)

        http = httpx.Client(transport=httpx.MockTransport(transport))
        return VigilanceClient(http, api_key=api_key), recues

    def test_avec_cle_interroge_le_temps_reel(self) -> None:
        client, recues = self.client(200, '{"product":{}}', "cle-de-test")
        resultat = client.fetch_latest()
        assert resultat.access == ACCESS_LIVE
        assert resultat.is_live
        assert str(recues[0].url) == LIVE_CARTE_URL

    def test_la_cle_voyage_en_entete_jamais_dans_l_url(self) -> None:
        # Même règle que pour FIRMS, dont l'URL portait la clé dans son chemin
        # et la faisait fuiter dans les journaux (§22.2).
        client, recues = self.client(200, '{"product":{}}', "cle-secrete")
        client.fetch_latest()
        assert recues[0].headers["apikey"] == "cle-secrete"
        assert "cle-secrete" not in str(recues[0].url)

    def test_sans_cle_ne_tente_pas_le_temps_reel(self) -> None:
        # L'API répondrait 401 : transformer une configuration absente en panne
        # réseau brouillerait le diagnostic.
        client, _ = self.client(200, "{}", None)
        assert client.has_key is False
        with pytest.raises(VigilanceUnavailableError, match="Clé"):
            client.fetch_live()

    def test_une_cle_vide_vaut_une_cle_absente(self) -> None:
        # Un secret non renseigné arrive en chaîne vide chez un ordonnanceur.
        client, _ = self.client(200, "{}", "   ")
        assert client.has_key is False

    def test_une_cle_refusee_le_dit(self) -> None:
        # Une clé expirée se règle au portail, pas en relançant la tâche.
        client, _ = self.client(401, "unauthorized", "cle-perimee")
        with pytest.raises(VigilanceUnavailableError, match="refusée"):
            client.fetch_live()

    def test_le_quota_est_distingue(self) -> None:
        client, _ = self.client(429, "too many", "cle-de-test")
        with pytest.raises(VigilanceUnavailableError, match="Quota"):
            client.fetch_live()

    def test_le_corps_est_rendu_tel_quel(self) -> None:
        # Il est archivé avant analyse : le rendre déjà interprété interdirait
        # de diagnostiquer un changement de format sur la donnée reçue.
        client, _ = self.client(200, '{"product":{"warning_type":"vigilance"}}', "cle")
        assert client.fetch_latest().body == '{"product":{"warning_type":"vigilance"}}'


class TestNomDeCleParApplication:
    """Le portail délivre une clé par application, pas une clé par compte.

    « Bulletin Vigilance » et « Données Publiques Radar » en ont chacune une.
    Un nom générique unique deviendrait faux dès la seconde : on ne saurait plus
    laquelle il porte, et poser la mauvaise produit un 403 sans motif visible.
    """

    def test_le_nom_specifique_l_emporte(self) -> None:
        assert (
            api_key_from(
                {
                    "METEOFRANCE_VIGILANCE_API_KEY": "vigilance",
                    "METEOFRANCE_API_KEY": "generique",
                }
            )
            == "vigilance"
        )

    def test_le_nom_generique_reste_lu(self) -> None:
        # Déprécié, non supprimé : casser une configuration en place au milieu
        # d'une mise en service serait payer cher une cohérence de nommage.
        assert api_key_from({"METEOFRANCE_API_KEY": "heritee"}) == "heritee"

    def test_une_valeur_vide_ne_compte_pas(self) -> None:
        # Un secret non renseigné arrive en chaîne vide chez un ordonnanceur,
        # jamais en variable absente.
        assert api_key_from({"METEOFRANCE_VIGILANCE_API_KEY": "   "}) == ""

    def test_une_valeur_vide_laisse_sa_chance_au_nom_generique(self) -> None:
        assert (
            api_key_from({"METEOFRANCE_VIGILANCE_API_KEY": "", "METEOFRANCE_API_KEY": "heritee"})
            == "heritee"
        )

    def test_aucune_cle(self) -> None:
        assert api_key_from({}) == ""

    def test_la_cle_du_radar_n_est_pas_prise_pour_celle_de_la_vigilance(self) -> None:
        # Le cas qui motive tout ceci : deux clés en poche, une seule valable ici.
        assert api_key_from({"METEOFRANCE_RADAR_API_KEY": "radar"}) == ""
