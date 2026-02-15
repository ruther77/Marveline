"""Tests d'intégration pour les endpoints d'authentification.

Enrichi en Session 2G : case-insensitive login, email trimming,
error consistency, CSRF, JTI claims.
"""
import pytest
from fastapi.testclient import TestClient

from tests.conftest import csrf_token_for_user


def test_login_success(client: TestClient, test_user):
    """Test login réussi avec credentials valides."""
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "test@carocorp.com",  # OAuth2 spec uses 'username'
            "password": "testpass123"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800  # 30 minutes


def test_login_wrong_password(client: TestClient, test_user):
    """Test login avec mot de passe incorrect → 401."""
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "test@carocorp.com",
            "password": "wrongpassword"
        }
    )

    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_nonexistent_user(client: TestClient):
    """Test login avec email inexistant → 401."""
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "nonexistent@example.com",
            "password": "somepassword"
        }
    )

    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_inactive_user(client: TestClient, test_db, test_user):
    """Test login avec compte inactif → 403."""
    # Désactiver le compte
    test_user.is_active = False
    test_db.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "test@carocorp.com",
            "password": "testpass123"
        }
    )

    assert response.status_code == 403
    assert "Account is inactive" in response.json()["detail"]

    # Réactiver pour les autres tests
    test_user.is_active = True
    test_db.commit()


def test_refresh_token_success(client: TestClient, test_user):
    """Test refresh token valide génère nouveau access token."""
    # Login pour obtenir refresh token
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "test@carocorp.com",
            "password": "testpass123"
        }
    )
    refresh_token = login_response.json()["refresh_token"]

    # Utiliser refresh token
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != refresh_token  # Rotation: nouveau refresh token
    assert data["token_type"] == "bearer"


def test_refresh_token_invalid(client: TestClient):
    """Test refresh token invalide → 401."""
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid_token_string"}
    )

    assert response.status_code == 401


def test_refresh_token_with_access_token(client: TestClient, test_user, auth_token):
    """Test refresh avec access token au lieu de refresh token → 401."""
    # Tenter d'utiliser access token comme refresh token
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": auth_token}  # Access token, pas refresh
    )

    assert response.status_code == 401
    # Le service doit détecter que le token type != "refresh"


def test_jwt_token_contains_correct_claims(test_user, auth_token):
    """Test que le JWT token contient les claims corrects."""
    from app.core.security import decode_token

    # Décoder token directement (évite rate limiting du login endpoint)
    payload = decode_token(auth_token)

    assert payload is not None
    assert payload["sub"] == str(test_user.id)  # sub est une string selon RFC 7519
    assert payload["tenant_id"] == test_user.tenant_id
    assert payload["email"] == test_user.email
    assert payload["role"] == test_user.role
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload


class TestCaseInsensitiveLogin:
    """Login doit être insensible à la casse de l'email."""

    def test_login_uppercase_email(self, client, test_user):
        """Login avec email en MAJUSCULES doit fonctionner."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "TEST@CAROCORP.COM", "password": "testpass123"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_mixed_case_email(self, client, test_user):
        """Login avec email en casse mixte doit fonctionner."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "Test@CaroCorp.Com", "password": "testpass123"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_email_with_leading_trailing_spaces(self, client, test_user):
        """Login avec espaces autour de l'email doit fonctionner."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "  test@carocorp.com  ", "password": "testpass123"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()


class TestLoginErrorConsistency:
    """Les messages d'erreur ne doivent pas révéler si le compte existe."""

    def test_wrong_password_and_nonexistent_same_message(self, client, test_user):
        """Mauvais password et user inexistant retournent le même message."""
        resp_wrong_pw = client.post(
            "/api/v1/auth/login",
            data={"username": "test@carocorp.com", "password": "wrongpassword"},
        )
        resp_no_user = client.post(
            "/api/v1/auth/login",
            data={"username": "ghost@nowhere.com", "password": "wrongpassword"},
        )
        assert resp_wrong_pw.status_code == 401
        assert resp_no_user.status_code == 401
        assert resp_wrong_pw.json()["detail"] == resp_no_user.json()["detail"]

    def test_login_empty_email_rejected(self, client):
        """Login avec email vide → rejeté."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "", "password": "somepassword"},
        )
        assert response.status_code in (401, 422)

    def test_login_empty_password_rejected(self, client, test_user):
        """Login avec password vide → rejeté."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "test@carocorp.com", "password": ""},
        )
        assert response.status_code in (401, 422)


class TestLoginTokenClaims:
    """Vérifications avancées sur les tokens retournés par login."""

    def test_access_token_has_jti(self, client, test_user):
        """L'access token retourné doit contenir un JTI (JWT ID)."""
        from app.core.security import decode_token

        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "test@carocorp.com", "password": "testpass123"},
        )
        assert resp.status_code == 200
        payload = decode_token(resp.json()["access_token"])
        assert "jti" in payload, "Access token must have a JTI"
        assert len(payload["jti"]) > 10, "JTI should be a UUID-like string"

    def test_refresh_token_has_jti(self, client, test_user):
        """Le refresh token retourné doit contenir un JTI."""
        from app.core.security import decode_token

        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "test@carocorp.com", "password": "testpass123"},
        )
        assert resp.status_code == 200
        payload = decode_token(resp.json()["refresh_token"])
        assert "jti" in payload, "Refresh token must have a JTI"

    def test_csrf_token_returned_after_login(self, client, test_user):
        """Le endpoint CSRF doit fonctionner après login."""
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "test@carocorp.com", "password": "testpass123"},
        )
        access = resp.json()["access_token"]

        csrf_resp = client.get(
            "/api/v1/auth/csrf",
            headers={"Authorization": f"Bearer {access}"},
        )
        assert csrf_resp.status_code == 200
        assert "csrf_token" in csrf_resp.json()

    def test_access_and_refresh_tokens_are_different(self, client, test_user):
        """Access et refresh tokens ne sont jamais identiques."""
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "test@carocorp.com", "password": "testpass123"},
        )
        data = resp.json()
        assert data["access_token"] != data["refresh_token"]

    def test_login_response_structure(self, client, test_user):
        """La réponse de login contient tous les champs attendus."""
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "test@carocorp.com", "password": "testpass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        required_keys = {"access_token", "refresh_token", "token_type", "expires_in"}
        assert required_keys.issubset(data.keys())
