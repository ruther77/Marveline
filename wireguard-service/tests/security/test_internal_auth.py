"""Tests de sécurité pour l'authentification inter-service.

Vérifie que l'API key interne est correctement validée
et que les headers tenant/actor sont extraits.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
SECURITY_FILE = PROJECT_ROOT / "app" / "core" / "security.py"
DEPS_FILE = PROJECT_ROOT / "app" / "core" / "deps.py"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests structurels (analyse source)
# ---------------------------------------------------------------------------

class TestSecuritySourceStructure:
    """Vérifie la structure du module security."""

    def test_verify_function_exists(self):
        source = _read_source(SECURITY_FILE)
        assert "def verify_internal_api_key(" in source

    def test_uses_hmac_compare_digest(self):
        """La comparaison doit être timing-safe (hmac.compare_digest)."""
        source = _read_source(SECURITY_FILE)
        assert "hmac.compare_digest" in source

    def test_no_direct_equality_comparison(self):
        """Ne doit pas utiliser == pour comparer les clés (timing attack)."""
        source = _read_source(SECURITY_FILE)
        # Vérifier qu'il n'y a pas de comparaison directe provided_key == expected_key
        assert "provided_key ==" not in source
        assert "expected_key ==" not in source


class TestDepsSourceStructure:
    """Vérifie la structure du module deps."""

    def test_get_internal_auth_exists(self):
        source = _read_source(DEPS_FILE)
        assert "def get_internal_auth(" in source

    def test_extracts_tenant_id_header(self):
        source = _read_source(DEPS_FILE)
        assert "X-Tenant-ID" in source

    def test_extracts_actor_id_header(self):
        source = _read_source(DEPS_FILE)
        assert "X-Actor-ID" in source

    def test_extracts_api_key_header(self):
        source = _read_source(DEPS_FILE)
        assert "X-Internal-API-Key" in source

    def test_returns_401_on_invalid_key(self):
        source = _read_source(DEPS_FILE)
        assert "401" in source or "HTTP_401_UNAUTHORIZED" in source

    def test_returns_400_on_invalid_tenant(self):
        source = _read_source(DEPS_FILE)
        assert "400" in source or "HTTP_400_BAD_REQUEST" in source

    def test_internal_auth_dataclass(self):
        source = _read_source(DEPS_FILE)
        assert "class InternalAuth" in source
        assert "tenant_id" in source
        assert "actor_id" in source


# ---------------------------------------------------------------------------
# Tests fonctionnels (nécessitent fastapi installé)
# ---------------------------------------------------------------------------

try:
    import os
    os.environ.setdefault("INTERNAL_API_KEY", "test_key_exactly_32_characters!!")
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://test:test@localhost/test")
    from app.core.security import verify_internal_api_key
    from app.core.config import get_settings
    _CONFIGURED_KEY = get_settings().INTERNAL_API_KEY
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    _CONFIGURED_KEY = ""


@pytest.mark.skipif(not SECURITY_AVAILABLE, reason="app modules not importable")
class TestVerifyInternalApiKey:
    """Tests fonctionnels de vérification API key."""

    def test_valid_key_accepted(self):
        assert verify_internal_api_key(_CONFIGURED_KEY) is True

    def test_invalid_key_rejected(self):
        assert verify_internal_api_key("wrong_key") is False

    def test_empty_key_rejected(self):
        assert verify_internal_api_key("") is False

    def test_none_like_rejected(self):
        """Une chaîne vide ne doit pas passer."""
        assert verify_internal_api_key("") is False
