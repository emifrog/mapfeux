"""Tests de la chaîne de connexion — régression sur le double encodage."""

from __future__ import annotations

import pathlib

import pytest

from geo_worker.db import DsnError, dsn_from_env_file, normalise_dsn, read_env_file

HOST = "db.exemple.supabase.co:5432/postgres"


class TestNormaliseDsn:
    def test_laisse_intacte_une_chaine_correcte(self) -> None:
        dsn = f"postgresql://postgres:motdepasse@{HOST}"
        assert normalise_dsn(dsn) == dsn

    def test_encode_une_arobase_du_mot_de_passe(self) -> None:
        # Sans correction, l'hôte devient « suite@db.exemple… » et la
        # résolution DNS échoue avec un message trompeur.
        assert (
            normalise_dsn(f"postgresql://postgres:debut@suite@{HOST}")
            == f"postgresql://postgres:debut%40suite@{HOST}"
        )

    def test_n_encode_pas_deux_fois(self) -> None:
        # Régression : une version encodait sans condition, transformant %40 en
        # %2540 et faisant échouer l'authentification sans cause visible.
        dsn = f"postgresql://postgres:debut%40suite@{HOST}"
        assert normalise_dsn(dsn) == dsn
        assert "%2540" not in normalise_dsn(dsn)

    def test_idempotence(self) -> None:
        once = normalise_dsn(f"postgresql://postgres:a@b@{HOST}")
        assert normalise_dsn(once) == once

    def test_laisse_intacte_une_chaine_sans_schema(self) -> None:
        assert normalise_dsn("pas-une-url") == "pas-une-url"

    def test_conserve_le_chemin_de_base(self) -> None:
        assert normalise_dsn(f"postgresql://u:a@b@{HOST}").endswith("/postgres")


class TestReadEnvFile:
    def test_lit_les_paires(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / ".env"
        path.write_text("A=1\n# commentaire\n\nB = deux \n", encoding="utf-8")
        assert read_env_file(path) == {"A": "1", "B": "deux"}

    def test_conserve_les_egaux_de_la_valeur(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / ".env"
        path.write_text("DATABASE_URL=postgresql://u:p=q@h/db\n", encoding="utf-8")
        assert read_env_file(path)["DATABASE_URL"] == "postgresql://u:p=q@h/db"

    def test_fichier_absent(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(DsnError, match="introuvable"):
            read_env_file(tmp_path / "absent.env")


class TestDsnFromEnvFile:
    def test_retourne_une_chaine_normalisee(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / ".env"
        path.write_text(f"DATABASE_URL=postgresql://u:a@b@{HOST}\n", encoding="utf-8")
        assert dsn_from_env_file(path) == f"postgresql://u:a%40b@{HOST}"

    def test_variable_absente(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / ".env"
        path.write_text("AUTRE=1\n", encoding="utf-8")
        with pytest.raises(DsnError, match="DATABASE_URL absente"):
            dsn_from_env_file(path)
