"""Tests d'intégration pour POST /auth/logout."""
import pytest
from fastapi.testclient import TestClient


def test_logout_success(client: TestClient, test_user):
    """Test logout réussi avec access + refresh tokens."""
    # Login pour obtenir tokens
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@carocorp.com", "password": "testpass123"},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Logout avec refresh token
    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Logged out successfully"
    assert data["tokens_revoked"] is True


def test_logout_without_refresh_token(client: TestClient, test_user):
    """Test logout sans refresh token (seulement access token blacklisté)."""
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@carocorp.com", "password": "testpass123"},
    )
    access_token = login_response.json()["access_token"]

    # Logout sans body
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["tokens_revoked"] is True


def test_logout_without_auth_returns_401(client: TestClient):
    """Test logout sans JWT → 401."""
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401


def test_refresh_after_logout_returns_401(client: TestClient, test_user):
    """Test que refresh token est invalide après logout."""
    # Login
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@carocorp.com", "password": "testpass123"},
    )
    tokens = login_response.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Logout avec refresh token
    client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # Tenter refresh → 401 (refresh token révoqué)
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 401


def test_access_token_blacklisted_after_logout(client: TestClient, test_user):
    """Test que l'access token est blacklisté après logout."""
    # Login
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@carocorp.com", "password": "testpass123"},
    )
    tokens = login_response.json()
    access_token = tokens["access_token"]

    # Logout
    client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # Tenter d'utiliser l'access token → 401 (blacklisté)
    csrf_response = client.get(
        "/api/v1/auth/csrf",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert csrf_response.status_code == 401


def test_csrf_tokens_revoked_after_logout(client: TestClient, test_user):
    """Test que les tokens CSRF sont révoqués après logout."""
    from app.core.redis import redis_client

    # Login
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@carocorp.com", "password": "testpass123"},
    )
    access_token = login_response.json()["access_token"]

    # Obtenir un token CSRF
    csrf_response = client.get(
        "/api/v1/auth/csrf",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert csrf_response.status_code == 200
    csrf_token = csrf_response.json()["csrf_token"]

    # Vérifier que CSRF existe dans Redis
    assert redis_client.validate_csrf_token(test_user.id, csrf_token) is True

    # Logout
    client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # CSRF doit être révoqué
    assert redis_client.validate_csrf_token(test_user.id, csrf_token) is False


def test_logout_creates_audit_log(client: TestClient, test_user, test_db):
    """Test que le logout crée un audit log LOGOUT."""
    from app.models.audit_log import AuditLog

    # Login
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@carocorp.com", "password": "testpass123"},
    )
    access_token = login_response.json()["access_token"]

    # Logout
    client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # Vérifier audit log LOGOUT
    audit_log = (
        test_db.query(AuditLog)
        .filter(AuditLog.action == "LOGOUT", AuditLog.user_id == test_user.id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert audit_log is not None
    assert audit_log.tenant_id == test_user.tenant_id
    assert audit_log.description == "User logged out"


def test_double_logout_is_safe(client: TestClient, test_user):
    """Test que un double logout ne cause pas d'erreur (idempotent)."""
    # Login
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@carocorp.com", "password": "testpass123"},
    )
    tokens = login_response.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Premier logout
    response1 = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response1.status_code == 200

    # Login à nouveau pour obtenir un nouveau token
    login_response2 = client.post(
        "/api/v1/auth/login",
        data={"username": "test@carocorp.com", "password": "testpass123"},
    )
    access_token2 = login_response2.json()["access_token"]

    # Deuxième logout (avec nouveau token mais ancien refresh) — doit être safe
    response2 = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token2}"},
    )
    assert response2.status_code == 200
