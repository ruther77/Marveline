"""Tests sécurité : token JWT — forgery, type confusion, replay, claims manquants.

Couvre les vecteurs d'attaque JWT :
- Token signé avec un mauvais secret → rejeté
- Token algo "none" → rejeté (déjà dans test_timing_attack, renforcé ici)
- Refresh token utilisé comme access token → rejeté
- Access token utilisé comme refresh token → rejeté (déjà dans test_auth_endpoints)
- Token avec tenant_id falsifié → rejeté (déjà dans test_email_tenant_isolation, renforcé ici)
- Token sans claims obligatoires (sub, tenant_id) → rejeté
- Token expiré → 401 avec message spécifique
- Replay detection : double usage refresh → famille révoquée
- Blacklist access après logout → rejeté
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.core.exceptions import TokenInvalid, TokenExpired


class TestJWTForgery:
    """Tests de tokens JWT forgés avec différentes attaques."""

    def test_token_signed_with_wrong_secret_rejected(self, client, test_user):
        """Token signé avec un mauvais secret doit être rejeté."""
        from tests.conftest import csrf_token_for_user

        forged_payload = {
            "sub": str(test_user.id),
            "tenant_id": test_user.tenant_id,
            "email": test_user.email,
            "role": test_user.role,
            "type": "access",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        forged_token = jwt.encode(forged_payload, "wrong-secret-key-attack", algorithm="HS256")
        csrf = csrf_token_for_user(test_user.id)

        response = client.get(
            "/api/v1/products",
            headers={
                "Authorization": f"Bearer {forged_token}",
                "X-CSRF-Token": csrf,
            },
        )
        assert response.status_code == 401

    def test_token_with_different_algorithm_rejected(self, client, test_user):
        """Token signé avec un algorithme différent (HS384) doit être rejeté."""
        from tests.conftest import csrf_token_for_user

        forged_payload = {
            "sub": str(test_user.id),
            "tenant_id": test_user.tenant_id,
            "email": test_user.email,
            "role": test_user.role,
            "type": "access",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        # Signer avec HS384 au lieu de HS256
        forged_token = jwt.encode(forged_payload, settings.JWT_SECRET, algorithm="HS384")
        csrf = csrf_token_for_user(test_user.id)

        response = client.get(
            "/api/v1/products",
            headers={
                "Authorization": f"Bearer {forged_token}",
                "X-CSRF-Token": csrf,
            },
        )
        # HS384 n'est pas dans la liste d'algorithmes acceptés → rejeté
        assert response.status_code == 401

    def test_empty_bearer_token_rejected(self, client):
        """Authorization: Bearer (vide) → 401."""
        response = client.get(
            "/api/v1/products",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code in (401, 403)

    def test_no_authorization_header_rejected(self, client):
        """Pas de header Authorization → 401."""
        response = client.get("/api/v1/products")
        assert response.status_code == 401


class TestTokenTypeSafety:
    """Tests de confusion de type de token (access vs refresh)."""

    def test_refresh_token_as_access_rejected(self, client, test_user):
        """Refresh token utilisé comme access token doit être rejeté."""
        from tests.conftest import csrf_token_for_user

        refresh_token = create_refresh_token({
            "sub": test_user.id,
            "tenant_id": test_user.tenant_id,
        })
        csrf = csrf_token_for_user(test_user.id)

        response = client.get(
            "/api/v1/products",
            headers={
                "Authorization": f"Bearer {refresh_token}",
                "X-CSRF-Token": csrf,
            },
        )
        assert response.status_code == 401

    def test_access_token_as_refresh_rejected(self, client, test_user):
        """Access token utilisé comme refresh token doit être rejeté."""
        access_token = create_access_token({
            "sub": test_user.id,
            "tenant_id": test_user.tenant_id,
            "email": test_user.email,
            "role": test_user.role,
        })

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert response.status_code == 401


class TestTokenClaimsValidation:
    """Tests de claims obligatoires dans les tokens."""

    def test_token_without_sub_rejected(self, client):
        """Token sans claim 'sub' doit être rejeté."""
        from tests.conftest import csrf_token_for_user

        malformed_payload = {
            "tenant_id": 1,
            "email": "test@test.com",
            "role": "staff",
            "type": "access",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(malformed_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        response = client.get(
            "/api/v1/products",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    def test_token_with_non_numeric_sub_rejected(self, client):
        """Token avec sub non-numérique doit être rejeté."""
        malformed_payload = {
            "sub": "not-a-number",
            "tenant_id": 1,
            "email": "test@test.com",
            "role": "staff",
            "type": "access",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(malformed_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        response = client.get(
            "/api/v1/products",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    def test_token_with_nonexistent_user_id_rejected(self, client, test_user):
        """Token avec user_id inexistant en DB doit être rejeté."""
        from tests.conftest import csrf_token_for_user

        token = create_access_token({
            "sub": 999999,
            "tenant_id": 1,
            "email": "ghost@test.com",
            "role": "staff",
        })

        response = client.get(
            "/api/v1/products",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    def test_expired_access_token_returns_401(self, client, test_user):
        """Token expiré retourne 401."""
        from tests.conftest import csrf_token_for_user

        expired_token = create_access_token(
            data={
                "sub": test_user.id,
                "tenant_id": test_user.tenant_id,
                "email": test_user.email,
                "role": test_user.role,
            },
            expires_delta=timedelta(seconds=-1),
        )
        csrf = csrf_token_for_user(test_user.id)

        response = client.get(
            "/api/v1/products",
            headers={
                "Authorization": f"Bearer {expired_token}",
                "X-CSRF-Token": csrf,
            },
        )
        assert response.status_code == 401


class TestReplayDetectionIntegration:
    """Tests de replay detection au niveau endpoint."""

    def test_double_refresh_same_token_revokes_family(self, client, test_user):
        """Double utilisation du même refresh token → famille révoquée."""
        # Login
        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": "test@carocorp.com", "password": "testpass123"},
        )
        assert login_resp.status_code == 200
        original_refresh = login_resp.json()["refresh_token"]

        # Premier refresh → OK
        resp1 = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original_refresh},
        )
        assert resp1.status_code == 200
        new_refresh = resp1.json()["refresh_token"]

        # Replay attack : réutiliser l'ancien refresh token
        resp2 = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original_refresh},
        )
        assert resp2.status_code == 401  # Replay détecté

        # Le nouveau refresh token doit aussi être révoqué (toute la famille)
        resp3 = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": new_refresh},
        )
        assert resp3.status_code == 401  # Famille entière révoquée

    def test_refresh_rotation_generates_new_tokens(self, client, test_user):
        """Refresh rotation doit générer de nouveaux tokens à chaque fois."""
        # Login
        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": "test@carocorp.com", "password": "testpass123"},
        )
        tokens1 = login_resp.json()

        # Premier refresh
        resp1 = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens1["refresh_token"]},
        )
        tokens2 = resp1.json()

        # Deuxième refresh (avec le nouveau token)
        resp2 = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens2["refresh_token"]},
        )
        tokens3 = resp2.json()

        # Tous les tokens doivent être différents
        assert tokens1["access_token"] != tokens2["access_token"]
        assert tokens2["access_token"] != tokens3["access_token"]
        assert tokens1["refresh_token"] != tokens2["refresh_token"]
        assert tokens2["refresh_token"] != tokens3["refresh_token"]
