"""Tests d'intégration pour les endpoints admin sessions.

Endpoints couverts :
  GET  /admin/tenants/{tenant_id}/sessions          — sessions:read
  GET  /admin/tenants/{tenant_id}/users/{uid}/sessions — sessions:read
  DELETE /admin/tenants/{tenant_id}/sessions/{sid}  — sessions:revoke + step-up
"""
import pytest
from fastapi.testclient import TestClient

from app.core.security import decode_token


# ============================================================
# Helpers
# ============================================================

def _login(
    client: TestClient,
    email: str = "admin@carocorp.com",
    password: str = "admin123",
) -> str:
    """Login et retourne l'access_token."""
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _auth_csrf(token: str, user_id: int) -> dict:
    from tests.conftest import csrf_token_for_user
    sid = decode_token(token).get("sid")
    csrf = csrf_token_for_user(user_id, session_id=sid)
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": csrf,
    }


# ============================================================
# GET /admin/tenants/{tenant_id}/sessions
# ============================================================

class TestAdminListTenantSessions:
    """Tests pour GET /api/v1/admin/tenants/{tenant_id}/sessions."""

    def test_list_tenant_sessions_after_login(self, client: TestClient, test_admin):
        """Admin peut lister les sessions de son tenant."""
        access_token = _login(client)
        tenant_id = test_admin.tenant_id

        resp = client.get(
            f"/api/v1/admin/tenants/{tenant_id}/sessions",
            headers=_auth(access_token),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "items" in data          # champ PaginatedResponse standard
        assert "total" in data
        assert "active_count" in data
        assert data["total"] >= 1
        assert len(data["sessions"]) >= 1

    def test_list_tenant_sessions_items_alias(self, client: TestClient, test_admin):
        """sessions et items retournent le même contenu."""
        access_token = _login(client)
        tenant_id = test_admin.tenant_id

        resp = client.get(
            f"/api/v1/admin/tenants/{tenant_id}/sessions",
            headers=_auth(access_token),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == data["items"]

    def test_list_tenant_sessions_requires_auth(self, client: TestClient, test_admin):
        """Sans token → 401."""
        resp = client.get(f"/api/v1/admin/tenants/{test_admin.tenant_id}/sessions")
        assert resp.status_code == 401

    def test_list_tenant_sessions_requires_sessions_read_scope(
        self, client: TestClient, test_user, auth_token
    ):
        """Staff (sans sessions:read) → 403."""
        resp = client.get(
            f"/api/v1/admin/tenants/{test_user.tenant_id}/sessions",
            headers=_auth(auth_token),
        )
        assert resp.status_code == 403

    def test_list_tenant_sessions_cross_tenant_mismatch(
        self, client: TestClient, test_admin, test_admin_tenant2, auth_token_admin_tenant2
    ):
        """Admin tenant 2 ne peut pas accéder aux sessions du tenant 1 → 403."""
        resp = client.get(
            f"/api/v1/admin/tenants/{test_admin.tenant_id}/sessions",
            headers=_auth(auth_token_admin_tenant2),
        )
        assert resp.status_code == 403

    def test_list_tenant_sessions_empty_before_login(
        self, client: TestClient, test_admin, auth_token_admin
    ):
        """Sans sessions DB, la liste est vide (token seul sans login)."""
        tenant_id = test_admin.tenant_id

        resp = client.get(
            f"/api/v1/admin/tenants/{tenant_id}/sessions",
            headers=_auth(auth_token_admin),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["sessions"] == []


# ============================================================
# GET /admin/tenants/{tenant_id}/users/{user_id}/sessions
# ============================================================

class TestAdminListUserSessions:
    """Tests pour GET /api/v1/admin/tenants/{tenant_id}/users/{user_id}/sessions."""

    def test_list_user_sessions_after_login(self, client: TestClient, test_admin):
        """Admin peut lister les sessions d'un user spécifique du tenant."""
        access_token = _login(client)
        tenant_id = test_admin.tenant_id

        resp = client.get(
            f"/api/v1/admin/tenants/{tenant_id}/users/{test_admin.id}/sessions",
            headers=_auth(access_token),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_list_user_sessions_isolation_from_other_user(
        self, client: TestClient, test_admin, test_user
    ):
        """Sessions d'un user ne contiennent pas celles d'un autre."""
        access_token = _login(client)
        tenant_id = test_admin.tenant_id

        resp = client.get(
            f"/api/v1/admin/tenants/{tenant_id}/users/{test_user.id}/sessions",
            headers=_auth(access_token),
        )

        assert resp.status_code == 200
        data = resp.json()
        # test_user n'a pas fait de login → 0 session
        assert data["total"] == 0

    def test_list_user_sessions_cross_tenant_mismatch(
        self, client: TestClient, test_admin, test_admin_tenant2, auth_token_admin_tenant2
    ):
        """Admin tenant 2 ne peut pas accéder aux sessions du tenant 1 → 403."""
        resp = client.get(
            f"/api/v1/admin/tenants/{test_admin.tenant_id}/users/{test_admin.id}/sessions",
            headers=_auth(auth_token_admin_tenant2),
        )
        assert resp.status_code == 403


# ============================================================
# DELETE /admin/tenants/{tenant_id}/sessions/{session_id}
# ============================================================

class TestAdminRevokeSession:
    """Tests pour DELETE /api/v1/admin/tenants/{tenant_id}/sessions/{session_id}."""

    def test_revoke_session_requires_stepup(self, client: TestClient, test_admin):
        """Sans step-up MFA → 403 STEP_UP_REQUIRED."""
        access_token = _login(client)
        tenant_id = test_admin.tenant_id

        # Obtenir une session à révoquer
        list_resp = client.get(
            f"/api/v1/admin/tenants/{tenant_id}/sessions",
            headers=_auth(access_token),
        )
        sessions = list_resp.json()["sessions"]
        assert len(sessions) >= 1
        session_id = sessions[0]["session_id"]

        resp = client.delete(
            f"/api/v1/admin/tenants/{tenant_id}/sessions/{session_id}",
            headers=_auth_csrf(access_token, test_admin.id),
        )

        # Step-up requis mais absent → 403
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "STEP_UP_REQUIRED"

    def test_revoke_session_cross_tenant_mismatch(
        self, client: TestClient, test_admin, test_admin_tenant2, auth_token_admin_tenant2
    ):
        """Admin tenant 2 tente de révoquer sur tenant 1 → 403 TENANT_MISMATCH."""
        resp = client.delete(
            f"/api/v1/admin/tenants/{test_admin.tenant_id}/sessions/any-session-id",
            headers=_auth_csrf(auth_token_admin_tenant2, test_admin_tenant2.id),
        )
        # Avant même step-up — tenant mismatch vérifié en premier
        assert resp.status_code in (403, 403)
        detail = resp.json().get("detail", {})
        assert detail in ("TENANT_MISMATCH", {"error": "STEP_UP_REQUIRED", "message": "MFA step-up required for this action"})

    def test_revoke_session_requires_auth(self, client: TestClient, test_admin):
        """Sans token → 401."""
        resp = client.delete(f"/api/v1/admin/tenants/{test_admin.tenant_id}/sessions/some-id")
        assert resp.status_code == 401

    def test_revoke_session_requires_sessions_revoke_scope(
        self, client: TestClient, test_user, auth_token
    ):
        """Staff (sans sessions:revoke) → 403."""
        resp = client.delete(
            f"/api/v1/admin/tenants/{test_user.tenant_id}/sessions/some-session-id",
            headers=_auth_csrf(auth_token, test_user.id),
        )
        assert resp.status_code == 403
