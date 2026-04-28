"""Tests d'integration pour les endpoints de gestion des sessions."""
import pytest
from fastapi.testclient import TestClient

from app.core.security import decode_token
from tests.conftest import csrf_token_for_user


# ============================================================
# Helper: login et retourne (access_token, refresh_token, user_id)
# ============================================================

def _login(
    client: TestClient,
    email: str = "test@carocorp.com",
    password: str = "testpass123",
    user_agent: str | None = None,
):
    """Login et retourne (access_token, refresh_token)."""
    headers = {"User-Agent": user_agent} if user_agent else None
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
        headers=headers,
    )
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    data = resp.json()
    return data["access_token"], resp.cookies["refresh_token"]


def _auth_headers_with_csrf(access_token: str, user_id: int) -> dict:
    """Construit headers auth + CSRF pour requetes modifiantes."""
    sid = decode_token(access_token).get("sid")
    csrf = csrf_token_for_user(user_id, session_id=sid)
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
        assert data["total"] == 1
        assert len(data["sessions"]) == 1

        session = data["sessions"][0]
        assert "session_id" in session
        assert "device_id" in session
        assert session["device_id"]
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
        assert data["total"] == 0
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
        assert data["total"] == 3

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
        """Revoquer une session non-courante avec succes."""
        # Creer 2 sessions — on revoque l'ancienne depuis la courante
        _login(client)
        access_token, _ = _login(client)

        # Lister — triees decroissant : sessions[0]=courante, sessions[1]=ancienne
        list_resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_token),
        )
        sessions = list_resp.json()["sessions"]
        assert len(sessions) == 2
        old_session_id = sessions[1]["session_id"]

        # Revoquer l'ancienne (pas la courante) → 200
        resp = client.delete(
            f"/api/v1/sessions/{old_session_id}",
            headers=_auth_headers_with_csrf(access_token, test_user.id),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Session revoked"
        assert data["session_id"] == old_session_id

        # Il reste 1 session (la courante)
        list_resp2 = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_token),
        )
        assert list_resp2.json()["total"] == 1

    def test_cannot_revoke_current_session(self, client: TestClient, test_user):
        """Revoquer la session courante → 400 CANNOT_REVOKE_CURRENT_SESSION (spec §06 §6.12)."""
        access_token, _ = _login(client)

        # Obtenir le session_id de la session courante
        list_resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_token),
        )
        current_session_id = list_resp.json()["sessions"][0]["session_id"]

        # Tenter de revoquer la session courante avec le meme token → 400
        resp = client.delete(
            f"/api/v1/sessions/{current_session_id}",
            headers=_auth_headers_with_csrf(access_token, test_user.id),
        )

        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["error"] == "CANNOT_REVOKE_CURRENT_SESSION"

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
        assert list_resp2.json()["total"] == 2


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
        assert list_resp.json()["total"] == 4

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
        assert list_resp2.json()["total"] == 0

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
        assert list_resp.json()["total"] == 1


# ============================================================
# POST /auth/logout/device/{device_id} — Revoquer un appareil
# ============================================================

class TestLogoutDevice:
    """Tests pour POST /api/v1/auth/logout/device/{device_id}."""

    def test_logout_device_revokes_target_device_sessions_only(self, client: TestClient, test_user):
        """Révoque toutes les sessions d'un device ciblé sans toucher les autres devices."""
        # Device A : deux sessions
        _login(client, user_agent="Device-A-Agent/1.0")
        _login(client, user_agent="Device-A-Agent/1.0")
        # Device B : session courante
        access_b, _ = _login(client, user_agent="Device-B-Agent/1.0")

        list_resp = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_b),
        )
        assert list_resp.status_code == 200
        sessions_before = list_resp.json()["sessions"]
        assert len(sessions_before) >= 3

        target_device_id = next(
            s["device_id"] for s in sessions_before if s["user_agent"] == "Device-A-Agent/1.0"
        )
        current_device_id = next(s["device_id"] for s in sessions_before if s["is_current"])
        assert target_device_id != current_device_id

        revoke_resp = client.post(
            f"/api/v1/auth/logout/device/{target_device_id}",
            headers=_auth_headers_with_csrf(access_b, test_user.id),
        )
        assert revoke_resp.status_code == 200
        payload = revoke_resp.json()
        assert payload["status"] == "logged_out"
        assert payload["device_id"] == target_device_id
        assert payload["sessions_revoked"] >= 1

        list_after = client.get(
            "/api/v1/sessions",
            headers=_auth_headers(access_b),
        )
        assert list_after.status_code == 200
        sessions_after = list_after.json()["sessions"]
        assert all(s["device_id"] != target_device_id for s in sessions_after)
        assert any(s["device_id"] == current_device_id for s in sessions_after)

    def test_logout_device_not_found_returns_404(self, client: TestClient, test_user):
        """Device inconnu pour le user courant → 404."""
        access_token, _ = _login(client)
        resp = client.post(
            "/api/v1/auth/logout/device/unknown-device-id",
            headers=_auth_headers_with_csrf(access_token, test_user.id),
        )
        assert resp.status_code == 404


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
        assert data["total"] <= max_sessions
