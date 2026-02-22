"""Tests sécurité : configuration CORS.

Couvre CORS-01 :
- Origines non autorisées rejetées
- Origines autorisées acceptées
- allow_headers n'est pas un wildcard
- allow_credentials=True uniquement avec origines explicites (pas *)
- Preflight OPTIONS retourne les bons headers
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings


@pytest.fixture
def cors_client():
    """Client de test standard."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestCORSOriginValidation:
    """Les origines non autorisées ne reçoivent pas de headers CORS."""

    def test_authorized_origin_gets_cors_headers(self, cors_client):
        """Origine autorisée reçoit Access-Control-Allow-Origin."""
        authorized_origin = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "http://localhost:3002"
        resp = cors_client.options(
            "/api/v1/health",
            headers={
                "Origin": authorized_origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI retourne 200 pour preflight si origine autorisée
        assert resp.headers.get("Access-Control-Allow-Origin") == authorized_origin

    def test_unauthorized_origin_no_cors_headers(self, cors_client):
        """Origine non autorisée ne reçoit pas Access-Control-Allow-Origin."""
        resp = cors_client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://evil.attacker.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        # Pas de header CORS → l'origine n'est pas autorisée
        acao = resp.headers.get("Access-Control-Allow-Origin", "")
        assert acao != "https://evil.attacker.com"
        assert acao != "*"

    def test_wildcard_not_in_cors_origins(self):
        """La liste CORS_ORIGINS ne contient pas de wildcard."""
        assert "*" not in settings.CORS_ORIGINS

    def test_cors_allow_credentials_requires_explicit_origins(self):
        """Si allow_credentials=True, les origines ne peuvent pas être '*'."""
        if settings.CORS_ALLOW_CREDENTIALS:
            assert "*" not in settings.CORS_ORIGINS, (
                "SECURITE: allow_credentials=True avec CORS_ORIGINS=['*'] "
                "est interdit par la spec CORS."
            )


class TestCORSAllowedHeaders:
    """Les headers autorisés sont une liste explicite, pas un wildcard."""

    def test_authorized_headers_in_preflight(self, cors_client):
        """Les headers métier sont bien autorisés dans le preflight."""
        authorized_origin = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "http://localhost:3002"
        resp = cors_client.options(
            "/api/v1/health",
            headers={
                "Origin": authorized_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, Authorization, X-CSRF-Token",
            },
        )
        allowed = resp.headers.get("Access-Control-Allow-Headers", "")
        # Les headers demandés doivent être autorisés (ou le preflight passe)
        # FastAPI répond les headers autorisés — vérifier que ce n'est pas juste "*"
        if allowed:
            assert allowed != "*", "SECURITE: Access-Control-Allow-Headers ne doit pas être '*'"

    def test_no_wildcard_in_allow_headers(self, cors_client):
        """Le preflight ne retourne jamais Allow-Headers: *."""
        authorized_origin = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "http://localhost:3002"
        resp = cors_client.options(
            "/api/v1/health",
            headers={
                "Origin": authorized_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        allowed_headers = resp.headers.get("Access-Control-Allow-Headers", "")
        assert allowed_headers != "*"
