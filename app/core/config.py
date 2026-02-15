"""Configuration de l'application CaroCorp."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from functools import lru_cache
from app.constants import Limits


class Settings(BaseSettings):
    """Configuration principale de l'application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignorer les champs extra du .env
    )

    # Application
    APP_NAME: str = "CaroCorp"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://caro:password@localhost:5433/CaroCorp"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # JWT Authentication
    JWT_SECRET: str = "dev_jwt_secret_CHANGER_EN_PROD_min32chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Limits.ACCESS_TOKEN_EXPIRE_MINUTES
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Limits.REFRESH_TOKEN_EXPIRE_DAYS

    # Redis
    REDIS_URL: str = "redis://:password@localhost:6380/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://:password@localhost:6380/1"
    CELERY_RESULT_BACKEND: str = "redis://:password@localhost:6380/2"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3002"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Security
    CSRF_SECRET: str = "dev_csrf_secret_CHANGER_EN_PROD_min32chars"
    BCRYPT_ROUNDS: int = 12

    # Argon2id (OWASP 2024+ recommended)
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST: int = 65536   # 64 MiB en KiB
    ARGON2_PARALLELISM: int = 4

    # MFA / Encryption
    ENCRYPTION_KEY: str = "dev_encryption_key_32bytes_CHANGE"  # 32 bytes pour AES-256
    MFA_ISSUER_NAME: str = "Marveline"

    # Logging & compression
    LOG_LEVEL: str = "INFO"
    GZIP_MIN_SIZE: int = 500

    @model_validator(mode='after')
    def validate_production_secrets(self) -> 'Settings':
        """Vérifie qu'aucun secret dev n'est utilisé en production.

        Raises:
            ValueError: Si des secrets dev_* sont détectés en production (DEBUG=False)
        """
        if not self.DEBUG:
            # Liste des secrets à vérifier (nom du champ, valeur par défaut dev)
            dev_secrets = [
                ('JWT_SECRET', 'dev_jwt_secret_CHANGER_EN_PROD_min32chars'),
                ('CSRF_SECRET', 'dev_csrf_secret_CHANGER_EN_PROD_min32chars'),
                ('ENCRYPTION_KEY', 'dev_encryption_key_32bytes_CHANGE'),
            ]

            violations = []
            for field_name, dev_value in dev_secrets:
                field_value = getattr(self, field_name)
                if field_value == dev_value or field_value.startswith('dev_'):
                    violations.append(field_name)

            if violations:
                raise ValueError(
                    f"SECURITE CRITIQUE: Secrets dev detectes en production: {', '.join(violations)}. "
                    f"Definir ces variables d'environnement avec des valeurs securisees."
                )

        return self


@lru_cache()
def get_settings() -> Settings:
    """Singleton pour la configuration."""
    return Settings()


settings = get_settings()
