"""Journalisation structurée.

Référence : cahier §23.1.

Interdits absolus dans les journaux : clés fournisseurs, payloads bruts et
coordonnées d'utilisateur. Le processeur `redact_sensitive` en est le garde-fou
mécanique — la discipline seule ne suffit pas.
"""

from __future__ import annotations

import logging
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
    """Configure structlog en sortie JSON."""
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )

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
