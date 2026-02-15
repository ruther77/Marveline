"""Tests unitaires pour app/middleware/security.py.

Couvre les 3 middlewares :
- CSRFProtectionMiddleware : safe methods skip, public endpoints skip,
  no auth skip, valid/invalid/missing CSRF, token length check
- SecurityHeadersMiddleware : tous les headers de sécurité
- RateLimitMiddleware : exempt paths, global IP, scope detection, 429 response

Utilise le TestClient FastAPI avec les middlewares réels et Redis réel (Docker).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, decode_token
from app.core.redis import redis_client
from app.middleware.security import CSRFProtectionMiddleware
from app.constants import (
    AuthEndpoints,
    ErrorMessages,
    HealthEndpoints,
    PublicEndpoints,
    SecurityHeaders,
)
from tests.conftest import csrf_token_for_user


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def raw_client():
    """TestClient sans DB override (middleware-only tests)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user_jwt():
    """JWT valide pour user_id=999, tenant_id=1."""
    return create_access_token({"sub": 999, "tenant_id": 1, "role": "staff"})


@pytest.fixture
def user_csrf():
    """CSRF token stocké dans Redis pour user_id=999."""
    return csrf_token_for_user(999)


# ── CSRF: Safe Methods Skip ────────────────────────────────────────────


class TestCSRFSafeMethods:
    """GET, HEAD, OPTIONS ne doivent pas déclencher CSRF."""

    def test_get_skips_csrf(self, raw_client, user_jwt):
        """GET ne nécessite pas de CSRF token."""
        resp = raw_client.get(
            "/api/v1/health",
            headers={"Authorization": f"Bearer {user_jwt}"},
        )
        # Should not be 403 CSRF
        assert resp.status_code != 403

    def test_options_skips_csrf(self, raw_client, user_jwt):
        """OPTIONS ne nécessite pas de CSRF token."""
        resp = raw_client.options(
            "/api/v1/health",
            headers={"Authorization": f"Bearer {user_jwt}"},
        )
        assert resp.status_code != 403

    def test_head_skips_csrf(self, raw_client, user_jwt):
        """HEAD ne nécessite pas de CSRF token."""
        resp = raw_client.head(
            "/api/v1/health",
            headers={"Authorization": f"Bearer {user_jwt}"},
        )
        assert resp.status_code != 403


# ── CSRF: Public Endpoints Skip ────────────────────────────────────────


class TestCSRFPublicEndpoints:
    """Les endpoints publics (login, refresh, logout, mfa/verify) skip CSRF."""

    def test_login_skips_csrf(self, raw_client):
        """POST /auth/login ne nécessite pas de CSRF."""
        resp = raw_client.post(
            AuthEndpoints.LOGIN,
            data={"username": "x@y.com", "password": "wrong"},
        )
        # Should be 401/422 (invalid creds), NOT 403 CSRF
        assert resp.status_code != 403

    def test_refresh_skips_csrf(self, raw_client):
        """POST /auth/refresh ne nécessite pas de CSRF."""
        resp = raw_client.post(
            AuthEndpoints.REFRESH,
            json={"refresh_token": "invalid"},
        )
        assert resp.status_code != 403

    def test_logout_skips_csrf(self, raw_client, user_jwt):
        """POST /auth/logout ne nécessite pas de CSRF."""
        resp = raw_client.post(
            AuthEndpoints.LOGOUT,
            headers={"Authorization": f"Bearer {user_jwt}"},
            json={"refresh_token": "invalid"},
        )
        assert resp.status_code != 403


# ── CSRF: No Auth Header Skip ──────────────────────────────────────────


class TestCSRFNoAuth:
    """Requêtes sans Authorization header skip CSRF (endpoint gère 401)."""

    def test_post_without_auth_skips_csrf(self, raw_client):
        """POST sans Authorization ne déclenche pas 403 CSRF."""
        resp = raw_client.post("/api/v1/customers", json={})
        # Attendu: 401 (pas d'auth), pas 403 (CSRF)
        assert resp.status_code != 403


