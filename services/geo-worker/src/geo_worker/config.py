"""Configuration du worker.

Référence : cahier annexe C et §14.3.

Aucune clé fournisseur n'est écrite dans le code ni dans la base : elles sont
lues depuis l'environnement au démarrage, et leur absence rend le connecteur
correspondant indisponible plutôt que silencieusement inopérant.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables d'environnement du service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="local")
    log_level: str = Field(default="info")

    # Base de données ---------------------------------------------------------
    database_url: SecretStr
    supabase_url: str
    supabase_service_role_key: SecretStr
    supabase_storage_bucket_raw: str = "raw"
    supabase_storage_bucket_derived: str = "derived"

    # Fournisseurs ------------------------------------------------------------
    firms_map_key: SecretStr | None = None
    meteofrance_api_key: SecretStr | None = None
    copernicus_url: str | None = None
    copernicus_key: SecretStr | None = None

    # Observabilité -----------------------------------------------------------
    otel_exporter_otlp_endpoint: str | None = None
    sentry_dsn: str | None = None

    @property
    def firms_enabled(self) -> bool:
        """Un connecteur sans clé est déclaré indisponible, pas ignoré."""
        return self.firms_map_key is not None

    @property
    def meteofrance_enabled(self) -> bool:
        return self.meteofrance_api_key is not None

    @property
    def cams_enabled(self) -> bool:
        return self.copernicus_key is not None and self.copernicus_url is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Instance unique, chargée au premier appel."""
    return Settings()
