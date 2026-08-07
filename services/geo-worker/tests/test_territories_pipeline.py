"""Tests des territoires — cahier §13.1, FR-014 et §16.7.

La partie SQL exige une base ; ces tests couvrent ce qui se vérifie sans elle :
la slugification — qui doit reproduire les slugs déjà figés par le seed, pas
inventer une seconde convention — et la normalisation des listes de l'API.
"""

from __future__ import annotations

import pytest

from geo_worker.pipelines.territories import slugify
from geo_worker.providers.admin_boundaries import (
    BoundaryParseError,
    parse_departments_payload,
    parse_regions_payload,
)


class TestSlugify:
    def test_reproduit_le_slug_du_seed(self) -> None:
        # Le seed a figé ces deux slugs : l'algorithme doit les retrouver.
        assert slugify("Provence-Alpes-Côte d'Azur") == "provence-alpes-cote-d-azur"
        assert slugify("Alpes-Maritimes") == "alpes-maritimes"

    def test_accents_et_apostrophes(self) -> None:
        assert slugify("Île-de-France") == "ile-de-france"
        assert slugify("Côtes-d'Armor") == "cotes-d-armor"
        assert slugify("Val-d'Oise") == "val-d-oise"

    def test_espaces_multiples_et_bords(self) -> None:
        assert slugify("  Grand   Est  ") == "grand-est"

    def test_conforme_a_la_contrainte_de_forme(self) -> None:
        # territories_slug_format : ^[a-z0-9]+(?:-[a-z0-9]+)*$
        import re

        pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        for name in ("Provence-Alpes-Côte d'Azur", "Île-de-France", "Corse-du-Sud", "Ain"):
            assert pattern.match(slugify(name)), name


class TestParseRegions:
    def test_normalise_et_rejette_sans_interrompre(self) -> None:
        units, rejections = parse_regions_payload(
            [
                {"nom": "Occitanie", "code": "76"},
                {"nom": "", "code": "93"},
                {"nom": "Fantôme", "code": "ABC"},
                "pas un objet",
            ]
        )
        assert [(u.code, u.name, u.region_code) for u in units] == [("76", "Occitanie", None)]
        assert len(rejections) == 3

    def test_liste_exigee(self) -> None:
        with pytest.raises(BoundaryParseError):
            parse_regions_payload({"nom": "Occitanie"})


class TestParseDepartments:
    def test_normalise_corse_et_rattache_la_region(self) -> None:
        units, rejections = parse_departments_payload(
            [
                {"nom": "Haute-Corse", "code": "2b", "codeRegion": "94"},
                {"nom": "Var", "code": "83", "codeRegion": "93"},
            ]
        )
        assert [(u.code, u.region_code) for u in units] == [("2B", "94"), ("83", "93")]
        assert rejections == []

    def test_rejette_drom_et_region_manquante(self) -> None:
        units, rejections = parse_departments_payload(
            [
                {"nom": "La Réunion", "code": "974", "codeRegion": "04"},
                {"nom": "Nord", "code": "59", "codeRegion": ""},
            ]
        )
        assert units == []
        assert len(rejections) == 2
