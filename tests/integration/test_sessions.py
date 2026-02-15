"""Tests d'integration pour les endpoints de gestion des sessions."""
import pytest
from fastapi.testclient import TestClient

from tests.conftest import csrf_token_for_user


# ============================================================
# Helper: login et retourne (access_token, refresh_token, user_id)
# ============================================================

def _login(client: TestClient, email: str = "test@carocorp.com", password: str = "testpass123"):
    """Login et retourne (access_token, refresh_token)."""
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    data = resp.json()
    return data["access_token"], data["refresh_token"]


def _auth_headers_with_csrf(access_token: str, user_id: int) -> dict:
    """Construit headers auth + CSRF pour requetes modifiantes."""
    csrf = csrf_token_for_user(user_id)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-CSRF-Token": csrf,
    }


def _auth_headers(access_token: str) -> dict:
    """Headers auth sans CSRF (pour GET uniquement)."""
    return {"Authorization": f"Bearer {access_token}"}


# ============================================================
# GET /sessions — Lister les sessions
# ============================================================

class TestListSessions:
    """Tests pour GET /api/v1/sessions."""

    def test_list_sessions_after_login(self, client: TestClient, test_user):
        """Apres login, GET /sessions retourne 1 session."""
        access_token, _ = _login(client)

        resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_token),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert len(data["sessions"]) == 1

        session = data["sessions"][0]
        assert "session_id" in session
        assert session["ip_address"]
        assert session["created_at"]
        assert session["last_activity"]

    def test_list_sessions_without_login_empty(self, client: TestClient, test_user, auth_token):
        """Avec un token valide mais sans login (pas de session creee), retourne 0 sessions."""
        resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(auth_token),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["sessions"] == []

    def test_list_sessions_multiple_logins(self, client: TestClient, test_user):
        """Plusieurs logins creent plusieurs sessions."""
        tokens = []
        for _ in range(3):
            access, _ = _login(client)
            tokens.append(access)

        resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(tokens[-1]),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 3

    def test_list_sessions_requires_auth(self, client: TestClient):
        """GET /sessions sans token → 401."""
        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 401

    def test_list_sessions_sorted_newest_first(self, client: TestClient, test_user):
        """Les sessions sont triees par date de creation decroissante."""
        for _ in range(2):
            _login(client)

        access_token, _ = _login(client)

        resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_token),
        )

        sessions = resp.json()["sessions"]
        assert len(sessions) == 3

        for i in range(len(sessions) - 1):
            assert sessions[i]["created_at"] >= sessions[i + 1]["created_at"]


# ============================================================
# DELETE /sessions/{id} — Revoquer une session
# ============================================================

class TestRevokeSession:
    """Tests pour DELETE /api/v1/sessions/{session_id}."""

    def test_revoke_session_success(self, client: TestClient, test_user):
        """Revoquer une session avec succes."""
        access_token, _ = _login(client)

        # Lister pour obtenir le session_id
        list_resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_token),
        )
        session_id = list_resp.json()["sessions"][0]["session_id"]

        # Revoquer (DELETE = methode modifiante → CSRF requis)
        resp = client.delete(
            f"/api/v1/sessions/{session_id}",
            headers=_auth_headers_with_csrf(access_token, test_user.id),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Session revoked"
        assert data["session_id"] == session_id

        # Verifier que la session n'existe plus
        list_resp2 = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_token),
        )
        assert list_resp2.json()["count"] == 0

    def test_revoke_session_not_found(self, client: TestClient, test_user, auth_token):
        """Revoquer une session inexistante → 404."""
        resp = client.delete(
            "/api/v1/sessions/nonexistent-session-id",
            headers=_auth_headers_with_csrf(auth_token, test_user.id),
        )

        assert resp.status_code == 404

    def test_revoke_session_requires_auth(self, client: TestClient):
        """DELETE /sessions/{id} sans token → 401."""
        resp = client.delete("/api/v1/sessions/some-session-id")
        assert resp.status_code == 401

    def test_revoke_session_cross_user_denied(
        self, client: TestClient, test_user, test_user_tenant2
    ):
        """Un user ne peut pas revoquer la session d'un autre user."""
        # User1 login
        access_token_user1, _ = _login(client, "test@carocorp.com", "testpass123")

        # Lister les sessions de user1
        list_resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_token_user1),
        )
        session_id_user1 = list_resp.json()["sessions"][0]["session_id"]

        # User2 login
        access_token_user2, _ = _login(client, "test@tenant2.com", "testpass123")

        # User2 tente de revoquer la session de user1 → 404
        resp = client.delete(
            f"/api/v1/sessions/{session_id_user1}",
            headers=_auth_headers_with_csrf(access_token_user2, test_user_tenant2.id),
        )

        assert resp.status_code == 404

    def test_revoke_one_session_keeps_others(self, client: TestClient, test_user):
        """Revoquer une session ne supprime pas les autres."""
        tokens = []
        for _ in range(3):
            access, _ = _login(client)
            tokens.append(access)

        # Lister
        list_resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(tokens[-1]),
        )
        sessions = list_resp.json()["sessions"]
        assert len(sessions) == 3

        # Revoquer la plus ancienne
        target_id = sessions[-1]["session_id"]
        client.delete(
            f"/api/v1/sessions/{target_id}",
            headers=_auth_headers_with_csrf(tokens[-1], test_user.id),
        )

        # Il reste 2 sessions
        list_resp2 = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(tokens[-1]),
        )
        assert list_resp2.json()["count"] == 2


