"""Tests unitaires pour app/core/config.py — validation des secrets production.

Couvre CONFIG-01 : le model_validator doit rejeter les secrets dev_*
quand DEBUG=False (mode production).
"""
import pytest
from pydantic import ValidationError


class TestProductionSecretsValidation:
    """Le validator bloque le démarrage si des secrets dev sont détectés en prod."""

    def test_dev_secrets_raise_in_production(self):
        """Secrets par défaut dev_* doivent lever ValueError quand DEBUG=False."""
        from app.core.config import Settings

        with pytest.raises((ValidationError, ValueError)):
            Settings(
                DEBUG=False,
                JWT_SECRET="dev_jwt_secret_CHANGER_EN_PROD_min32chars",
                DATABASE_URL="postgresql+psycopg2://caro:pw@localhost:5432/db",
            )

    def test_strong_secrets_accepted_in_production(self):
        """Secrets forts (non dev_*) doivent être acceptés en production."""
        from app.core.config import Settings

        s = Settings(
            DEBUG=False,
            JWT_SECRET="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",  # 32 chars, no dev_
            CSRF_SECRET="z9y8x7w6v5u4t3s2r1q0p9o8n7m6l5k4",  # 32 chars, no dev_
            ENCRYPTION_KEY="12345678901234567890123456789012",    # 32 chars
            WG_INTERNAL_API_KEY="prod_key_for_wireguard_service_ok",
            DATABASE_URL="postgresql+psycopg2://caro:pw@localhost:5432/db",
            REDIS_URL="redis://:pw@localhost:6380/0",
            CELERY_BROKER_URL="redis://:pw@localhost:6380/1",
            CELERY_RESULT_BACKEND="redis://:pw@localhost:6380/2",
        )
        assert s.DEBUG is False

    def test_dev_jwt_secret_blocked(self):
        """JWT_SECRET avec préfixe dev_ doit être bloqué en production."""
        from app.core.config import Settings

        with pytest.raises((ValidationError, ValueError)):
            Settings(
                DEBUG=False,
                JWT_SECRET="dev_anything",
                CSRF_SECRET="safe_csrf_secret_not_dev_prefix_32chars",
                ENCRYPTION_KEY="safe_encryption_key_32bytes_safe!",
                WG_INTERNAL_API_KEY="safe_wg_key",
                DATABASE_URL="postgresql+psycopg2://u:p@h/db",
            )

    def test_dev_secrets_allowed_in_debug_mode(self):
        """Secrets dev_* sont tolérés quand DEBUG=True (dev local)."""
        from app.core.config import Settings

        # Ne doit pas lever d'exception
        s = Settings(
            DEBUG=True,
            JWT_SECRET="dev_jwt_secret_CHANGER_EN_PROD_min32chars",
        )
        assert s.DEBUG is True
        assert s.JWT_SECRET.startswith("dev_")

    def test_trusted_proxy_headers_default_false(self):
        """TRUSTED_PROXY_HEADERS est False par défaut (sécurité X-Forwarded-For)."""
        from app.core.config import Settings

        s = Settings(DEBUG=True)
        assert s.TRUSTED_PROXY_HEADERS is False

    def test_cors_origins_default_is_localhost(self):
        """CORS_ORIGINS par défaut ne contient pas de wildcard."""
        from app.core.config import Settings

        s = Settings(DEBUG=True)
        assert "*" not in s.CORS_ORIGINS
        assert all(isinstance(o, str) for o in s.CORS_ORIGINS)
