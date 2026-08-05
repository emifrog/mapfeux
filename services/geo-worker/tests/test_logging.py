"""Journalisation : expurgation et absence de variables locales — cahier §23.1.

Ces tests existent à cause d'une fuite réelle. Un dépôt Storage refusé a fait
imprimer, dans la trace de `log.exception`, le contenu des variables locales de
la fonction d'envoi — dont la clé secrète Supabase, en clair.

La cause n'était pas la trace mais **l'absence de configuration** : aucun script
n'appelait `configure_logging`, et structlog appliquait donc sa configuration
par défaut, qui met en forme les exceptions avec `rich` et ses variables
locales. Le processeur d'expurgation n'était pas installé non plus.

Le paquet se configure désormais à l'import. Ce qui suit vérifie qu'il l'est
resté.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any

import pytest
import structlog

from geo_worker.logging import REDACTED, configure_logging, get_logger, redact_sensitive

SECRET = "sb_secret_valeur_qui_ne_doit_jamais_paraitre"


class TestExpurgation:
    def test_remplace_les_cles_sensibles(self) -> None:
        event = redact_sensitive(None, "info", {"secret_key": SECRET, "job": "arome"})
        assert event["secret_key"] == REDACTED
        assert event["job"] == "arome"

    def test_descend_dans_les_dictionnaires_imbriques(self) -> None:
        # Un payload fournisseur porte des coordonnées à plusieurs niveaux.
        event = redact_sensitive(
            None, "info", {"metrics": {"map_key": "abc", "latitude": 43.5, "lignes": 12}}
        )
        assert event["metrics"]["map_key"] == REDACTED
        assert event["metrics"]["latitude"] == REDACTED
        assert event["metrics"]["lignes"] == 12

    def test_couvre_les_secrets_du_projet(self) -> None:
        for cle in ("supabase_secret_key", "firms_map_key", "password", "authorization"):
            assert redact_sensitive(None, "info", {cle: "x"})[cle] == REDACTED


class TestConfigurationDOffice:
    """L'importer suffit : aucun point d'entrée n'a à y penser."""

    def test_l_expurgation_est_installee_des_l_import(self) -> None:
        assert redact_sensitive in structlog.get_config()["processors"]

    def test_le_rendu_est_json_et_non_console(self) -> None:
        # C'est le rendu console qui appelle le formateur d'exceptions de
        # `rich` — celui qui déroule les variables locales.
        processors = structlog.get_config()["processors"]
        assert any(isinstance(p, structlog.processors.JSONRenderer) for p in processors)
        assert not any(isinstance(p, structlog.dev.ConsoleRenderer) for p in processors)

    def test_les_exceptions_passent_par_le_formateur_standard(self) -> None:
        assert structlog.processors.format_exc_info in structlog.get_config()["processors"]

    def test_le_client_http_ne_journalise_plus_les_url(self) -> None:
        # `httpx` écrit « HTTP Request: GET <url> » en INFO. L'URL de l'API Area
        # de FIRMS porte la clé dans son chemin : la ligne fuitait à chaque
        # requête, pas seulement en cas d'erreur.
        for noisy in ("httpx", "httpcore"):
            assert logging.getLogger(noisy).level >= logging.WARNING


class TestTraceSansVariablesLocales:
    """La vérification qui porte sur le comportement, pas sur la configuration."""

    @pytest.fixture
    def sortie(self) -> Any:
        """Journalise vers un tampon, puis rend la configuration d'origine."""
        flux = io.StringIO()
        precedente = structlog.get_config()
        configure_logging()
        structlog.configure(
            processors=precedente["processors"],
            wrapper_class=precedente["wrapper_class"],
            logger_factory=structlog.PrintLoggerFactory(file=flux),
            cache_logger_on_first_use=False,
        )
        yield flux
        structlog.configure(**precedente)

    def test_une_exception_ne_rend_pas_les_variables_locales(self, sortie: io.StringIO) -> None:
        logger = get_logger("test")

        def deposer() -> None:
            secret_key = SECRET  # noqa: F841 — c'est précisément ce qui fuyait
            raise RuntimeError("Dépôt refusé (400) : Bucket not found")

        try:
            deposer()
        except RuntimeError:
            logger.exception("arome.crashed")

        texte = sortie.getvalue()
        # La trace doit être là — sans elle, plus de diagnostic possible.
        assert "RuntimeError" in texte
        assert "deposer" in texte
        # Mais sans le contenu des variables de la pile.
        assert SECRET not in texte

    def test_le_secret_passe_en_argument_est_expurge(self, sortie: io.StringIO) -> None:
        get_logger("test").info("arome.upload", secret_key=SECRET, bucket="raw")
        texte = sortie.getvalue()
        assert SECRET not in texte

        # La ligne est du JSON, où l'accent d'« expurgé » est échappé : la
        # comparer telle quelle passerait à côté.
        event = json.loads(texte)
        assert event["secret_key"] == REDACTED
        assert event["bucket"] == "raw"