# ============================================================
# DELETE /sessions — Revoquer toutes les sessions
# ============================================================

class TestRevokeAllSessions:
    """Tests pour DELETE /api/v1/sessions."""

    def test_revoke_all_sessions(self, client: TestClient, test_user):
        """Revoquer toutes les sessions."""
        for _ in range(3):
            _login(client)

        access_token, _ = _login(client)

        # Verifier 4 sessions
        list_resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_token),
        )
        assert list_resp.json()["count"] == 4

        # Revoquer toutes (DELETE → CSRF requis)
        resp = client.delete(
            "/api/v1/sessions",
            headers=_auth_headers_with_csrf(access_token, test_user.id),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "All sessions revoked"
        assert data["count"] == 4

        # Verifier 0 sessions
        list_resp2 = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_token),
        )
        assert list_resp2.json()["count"] == 0

    def test_revoke_all_sessions_none_exist(self, client: TestClient, test_user, auth_token):
        """Revoquer toutes les sessions quand aucune n'existe → count=0."""
        resp = client.delete(
            "/api/v1/sessions",
            headers=_auth_headers_with_csrf(auth_token, test_user.id),
        )

        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_revoke_all_sessions_requires_auth(self, client: TestClient):
        """DELETE /sessions sans token → 401."""
        resp = client.delete("/api/v1/sessions")
        assert resp.status_code == 401

    def test_revoke_all_sessions_cross_tenant_isolation(
        self, client: TestClient, test_user, test_user_tenant2
    ):
        """Revoquer toutes les sessions d'un user ne touche pas l'autre tenant."""
        # User1 login
        access_token_user1, _ = _login(client, "test@carocorp.com", "testpass123")

        # User2 login
        access_token_user2, _ = _login(client, "test@tenant2.com", "testpass123")

        # User1 revoque toutes SES sessions
        resp = client.delete(
            "/api/v1/sessions",
            headers=_auth_headers_with_csrf(access_token_user1, test_user.id),
        )
        assert resp.json()["count"] == 1

        # User2 a toujours sa session
        list_resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_token_user2),
        )
        assert list_resp.json()["count"] == 1


# ============================================================
# Max sessions enforcement via endpoints
# ============================================================

class TestMaxSessionsEnforcement:
    """Tests pour la limite max de sessions via endpoints."""

    def test_max_sessions_eviction(self, client: TestClient, test_user):
        """Au-dela de MAX_SESSIONS_PER_USER, la plus ancienne est evincee."""
        from app.constants import SessionConfig
        from app.core.redis import redis_client

        max_sessions = SessionConfig.MAX_SESSIONS_PER_USER

        # Creer max+1 sessions via login
        # Reset rate limits between logins to avoid 429
        last_access = None
        for i in range(max_sessions + 1):
            # Clear rate limit keys to avoid 429
            for key in redis_client.client.scan_iter("rate_limit:*"):
                redis_client.client.delete(key)
            access, _ = _login(client)
            last_access = access

        # Clear rate limits one more time for the listing login
        for key in redis_client.client.scan_iter("rate_limit:*"):
            redis_client.client.delete(key)

        resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(last_access),
        )

        data = resp.json()
        # max+1 logins but max sessions due to eviction
        assert data["count"] <= max_sessions
