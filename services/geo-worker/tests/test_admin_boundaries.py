"""Tests du connecteur de limites communales — cahier §24.1 et §24.4."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from geo_worker.providers.admin_boundaries import (
    BoundaryParseError,
    parse_feature,
    parse_feature_collection,
    source_version,
)

VERSION = "etalab-geo-api:2026-07-28"

POLYGON = {
    "type": "Polygon",
    "coordinates": [[[7.20, 43.68], [7.30, 43.68], [7.30, 43.75], [7.20, 43.75], [7.20, 43.68]]],
}


def feature(**overrides: object) -> dict[str, object]:
    properties: dict[str, object] = {
        "code": "06088",
        "nom": "Nice",
        "codeDepartement": "06",
        "codesPostaux": ["06000", "06100", "06200", "06300"],
        "centre": {"type": "Point", "coordinates": [7.2661, 43.7031]},
        "surface": 7192.0,
    }
    properties.update(overrides)
    return {"type": "Feature", "geometry": POLYGON, "properties": properties}


class TestParseFeature:
    def test_normalise_une_commune(self) -> None:
        boundary = parse_feature(feature(), VERSION)

        assert boundary.insee_code == "06088"
        assert boundary.name == "Nice"
        assert boundary.department_code == "06"
        assert boundary.postal_codes == ("06000", "06100", "06200", "06300")
        assert boundary.centroid_lon == pytest.approx(7.2661)
        # La surface est publiée en hectares.
        assert boundary.area_km2 == pytest.approx(71.92)
        assert json.loads(boundary.geometry_geojson)["type"] == "Polygon"

    def test_accepte_les_codes_corses(self) -> None:
        assert parse_feature(feature(code="2A004", codeDepartement="2A"), VERSION).insee_code == (
            "2A004"
        )

    def test_deduit_le_departement_du_code_insee(self) -> None:
        boundary = parse_feature(feature(codeDepartement=""), VERSION)
        assert boundary.department_code == "06"

    def test_rejette_un_code_insee_invalide(self) -> None:
        with pytest.raises(BoundaryParseError):
            parse_feature(feature(code="608"), VERSION)

    def test_rejette_une_commune_sans_nom(self) -> None:
        with pytest.raises(BoundaryParseError):
            parse_feature(feature(nom="  "), VERSION)

    def test_rejette_une_geometrie_non_surfacique(self) -> None:
        broken = feature()
        broken["geometry"] = {"type": "Point", "coordinates": [7.2, 43.7]}
        with pytest.raises(BoundaryParseError):
            parse_feature(broken, VERSION)

    def test_rejette_une_geometrie_absente(self) -> None:
        broken = feature()
        del broken["geometry"]
        with pytest.raises(BoundaryParseError):
            parse_feature(broken, VERSION)

    def test_centre_absent_laisse_le_calcul_a_postgis(self) -> None:
        boundary = parse_feature(feature(centre=None), VERSION)
        assert boundary.centroid_lon is None
        assert boundary.centroid_lat is None

    def test_centre_hors_bornes_est_ignore(self) -> None:
        boundary = parse_feature(
            feature(centre={"type": "Point", "coordinates": [999, 43.7]}), VERSION
        )
        assert boundary.centroid_lon is None

    def test_surface_absente_ou_nulle(self) -> None:
        assert parse_feature(feature(surface=None), VERSION).area_km2 is None
        assert parse_feature(feature(surface=0), VERSION).area_km2 is None

    def test_codes_postaux_absents(self) -> None:
        assert parse_feature(feature(codesPostaux=None), VERSION).postal_codes == ()


class TestParseFeatureCollection:
    def test_normalise_une_collection(self) -> None:
        payload = {"type": "FeatureCollection", "features": [feature(), feature(code="06004")]}
        boundaries, rejections = parse_feature_collection(payload, VERSION)

        assert len(boundaries) == 2
        assert rejections == []

    def test_rejette_les_entites_invalides_sans_interrompre(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [feature(), feature(code="invalide"), feature(code="06004")],
        }
        boundaries, rejections = parse_feature_collection(payload, VERSION)

        assert len(boundaries) == 2
        assert len(rejections) == 1
        assert "entité 1" in rejections[0]

    def test_refuse_une_reponse_sans_collection(self) -> None:
        with pytest.raises(BoundaryParseError):
            parse_feature_collection({"type": "FeatureCollection"}, VERSION)

    def test_collection_vide(self) -> None:
        boundaries, rejections = parse_feature_collection(
            {"type": "FeatureCollection", "features": []}, VERSION
        )
        assert boundaries == []
        assert rejections == []


class TestSourceVersion:
    def test_consigne_le_fournisseur_et_la_date(self) -> None:
        version = source_version(datetime(2026, 7, 28, 10, 0, tzinfo=UTC))
        # Ce n'est pas un millésime COG officiel : ADR-017.
        assert version == "etalab-geo-api:2026-07-28"