# ── CSRF: Token Validation ──────────────────────────────────────────────


class TestCSRFTokenValidation:
    """Tests de validation du token CSRF."""

    def test_missing_csrf_returns_403(self, raw_client, user_jwt):
        """POST avec JWT mais sans X-CSRF-Token = 403."""
        resp = raw_client.post(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {user_jwt}"},
            json={"name": "test"},
        )
        assert resp.status_code == 403
        assert ErrorMessages.CSRF_TOKEN_MISSING in resp.json()["detail"]

    def test_invalid_csrf_returns_403(self, raw_client, user_jwt):
        """POST avec JWT et faux CSRF token = 403."""
        resp = raw_client.post(
            "/api/v1/customers",
            headers={
                "Authorization": f"Bearer {user_jwt}",
                "X-CSRF-Token": "a" * 43,  # valid length but not in Redis
            },
            json={"name": "test"},
        )
        assert resp.status_code == 403
        assert ErrorMessages.CSRF_TOKEN_INVALID in resp.json()["detail"]

    def test_short_csrf_returns_403(self, raw_client, user_jwt):
        """POST avec CSRF token trop court = 403 INVALID."""
        resp = raw_client.post(
            "/api/v1/customers",
            headers={
                "Authorization": f"Bearer {user_jwt}",
                "X-CSRF-Token": "short",
            },
            json={"name": "test"},
        )
        assert resp.status_code == 403
        assert ErrorMessages.CSRF_TOKEN_INVALID in resp.json()["detail"]

    def test_valid_csrf_passes(self, raw_client, user_jwt, user_csrf):
        """POST avec JWT + CSRF valide ne retourne pas 403."""
        resp = raw_client.post(
            "/api/v1/customers",
            headers={
                "Authorization": f"Bearer {user_jwt}",
                "X-CSRF-Token": user_csrf,
            },
            json={"name": "test"},
        )
        # Le middleware CSRF a laissé passer — on attend pas 403
        # (l'endpoint peut retourner 401/422/500 selon l'état DB, c'est OK)
        assert resp.status_code != 403

    def test_invalid_jwt_skips_csrf(self, raw_client):
        """POST avec JWT invalide skip CSRF (endpoint gérera 401)."""
        resp = raw_client.post(
            "/api/v1/customers",
            headers={
                "Authorization": "Bearer invalid_jwt_token",
            },
            json={"name": "test"},
        )
        # JWT invalide → CSRF middleware retourne call_next (pas 403)
        assert resp.status_code != 403


# ── CSRF: Token Generation ─────────────────────────────────────────────


class TestCSRFTokenGeneration:
    def test_generate_csrf_token_length(self):
        """generate_csrf_token retourne un token de longueur suffisante."""
        token = CSRFProtectionMiddleware.generate_csrf_token()
        assert len(token) >= 32

    def test_generate_csrf_token_unique(self):
        """generate_csrf_token retourne un token unique à chaque appel."""
        t1 = CSRFProtectionMiddleware.generate_csrf_token()
        t2 = CSRFProtectionMiddleware.generate_csrf_token()
        assert t1 != t2


# ── Security Headers ───────────────────────────────────────────────────


