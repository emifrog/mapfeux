"""Tests de la chaîne de connexion — régression sur le double encodage."""

from __future__ import annotations

import pathlib

import pytest

from geo_worker.db import (
    DsnError,
    advisory_key,
    dsn_from_env_file,
    load_env,
    normalise_dsn,
    read_env_file,
)

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


class TestAdvisoryKey:
    def test_est_stable_entre_deux_processus(self) -> None:
        """La clé ne doit pas dépendre de la graine de hachage de Python.

        `hash()` intégré est randomisé à chaque démarrage. Deux processus
        concurrents — le cas même que le verrou doit détecter — obtiendraient
        alors des clés différentes et ne se verraient pas. La valeur est donc
        figée ici : si elle change, c'est que la dérivation a changé, et les
        verrous d'une version ne protègent plus de ceux de l'autre.
        """
        assert advisory_key("ingestion") == advisory_key("ingestion")
        assert advisory_key("ingestion") == 737575022638076852

    def test_distingue_deux_noms(self) -> None:
        assert advisory_key("ingestion") != advisory_key("regroupement")

    def test_tient_dans_un_entier_signe_de_64_bits(self) -> None:
        # `pg_try_advisory_lock` attend un bigint : une clé hors bornes serait
        # refusée par PostgreSQL, pas silencieusement tronquée.
        for name in ("ingestion", "regroupement", "", "a" * 500):
            assert -(2**63) <= advisory_key(name) < 2**63


class TestLoadEnv:
    def test_lit_le_fichier_quand_il_existe(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        path = tmp_path / ".env"
        path.write_text(f"DATABASE_URL=postgresql://u:p@{HOST}\n", encoding="utf-8")
        assert load_env(path)["DATABASE_URL"] == f"postgresql://u:p@{HOST}"

    def test_l_absence_de_fichier_n_est_pas_une_erreur(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Chez un ordonnanceur, il n'y a pas de fichier — seulement des variables."""
        monkeypatch.setenv("DATABASE_URL", f"postgresql://ci:secret@{HOST}")
        assert load_env(tmp_path / "absent.env")["DATABASE_URL"] == (
            f"postgresql://ci:secret@{HOST}"
        )

    def test_l_environnement_l_emporte_sur_le_fichier(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Ordre habituel : on surcharge une valeur le temps d'une commande sans
        # toucher au fichier.
        path = tmp_path / ".env"
        path.write_text("DATABASE_URL=postgresql://fichier@h/db\n", encoding="utf-8")
        monkeypatch.setenv("DATABASE_URL", "postgresql://environnement@h/db")
        assert load_env(path)["DATABASE_URL"] == "postgresql://environnement@h/db"

    def test_dsn_signale_l_absence_des_deux_sources(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(DsnError, match="environnement"):
            dsn_from_env_file(tmp_path / "absent.env")
