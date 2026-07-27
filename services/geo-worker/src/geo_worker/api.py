"""Service HTTP interne du worker.

Référence : cahier §10.2 et §23.2.

Cette API n'est pas publique : elle sert à la supervision et au déclenchement
manuel d'un import depuis l'administration. Elle ne doit jamais être exposée
directement sur Internet.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from geo_worker import __version__
from geo_worker.config import get_settings
from geo_worker.logging import configure_logging, get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(level=settings.log_level, environment=settings.environment)

    app = FastAPI(
        title="MapFeux — worker géospatial",
        version=__version__,
        docs_url="/docs",
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Sonde de vivacité. Ne teste volontairement aucune dépendance externe."""
        return {"status": "ok", "version": __version__, "environment": settings.environment}

    @app.get("/readiness")
    async def readiness() -> dict[str, Any]:
        """Connecteurs réellement utilisables, clé par clé.

        Un connecteur sans clé est déclaré indisponible : c'est ce que la page
        publique /statut doit refléter, plutôt qu'une source silencieusement
        absente (FR-110).
        """
        return {
            "status": "ok",
            "connectors": {
                "firms": settings.firms_enabled,
                "arome": settings.meteofrance_enabled,
                "cams": settings.cams_enabled,
            },
        }

    logger.info("worker.started", version=__version__, environment=settings.environment)
    return app