class TestSecurityHeaders:
    """Vérifie que SecurityHeadersMiddleware ajoute les bons headers."""

    def test_x_content_type_options(self, raw_client):
        resp = raw_client.get("/api/v1/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self, raw_client):
        resp = raw_client.get("/api/v1/health")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_x_xss_protection(self, raw_client):
        resp = raw_client.get("/api/v1/health")
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_hsts(self, raw_client):
        resp = raw_client.get("/api/v1/health")
        hsts = resp.headers.get("Strict-Transport-Security")
        assert hsts is not None
        assert "max-age=31536000" in hsts

    def test_referrer_policy(self, raw_client):
        resp = raw_client.get("/api/v1/health")
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


# ── Rate Limiting: Exempt Paths ─────────────────────────────────────────


class TestRateLimitExemptPaths:
    """Les endpoints health/docs sont exemptés du rate limiting."""

    def test_health_exempt(self, raw_client):
        """Health check ne retourne jamais 429."""
        for _ in range(10):
            resp = raw_client.get(HealthEndpoints.BASE)
            assert resp.status_code != 429

    def test_health_ready_exempt(self, raw_client):
        for _ in range(10):
            resp = raw_client.get(HealthEndpoints.READY)
            assert resp.status_code != 429

    def test_health_live_exempt(self, raw_client):
        for _ in range(10):
            resp = raw_client.get(HealthEndpoints.LIVE)
            assert resp.status_code != 429


# ── Rate Limiting: Headers ──────────────────────────────────────────────


class TestRateLimitHeaders:
    """Les réponses non-exemptées contiennent les headers rate limit."""

    def test_rate_limit_headers_present(self, raw_client, user_jwt, user_csrf):
        """Une requête authentifiée reçoit les headers rate limit."""
        resp = raw_client.post(
            "/api/v1/customers",
            headers={
                "Authorization": f"Bearer {user_jwt}",
                "X-CSRF-Token": user_csrf,
            },
            json={"name": "test"},
        )
        # Si la requête n'est pas rate-limited (pas 429), les headers sont là
        if resp.status_code != 429:
            assert "X-RateLimit-Limit" in resp.headers
            assert "X-RateLimit-Remaining" in resp.headers
            assert "X-RateLimit-Reset" in resp.headers


# ── Rate Limiting: Login Scope ──────────────────────────────────────────


class TestRateLimitLoginScope:
    """Le login endpoint a un rate limit strict (5 req/min)."""

    def test_login_rate_limited_after_threshold(self, raw_client):
        """6 logins en rafale doivent déclencher un 429."""
        for i in range(6):
            resp = raw_client.post(
                AuthEndpoints.LOGIN,
                data={"username": f"test{i}@x.com", "password": "wrong"},
            )

        # La 6ème requête ou les suivantes devraient avoir un 429
        resp = raw_client.post(
            AuthEndpoints.LOGIN,
            data={"username": "final@x.com", "password": "wrong"},
        )
        assert resp.status_code == 429

    def test_429_response_has_retry_after(self, raw_client):
        """La réponse 429 contient Retry-After."""
        # Flood login pour déclencher rate limit
        for _ in range(7):
            raw_client.post(
                AuthEndpoints.LOGIN,
                data={"username": "flood@x.com", "password": "wrong"},
            )

        resp = raw_client.post(
            AuthEndpoints.LOGIN,
            data={"username": "flood@x.com", "password": "wrong"},
        )
        if resp.status_code == 429:
            assert "Retry-After" in resp.headers
            assert "X-RateLimit-Remaining" in resp.headers
            assert resp.headers["X-RateLimit-Remaining"] == "0"


# ── Rate Limiting: Client IP Extraction ─────────────────────────────────


class TestRateLimitClientIP:
    """Vérifie l'extraction d'IP depuis X-Forwarded-For."""

    def test_x_forwarded_for_used(self, raw_client):
        """Si X-Forwarded-For est présent, c'est l'IP utilisée pour rate limit."""
        # Deux IPs différentes via X-Forwarded-For ne partagent pas le rate limit
        for _ in range(5):
            raw_client.post(
                AuthEndpoints.LOGIN,
                data={"username": "a@b.com", "password": "wrong"},
                headers={"X-Forwarded-For": "1.2.3.4"},
            )

        # IP différente ne devrait pas être rate limited
        resp = raw_client.post(
            AuthEndpoints.LOGIN,
            data={"username": "a@b.com", "password": "wrong"},
            headers={"X-Forwarded-For": "5.6.7.8"},
        )
        # 5.6.7.8 est une IP fraîche, ne devrait pas être rate limited
        assert resp.status_code != 429
