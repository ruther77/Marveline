"""Tests de sécurité pour la protection CSRF avec Redis."""
import hmac as _hmac

import pytest
import redis as _sync_redis
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.constants import RedisKeys
from app.constants.security import SessionConfig
from app.core.config import settings
from app.core.redis import redis_client, redis_sec
from app.core.security import decode_token as _decode_jwt
from app.core.deps import UserCompat


def _sid_from_headers(headers: dict) -> str:
    """Extrait le claim 'sid' depuis le token Bearer dans les headers."""
    token = headers["Authorization"][7:]  # "Bearer " = 7 chars
    return _decode_jwt(token).get("sid", "")


# Sync Redis client for test inspection — évite les conflits d'event loop entre
# TestClient (loop dédié) et redis_client async (binding initial au 1er loop).
_sync_sec = _sync_redis.from_url(settings.REDIS_SEC_URL, decode_responses=True)


def _sync_validate_csrf(sid: str, token: str) -> bool:
    stored = _sync_sec.get(RedisKeys.csrf_token(sid))
    if not stored:
        return False
    return _hmac.compare_digest(stored, token)


def _sync_revoke_csrf(sid: str) -> bool:
    return bool(_sync_sec.delete(RedisKeys.csrf_token(sid)))


def _sync_revoke_all_csrf(user_id: int) -> int:
    idx_key = RedisKeys.user_sessions_index(user_id)
    members = _sync_sec.smembers(idx_key)
    count = 0
    for member in members:
        sid = member.split(":", 1)[-1]
        count += _sync_sec.delete(RedisKeys.csrf_token(sid))
    return count


