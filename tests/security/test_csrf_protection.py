"""Tests de sécurité pour la protection CSRF avec Redis."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.redis import redis_client
from app.models.user import User


class TestCSRFProtection:
    """Tests unitaires de la protection CSRF."""

    def test_get_csrf_token_authenticated_success(
        self,
        client: TestClient,
        test_user: User,
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
        assert data["expires_in"] == 900  # 15 minutes

        # Vérifier que le token existe dans Redis
        assert redis_client.validate_csrf_token(test_user.id, data["csrf_token"]) is True

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
        assert response.json()["detail"] == "CSRF token manquant"

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
        assert "CSRF token invalide" in response.json()["detail"]

    def test_post_with_valid_csrf_token_success(
        self,
        client: TestClient,
        test_user: User,
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
        assert "Not authenticated" in response.json()["detail"]

    def test_multiple_csrf_tokens_per_user(
        self,
        client: TestClient,
        test_user: User,
        auth_headers_real: dict
    ):
        """Un utilisateur peut avoir plusieurs tokens CSRF actifs (multi-tabs)."""
        # Générer 3 tokens CSRF
        tokens = []
        for _ in range(3):
            response = client.get("/api/v1/auth/csrf", headers=auth_headers_real)
            assert response.status_code == 200
            tokens.append(response.json()["csrf_token"])

        # Tous les tokens sont uniques
        assert len(set(tokens)) == 3

        # Tous les tokens sont valides dans Redis
        for token in tokens:
            assert redis_client.validate_csrf_token(test_user.id, token) is True

    def test_csrf_token_expires_after_ttl(
        self,
        client: TestClient,
        test_user: User,
        auth_headers_real: dict
    ):
        """Le token CSRF expire après son TTL (15 minutes)."""
        # Générer token CSRF
        response = client.get("/api/v1/auth/csrf", headers=auth_headers_real)
        csrf_token = response.json()["csrf_token"]

        # Token valide immédiatement
        assert redis_client.validate_csrf_token(test_user.id, csrf_token) is True

        # Simuler expiration (supprimer manuellement de Redis)
        redis_client.revoke_csrf_token(test_user.id, csrf_token)

        # Token plus valide
        assert redis_client.validate_csrf_token(test_user.id, csrf_token) is False

    def test_revoke_all_csrf_tokens_logout(
        self,
        client: TestClient,
        test_user: User,
        auth_headers_real: dict
    ):
        """Lors du logout, tous les tokens CSRF d'un utilisateur sont révoqués."""
        # Générer 3 tokens CSRF
        tokens = []
        for _ in range(3):
            response = client.get("/api/v1/auth/csrf", headers=auth_headers_real)
            tokens.append(response.json()["csrf_token"])

        # Révoquer tous les tokens (simulate logout)
        revoked_count = redis_client.revoke_all_csrf_tokens(test_user.id)
        assert revoked_count >= 3

        # Aucun token valide
        for token in tokens:
            assert redis_client.validate_csrf_token(test_user.id, token) is False

    def test_csrf_token_tied_to_user(
        self,
        client: TestClient,
        test_user: User,
        test_user_tenant2: User,
        auth_headers_real: dict,
        auth_headers_tenant2: dict
    ):
        """Un token CSRF d'un user ne peut pas être utilisé par un autre user."""
        # User 1 génère un token CSRF
        response = client.get("/api/v1/auth/csrf", headers=auth_headers_real)
        csrf_token_user1 = response.json()["csrf_token"]

        # Token valide pour user1
        assert redis_client.validate_csrf_token(test_user.id, csrf_token_user1) is True

        # Token invalide pour user2 (pas dans Redis avec user2_id)
        assert redis_client.validate_csrf_token(test_user_tenant2.id, csrf_token_user1) is False

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
        assert "CSRF token invalide" in response.json()["detail"]

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
        assert "CSRF token invalide" in response.json()["detail"]
