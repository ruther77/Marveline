"""Configuration du microservice WireGuard."""

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class WireGuardSettings(BaseSettings):
    """Configuration du service WireGuard VPN."""

    # General
    ENV: str = "dev"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "WireGuard Service"
    APP_VERSION: str = "0.1.0"

    # Database (schema wg dans le PostgreSQL partagé)
    DATABASE_URL: str = "postgresql+psycopg2://user:password@db:5432/massacorp"

    # WireGuard server
    WG_PRIVATE_KEY: str = ""
    WG_LISTEN_PORT: int = 51820
    WG_ADDRESS: str = "10.10.0.1/24"
    WG_INTERFACE: str = "wg0"
    WG_POST_UP: str = ""
    WG_POST_DOWN: str = ""

    # WireGuard backend mode
    WG_BACKEND: str = "mock"  # "mock" pour dev/tests, "live" pour prod

    # DNS proposé aux clients
    WG_DNS: str = "1.1.1.1,8.8.8.8"

    # Endpoint public du serveur WG (IP ou domaine)
    WG_ENDPOINT: str = "vpn.marveline.com"

    # Auth inter-service
    INTERNAL_API_KEY: str = "CHANGE_ME_IN_PRODUCTION_MIN_32_CHARS"

    # Chiffrement des clés privées peers en DB
    ENCRYPTION_KEY: str = "CHANGE_ME_ENCRYPTION_KEY_32_BYTES"

    # Database Pool
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800

    # Peer defaults
    PEER_DEFAULT_KEEPALIVE: int = 25
    PEER_MAX_PER_TENANT: int = 100

    # File secrets support (*_FILE)
    _FILE_SECRET_FIELDS = [
        "DATABASE_URL",
        "WG_PRIVATE_KEY",
        "INTERNAL_API_KEY",
        "ENCRYPTION_KEY",
    ]

    _DANGEROUS_DEFAULTS = [
        "CHANGE_ME_IN_PRODUCTION_MIN_32_CHARS",
        "CHANGE_ME_ENCRYPTION_KEY_32_BYTES",
        "postgresql+psycopg2://user:password@db:5432/massacorp",
    ]

    def __init__(self, **values):
        super().__init__(**values)
        self._apply_file_overrides()

    def _apply_file_overrides(self) -> None:
        """Charge les secrets depuis les variables *_FILE si définies."""
        for field_name in self._FILE_SECRET_FIELDS:
            env_key = f"{field_name}_FILE"
            file_path = os.getenv(env_key)
            if not file_path:
                continue
            secret_value = self._read_secret_file(file_path=file_path, env_key=env_key)
            if secret_value:
                setattr(self, field_name, secret_value)

    @staticmethod
    def _read_secret_file(file_path: str, env_key: str) -> str:
        """Lit un secret depuis un fichier pointé par une variable *_FILE."""
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError as exc:
            raise ValueError(
                f"Impossible de lire {env_key}={file_path}: {exc}"
            ) from exc

    def validate_production_secrets(self) -> None:
        """Valide que les secrets ne sont pas les valeurs par défaut en production."""
        if self.ENV.lower() in ("dev", "test", "development"):
            return

        if self.INTERNAL_API_KEY in self._DANGEROUS_DEFAULTS:
            raise ValueError(
                "SECURITE CRITIQUE: INTERNAL_API_KEY utilise une valeur par défaut!"
            )

        if self.ENCRYPTION_KEY in self._DANGEROUS_DEFAULTS:
            raise ValueError(
                "SECURITE CRITIQUE: ENCRYPTION_KEY utilise une valeur par défaut!"
            )

        if not self.WG_PRIVATE_KEY:
            raise ValueError(
                "SECURITE CRITIQUE: WG_PRIVATE_KEY non définie!"
            )

        if len(self.INTERNAL_API_KEY) < 32:
            raise ValueError(
                "SECURITE: INTERNAL_API_KEY doit faire au moins 32 caractères."
            )

        if len(self.ENCRYPTION_KEY) < 32:
            raise ValueError(
                "SECURITE: ENCRYPTION_KEY doit faire au moins 32 caractères."
            )

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() in ("production", "prod")

    @property
    def is_development(self) -> bool:
        return self.ENV.lower() in ("dev", "development")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> WireGuardSettings:
    """Retourne les settings (cachées pour performance)."""
    env = os.getenv("ENV", "dev").lower()
    env_file = ".env" if env in ("dev", "development", "test") else None
    return WireGuardSettings(_env_file=env_file)
