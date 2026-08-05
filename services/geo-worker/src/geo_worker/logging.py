"""Journalisation structurée.

Référence : cahier §23.1.

Interdits absolus dans les journaux : clés fournisseurs, payloads bruts et
coordonnées d'utilisateur. Le processeur `redact_sensitive` en est le garde-fou
mécanique — la discipline seule ne suffit pas.

**La configuration s'applique à l'import du paquet**, et non sur appel de
l'application. C'est une entorse assumée à la règle qui veut qu'un import n'ait
pas d'effet de bord, et elle a une cause précise.

Tant que `configure_logging` n'a pas tourné, structlog emploie sa configuration
par défaut : un rendu console qui, lorsque `rich` est installé — il l'est, par
la pile scientifique — met en forme les exceptions **avec les variables
locales**. Un `log.exception` sur une erreur de dépôt a ainsi imprimé en clair
la clé secrète Supabase, qui vivait dans une variable locale de la fonction
d'envoi. Le processeur d'expurgation, lui, n'était pas installé : il ne
protégeait rien.

Aucun script n'appelait `configure_logging`. Le défaut ne demandait donc pas une
faute d'inattention particulière — c'était l'état normal de tout point d'entrée
autre que l'API, y compris la chaîne d'ingestion qui tourne toutes les dix
minutes chez GitHub Actions, sur un dépôt public, avec un mot de passe de base
et une clé fournisseur dans sa portée.

Rendre la configuration automatique supprime la classe de défaut au lieu d'en
corriger une occurrence. `configure_logging` reste appelable pour ajuster le
niveau ou l'environnement — l'API le fait.
"""

from __future__ import annotations

import logging
import os
from collections.abc import MutableMapping
from typing import Any

import structlog

SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "map_key",
        "firms_map_key",
        "service_role_key",
        "supabase_service_role_key",
        "secret_key",
        "supabase_secret_key",
        "password",
        "token",
        "authorization",
        "latitude",
        "longitude",
        "user_location",
        "raw_payload",
    }
)

REDACTED = "[expurgé]"


def redact_sensitive(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Remplace toute valeur dont la clé est sensible.

    S'applique aussi aux dictionnaires imbriqués : un payload fournisseur peut
    contenir des coordonnées à plusieurs niveaux.
    """
    for key in list(event_dict):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = REDACTED
        elif isinstance(event_dict[key], dict):
            event_dict[key] = redact_sensitive(_logger, _method, event_dict[key])
    return event_dict


def configure_logging(level: str = "info", environment: str = "local") -> None:
    """Configure structlog en sortie JSON.

    Le rendu JSON n'est pas qu'une commodité d'exploitation : c'est lui qui
    écarte le formateur d'exceptions de `rich`, seul responsable du rendu des
    variables locales. `format_exc_info` produit la trace standard de Python,
    qui porte les lignes et non leur contexte.
    """
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )

    # `httpx` journalise « HTTP Request: GET <url> » à chaque appel, en INFO.
    # Anodin pour la plupart des fournisseurs, inacceptable pour FIRMS : l'API
    # Area porte la clé **dans le chemin** de l'URL. Le connecteur prend soin de
    # ne jamais l'écrire — la bibliothèque le faisait à sa place, à chaque
    # requête et non seulement en cas d'erreur, donc dans les journaux d'un
    # dépôt public toutes les dix minutes.
    #
    # Muselé au niveau du client HTTP plutôt qu'expurgé après coup : une
    # expurgation par motif laisserait passer la prochaine URL porteuse de
    # secret. Les erreurs de transport remontent toujours, en WARNING.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_sensitive,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )

    structlog.contextvars.bind_contextvars(service="geo-worker", environment=environment)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]


# Configuration d'office, à l'import du paquet. Voir l'en-tête du module : sans
# elle, tout point d'entrée autre que l'API imprime les variables locales de la
# pile en cas d'exception, secrets compris. Un point d'entrée qui veut d'autres
# réglages rappelle `configure_logging` — l'appel est idempotent.
configure_logging(
    level=os.environ.get("LOG_LEVEL", "info"),
    environment=os.environ.get("ENVIRONMENT", "local"),
)