class TestCSRFProtection:
    """Tests unitaires de la protection CSRF."""

    def test_get_csrf_token_authenticated_success(
        self,
        client: TestClient,
        test_user: UserCompat,
        auth_headers_real: dict
    ):
        """GET /auth/csrf avec JWT valide retourne un token CSRF."""
        response = client.get(
            "/api/v1/auth/csrf",
            headers=auth_headers_real
        )

        assert response.status_code == 200
        data = response.json()

        assert "csrf_token" in data
        assert "expires_in" in data
        assert len(data["csrf_token"]) >= 32
        # TTL aligné sur la session (7j) — plus 900s après refactor P2-01
        assert data["expires_in"] == SessionConfig.SESSION_TTL_SECONDS

        # Vérifier que le token existe dans Redis via session_id (§04 §4.3)
        sid = _sid_from_headers(auth_headers_real)
        assert _sync_validate_csrf(sid, data["csrf_token"]) is True

    def test_get_csrf_token_unauthenticated_401(self, client: TestClient):
        """GET /auth/csrf sans JWT retourne 401."""
        response = client.get("/api/v1/auth/csrf")
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_get_csrf_token_invalid_jwt_401(self, client: TestClient):
        """GET /auth/csrf avec JWT invalide retourne 401."""
        response = client.get(
            "/api/v1/auth/csrf",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401

    def test_post_without_csrf_token_403(
        self,
        client: TestClient,
        auth_token: str
    ):
        """POST sans X-CSRF-Token header retourne 403."""
        # Headers avec SEULEMENT Authorization (pas de X-CSRF-Token)
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.post(
            "/api/v1/customers",
            headers=headers,
            json={
                "customer_type": "individual",
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean.dupont@example.com",
                "phone": "+33123456789"
            }
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "CSRF token missing"

    def test_post_with_invalid_csrf_token_403(
        self,
        client: TestClient,
        auth_headers_real: dict
    ):
        """POST avec X-CSRF-Token invalide retourne 403."""
        headers = {
            **auth_headers_real,
            "X-CSRF-Token": "invalid_token_12345678901234567890123456"
        }

        response = client.post(
            "/api/v1/customers",
            headers=headers,
            json={
                "customer_type": "individual",
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean.dupont@example.com",
                "phone": "+33123456789"
            }
        )

        assert response.status_code == 403
        assert "CSRF token invalid" in response.json()["detail"]

    def test_post_with_valid_csrf_token_success(
        self,
        client: TestClient,
        test_user: UserCompat,
        auth_headers_real: dict
    ):
        """POST avec X-CSRF-Token valide réussit."""
        # 1. Générer token CSRF
        csrf_response = client.get(
            "/api/v1/auth/csrf",
            headers=auth_headers_real
        )
        assert csrf_response.status_code == 200
        csrf_token = csrf_response.json()["csrf_token"]

        # 2. Faire une requête POST avec le token CSRF
        headers = {
            **auth_headers_real,
            "X-CSRF-Token": csrf_token
        }

        response = client.post(
            "/api/v1/customers",
            headers=headers,
            json={
                "customer_type": "individual",
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean.csrf.test@example.com",
                "phone": "+33123456789"
            }
        )

        # CSRF validation doit passer, endpoint peut créer le customer
        assert response.status_code in [201, 400]  # 201=success, 400=validation error

    def test_safe_methods_skip_csrf(
        self,
        client: TestClient,
        auth_headers_real: dict
    ):
        """GET, HEAD, OPTIONS ne nécessitent pas de token CSRF."""
        # GET sans CSRF token doit passer
        response = client.get(
            "/api/v1/customers",
            headers=auth_headers_real
        )
        assert response.status_code == 200

    def test_public_endpoints_skip_csrf(self, client: TestClient):
        """Les endpoints publics (health, docs, auth) skip CSRF."""
        # Health check sans auth ni CSRF
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        # Login sans CSRF
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "wrongpass"
            }
        )
        # Peut retourner 401 (wrong password) mais pas 403 (CSRF)
        assert response.status_code == 401

    def test_unauthenticated_post_skips_csrf(self, client: TestClient):
        """POST sans Authorization header skip CSRF (JWT retournera 401)."""
        # POST sans Authorization ni CSRF -> 401 (JWT), pas 403 (CSRF)
        response = client.post(
            "/api/v1/customers",
            json={
                "customer_type": "individual",
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean@example.com",
                "phone": "+33123456789"
            }
        )

        assert response.status_code == 401
        detail = response.json()["detail"]
        assert "authenticated" in detail.lower() or "credentials" in detail.lower()

    def test_multiple_csrf_tokens_per_session_replace(
        self,
        client: TestClient,
        test_user: UserCompat,
        auth_headers_real: dict
    ):
        """Appels successifs à /auth/csrf remplacent le token précédent (1 CSRF par session).

        Spec §04 §4.3 : clé Redis csrf:{session_id} — SETEX écrase l'ancienne valeur.
        Seul le dernier token émis est valide.
        """
        sid = _sid_from_headers(auth_headers_real)

        tokens = []
        for _ in range(3):
            response = client.get("/api/v1/auth/csrf", headers=auth_headers_real)
            assert response.status_code == 200
            tokens.append(response.json()["csrf_token"])

        # Tous les tokens générés sont distincts (randomness)
        assert len(set(tokens)) == 3

        # Seul le dernier token est valide (SETEX a remplacé les précédents)
        assert _sync_validate_csrf(sid, tokens[-1]) is True
        assert _sync_validate_csrf(sid, tokens[0]) is False
        assert _sync_validate_csrf(sid, tokens[1]) is False

    def test_csrf_token_expires_after_ttl(
        self,
        client: TestClient,
        test_user: UserCompat,
        auth_headers_real: dict
    ):
        """Le token CSRF expire après son TTL (aligné sur la session, 7j)."""
        sid = _sid_from_headers(auth_headers_real)

        # Générer token CSRF
        response = client.get("/api/v1/auth/csrf", headers=auth_headers_real)
        csrf_token = response.json()["csrf_token"]

        # Token valide immédiatement
        assert _sync_validate_csrf(sid, csrf_token) is True

        # Simuler expiration (supprimer manuellement de Redis via session_id)
        _sync_revoke_csrf(sid)

        # Token plus valide
        assert _sync_validate_csrf(sid, csrf_token) is False

    def test_revoke_all_csrf_tokens_logout(
        self,
        client: TestClient,
        test_user: UserCompat,
        auth_headers_real: dict
    ):
        """Lors du logout, tous les tokens CSRF liés aux sessions actives sont révoqués.

        revoke_all_csrf_tokens itère user_sessions_index:{uid} pour obtenir les sids.
        L'index doit être peuplé (comme en production après issue_tokens).
        """
        sid = _sid_from_headers(auth_headers_real)
        did = "test_device"

        # Peupler user_sessions_index pour que revoke_all_csrf_tokens puisse itérer
        _sync_sec.sadd(
            RedisKeys.user_sessions_index(test_user.id),
            f"{did}:{sid}"
        )

        # Générer 1 token CSRF pour cette session
        response = client.get("/api/v1/auth/csrf", headers=auth_headers_real)
        csrf_token = response.json()["csrf_token"]

        # Token valide
        assert _sync_validate_csrf(sid, csrf_token) is True

        # Révoquer tous les tokens CSRF de l'user (simulate logout)
        revoked_count = _sync_revoke_all_csrf(test_user.id)
        assert revoked_count >= 1

        # Token révoqué
        assert _sync_validate_csrf(sid, csrf_token) is False

    def test_csrf_token_tied_to_session(
        self,
        client: TestClient,
        test_user: UserCompat,
        test_user_tenant2: UserCompat,
        auth_headers_real: dict,
        auth_headers_tenant2: dict
    ):
        """Un token CSRF est lié à une session (sid), pas à un user_id.

        Le token CSRF de user1 (sid1) ne peut pas être utilisé par user2 (sid2).
        """
        sid_user1 = _sid_from_headers(auth_headers_real)
        sid_user2 = _sid_from_headers(auth_headers_tenant2)

        # User 1 génère un token CSRF
        response = client.get("/api/v1/auth/csrf", headers=auth_headers_real)
        csrf_token_user1 = response.json()["csrf_token"]

        # Token valide pour sid_user1
        assert _sync_validate_csrf(sid_user1, csrf_token_user1) is True

        # Token invalide pour sid_user2 (session différente)
        assert _sync_validate_csrf(sid_user2, csrf_token_user1) is False

        # User 2 tente d'utiliser le token de user1 -> 403
        headers_user2_with_token_user1 = {
            **auth_headers_tenant2,
            "X-CSRF-Token": csrf_token_user1
        }

        response = client.post(
            "/api/v1/customers",
            headers=headers_user2_with_token_user1,
            json={
                "customer_type": "individual",
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean.dupont.user2@example.com",
                "phone": "+33123456789"
            }
        )

        assert response.status_code == 403
        assert "CSRF token invalid" in response.json()["detail"]

    def test_csrf_token_length_validation(
        self,
        client: TestClient,
        auth_headers_real: dict
    ):
        """Les tokens CSRF courts (< 32 chars) sont rejetés."""
        headers = {
            **auth_headers_real,
            "X-CSRF-Token": "short"  # < 32 chars
        }

        response = client.post(
            "/api/v1/customers",
            headers=headers,
            json={
                "customer_type": "individual",
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean@example.com",
                "phone": "+33123456789"
            }
        )

        assert response.status_code == 403
        assert "CSRF token invalid" in response.json()["detail"]
