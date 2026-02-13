"""Configuration de l'application CaroCorp."""
from pydantic_settings import BaseSettings, SettingsConfigDict
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
    SESSION_EXPIRE_SECONDS: int = Limits.SESSION_TIMEOUT_SECONDS

    # Celery
    CELERY_BROKER_URL: str = "redis://:password@localhost:6380/1"
    CELERY_RESULT_BACKEND: str = "redis://:password@localhost:6380/2"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3002"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Security
    CSRF_SECRET: str = "dev_csrf_secret_CHANGER_EN_PROD_min32chars"
    BCRYPT_ROUNDS: int = 12


@lru_cache()
def get_settings() -> Settings:
    """Singleton pour la configuration."""
    return Settings()


settings = get_settings()
