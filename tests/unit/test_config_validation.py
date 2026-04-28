"""Tests unitaires pour app/core/config.py — validation des secrets production.

Couvre CONFIG-01 : le model_validator doit rejeter les secrets dev_*
inconditionnellement (même avec DEBUG=True).
"""
import pytest
from pydantic import ValidationError

# Secrets safe (non dev_*) utilisés par les tests qui ne testent PAS la validation des secrets
_SAFE_TEST_SECRETS: dict = {
    "ENCRYPTION_KEY": "test_not_dev_enc_key_32bytes_ok!!",
    "WG_INTERNAL_API_KEY": "test_wg_key_not_dev_prefix_ok!!!",
    "PASSWORD_PEPPER": "test_pepper_not_dev_32chars_safe!!",
    "TOTP_DEV_MASTER_KEY": "test_totp_master_not_dev_32chars!",
    "AUDIT_HMAC_KEY": "test_audit_hmac_not_dev_32chars!!",
}


class TestProductionSecretsValidation:
    """Le validator bloque le démarrage si des secrets dev sont détectés (tous modes)."""

    def test_dev_secrets_raise_in_production(self):
        """Secrets par défaut dev_* doivent lever ValueError."""
        from app.core.config import Settings

        # Forcer explicitement une valeur dev_ sur PASSWORD_PEPPER → violation
        with pytest.raises((ValidationError, ValueError)):
            Settings(
                DEBUG=False,
                PASSWORD_PEPPER="dev_pepper_CHANGER_EN_PROD_min32chars",
                **{k: v for k, v in _SAFE_TEST_SECRETS.items() if k != "PASSWORD_PEPPER"},
            )

    def test_strong_secrets_accepted(self):
        """Secrets forts (non dev_*) doivent être acceptés."""
        from app.core.config import Settings

        s = Settings(
            DEBUG=False,
            DATABASE_URL="postgresql+psycopg2://caro:pw@localhost:5432/db",
            **_SAFE_TEST_SECRETS,
        )
        assert s.DEBUG is False

    def test_dev_encryption_key_blocked(self):
        """ENCRYPTION_KEY avec préfixe dev_ doit être bloqué."""
        from app.core.config import Settings

        with pytest.raises((ValidationError, ValueError)):
            Settings(
                DEBUG=False,
                ENCRYPTION_KEY="dev_anything_32chars_padded_here!!!",
                **{k: v for k, v in _SAFE_TEST_SECRETS.items() if k != "ENCRYPTION_KEY"},
            )

    def test_dev_pepper_blocked(self):
        """PASSWORD_PEPPER avec préfixe dev_ doit être bloqué."""
        from app.core.config import Settings

        with pytest.raises((ValidationError, ValueError)):
            Settings(
                DEBUG=False,
                PASSWORD_PEPPER="dev_pepper_CHANGER_EN_PROD_min32chars",
                **{k: v for k, v in _SAFE_TEST_SECRETS.items() if k != "PASSWORD_PEPPER"},
            )

    def test_dev_secrets_blocked_regardless_of_debug_mode(self):
        """Secrets dev_* sont rejetés même avec DEBUG=True (validation inconditionnelle)."""
        from app.core.config import Settings

        # Doit lever une exception même en mode debug (valeurs par défaut dev_)
        with pytest.raises((ValidationError, ValueError)):
            Settings(
                DEBUG=True,
                ENCRYPTION_KEY="dev_anything_will_be_blocked_here!",
                **{k: v for k, v in _SAFE_TEST_SECRETS.items() if k != "ENCRYPTION_KEY"},
            )

    def test_optional_secrets_empty_allowed(self):
        """HCAPTCHA et OAuth secrets vides (non configurés) sont acceptés."""
        from app.core.config import Settings

        # Champs optionnels vides = service non activé, pas une violation
        s = Settings(
            DEBUG=True,
            HCAPTCHA_SECRET_KEY="",
            OAUTH_GOOGLE_CLIENT_SECRET="",
            OAUTH_GITHUB_CLIENT_SECRET="",
            OAUTH_FACEBOOK_CLIENT_SECRET="",
            **_SAFE_TEST_SECRETS,
        )
        assert s.HCAPTCHA_SECRET_KEY == ""

    def test_optional_secrets_dev_prefix_blocked(self):
        """HCAPTCHA et OAuth secrets avec préfixe dev_ doivent être bloqués."""
        from app.core.config import Settings

        with pytest.raises((ValidationError, ValueError)):
            Settings(
                DEBUG=True,
                HCAPTCHA_SECRET_KEY="dev_captcha_key_is_not_allowed!!",
                **_SAFE_TEST_SECRETS,
            )

    def test_trusted_proxy_headers_default_false(self):
        """TRUSTED_PROXY_HEADERS est False par défaut (sécurité X-Forwarded-For)."""
        from app.core.config import Settings

        s = Settings(DEBUG=True, **_SAFE_TEST_SECRETS)
        assert s.TRUSTED_PROXY_HEADERS is False

    def test_cors_origins_default_is_localhost(self):
        """CORS_ORIGINS par défaut ne contient pas de wildcard."""
        from app.core.config import Settings

        s = Settings(DEBUG=True, **_SAFE_TEST_SECRETS)
        assert "*" not in s.CORS_ORIGINS
        assert all(isinstance(o, str) for o in s.CORS_ORIGINS)
