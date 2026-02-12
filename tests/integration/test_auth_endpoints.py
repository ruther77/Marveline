"""Tests d'intégration pour les endpoints d'authentification."""
import pytest
from fastapi.testclient import TestClient


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
    assert "Incorrect email or password" in response.json()["detail"]


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
    assert "Incorrect email or password" in response.json()["detail"]


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
    assert data["refresh_token"] == refresh_token  # Même refresh token retourné
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


def test_jwt_token_contains_correct_claims(client: TestClient, test_user):
    """Test que le JWT token contient les claims corrects."""
    from app.core.security import decode_token

    # Login
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "test@carocorp.com",
            "password": "testpass123"
        }
    )
    access_token = login_response.json()["access_token"]

    # Décoder token (sans vérification signature pour test)
    payload = decode_token(access_token)

    assert payload is not None
    assert payload["sub"] == str(test_user.id)  # sub est une string selon RFC 7519
    assert payload["tenant_id"] == test_user.tenant_id
    assert payload["email"] == test_user.email
    assert payload["role"] == test_user.role
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload
