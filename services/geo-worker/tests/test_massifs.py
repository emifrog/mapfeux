"""Tests de la capture des massifs — ADR-026, cahier §9.2.

Les charges utiles nominales sont **copiées du site réel** (28 août 2026) :
le JSON quotidien du Var, un extrait de son référentiel GeoJSON, et les
deux formes de libellés officiels — tableau indexé (83) et clés nommées
(06). Une anomalie est rejetée et comptée, jamais silencieuse.
"""

from __future__ import annotations

import pytest

from geo_worker.pipelines.massif_levels import assemble_levels
from geo_worker.providers.massifs import (
    daily_levels_url,
    parse_daily_levels,
    parse_level_labels,
    parse_massif_names,
)

#: Extrait réel du JSON quotidien du Var, 28 août 2026.
DAILY_JSON = """
{ "massifs": { "831": [2, 0], "832": [2, 0], "838": [2, 0] },
  "zm": { "831": 2, "832": 2 } }
"""

#: Extrait réel de massifs_centre.js (Var).
CENTRE_JS = """
var massifs_centre = [
{ "type": "Feature", "properties": { "ID": 838, "level": 0, "procedure": 0, "NOM_MASSIF": "ESTEREL", "dept": 83 }, "geometry": { "type": "Point", "coordinates": [ 6.76, 43.52 ] } },
{ "type": "Feature", "properties": { "ID": 831, "level": 0, "procedure": 0, "NOM_MASSIF": "MONTS TOULONNAIS", "dept": 83 }, "geometry": { "type": "Point", "coordinates": [ 5.98, 43.19 ] } }
];
"""

#: Forme du Var : tableau `legend` indexé, la queue compose le niveau 5.
TRANSLATION_VAR = """
{ "legend": ["Pas de données", "Accès et travaux autorisés",
  "Accès autorisé, travaux encadrés", "Accès déconseillé",
  "Accès interdit hors ZAPEF",
  "Accès et travaux interdits dans tous massifs forestiers, ", "EXTRÊME ",
  "vigilance requise"] }
"""

#: Forme des Alpes-Maritimes : clés nommées.
TRANSLATION_06 = """
{ "no_data": "Pas de données", "green_access": "Accès autorisé, travaux autorisés",
  "yellow_access": "Accès déconseillé, travaux autorisés de 5h à 13h",
  "orange_access": "Accès déconseillé, travaux interdits",
  "red_access": "Accès interdit, travaux interdits" }
"""


class TestParseDailyLevels:
    def test_lit_le_json_reel(self) -> None:
        levels = parse_daily_levels(DAILY_JSON)
        assert levels == {"831": (2, 0), "832": (2, 0), "838": (2, 0)}

    def test_refuse_un_niveau_hors_echelle(self) -> None:
        with pytest.raises(ValueError, match="hors échelle"):
            parse_daily_levels('{"massifs": {"831": [7, 0]}}')

    def test_refuse_un_document_sans_massifs(self) -> None:
        with pytest.raises(ValueError, match="massifs"):
            parse_daily_levels('{"zm": {}}')


class TestParseMassifNames:
    def test_lit_le_geojson_embarque(self) -> None:
        names = parse_massif_names(CENTRE_JS)
        assert names == {"838": "ESTEREL", "831": "MONTS TOULONNAIS"}

    def test_refuse_une_page_restructuree(self) -> None:
        with pytest.raises(ValueError, match="restructurée"):
            parse_massif_names("var massifs_centre = [];")


class TestParseLevelLabels:
    def test_forme_tableau_du_var(self) -> None:
        labels = parse_level_labels(TRANSLATION_VAR)
        assert labels[1] == "Accès et travaux autorisés"
        assert labels[4] == "Accès interdit hors ZAPEF"
        # La queue du tableau compose le libellé du niveau 5 exceptionnel.
        assert labels[5] == (
            "Accès et travaux interdits dans tous massifs forestiers, EXTRÊME vigilance requise"
        )

    def test_forme_nommee_des_alpes_maritimes(self) -> None:
        labels = parse_level_labels(TRANSLATION_06)
        assert labels[1] == "Accès autorisé, travaux autorisés"
        assert labels[4] == labels[5] == "Accès interdit, travaux interdits"

    def test_aucune_forme_connue_rend_vide(self) -> None:
        # Sans libellés, le niveau s'affichera nu — jamais sous un libellé
        # inventé par MapFeux.
        assert parse_level_labels("{}") == {}


class TestAssembleLevels:
    def test_le_referentiel_nu_du_06_se_croise_par_prefixe(self) -> None:
        # Le JSON quotidien du 06 dit « 61 »… « 67 » ; son référentiel dit
        # 1…7. Le repli de préfixe les fait se rencontrer.
        assembled, rejections = assemble_levels(
            {"61": (1, 0), "67": (1, 0)},
            {"1": "Esterel - Tanneron", "7": "Moyen Var - Préalpes de Grasse"},
            parse_level_labels(TRANSLATION_06),
            department_path="6",
        )
        assert [item.massif_name for item in assembled] == [
            "Esterel - Tanneron",
            "Moyen Var - Préalpes de Grasse",
        ]
        assert rejections == []
        assert assembled[0].level_label == "Accès autorisé, travaux autorisés"

    def test_croise_niveaux_noms_et_libelles(self) -> None:
        levels = parse_daily_levels(DAILY_JSON)
        names = parse_massif_names(CENTRE_JS)
        labels = parse_level_labels(TRANSLATION_VAR)
        assembled, rejections = assemble_levels(levels, names, labels)
        # 832 est au JSON quotidien mais pas dans l'extrait du référentiel :
        # rejeté et compté — un numéro sans nom n'informe personne.
        assert [item.massif_name for item in assembled] == ["MONTS TOULONNAIS", "ESTEREL"]
        assert assembled[0].level == 2
        assert assembled[0].level_label == "Accès autorisé, travaux encadrés"
        assert any("832" in reason for reason in rejections)


class TestUrls:
    def test_le_06_perd_son_zero(self) -> None:
        assert daily_levels_url("06", "20260828").endswith("/static/6/import_data/20260828.json")
        assert daily_levels_url("83", "20260828").endswith("/static/83/import_data/20260828.json")
