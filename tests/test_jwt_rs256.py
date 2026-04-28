"""Tests JWT RS256 — claims v3, JWKS, rejet algorithmes non-RS256 (Phase 9).

Couvre spec §01-CRYPTO-JWT §1.2-1.6 :
  - Claims access token v3 complets
  - Claims refresh token v3 complets
  - Vérification signature RSA (rejet HS256)
  - Tolérance horloge ±30s
  - Endpoint JWKS /.well-known/jwks.json
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decode_access_token,
)
from app.core.exceptions import TokenExpired, TokenInvalid
from app.constants import TokenType


# ── Fixtures clés RSA de test ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def rsa_keypair():
    """Paire de clés RSA 2048 bits générée pour les tests."""
    priv = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    return priv, priv.public_key()


@pytest.fixture(scope="module")
def patched_keys(rsa_keypair):
    """Patche les 4 fonctions de clés RSA avec la paire de test."""
    priv, pub = rsa_keypair
    with (
        patch("app.core.security._get_private_key", return_value=priv),
        patch("app.core.security._get_public_key", return_value=pub),
        patch("app.core.security._get_refresh_private_key", return_value=priv),
        patch("app.core.security._get_refresh_public_key", return_value=pub),
    ):
        yield priv, pub


# ── Claims access token ──────────────────────────────────────────────────────

class TestAccessTokenClaims:
    """§1.2 — Access token v3 : claims obligatoires."""

    def test_access_token_has_standard_claims(self, patched_keys):
        """Vérifie les claims RFC 7519 : iss, sub, aud, exp, nbf, iat, jti."""
        token = create_access_token({"sub": "42", "tid": "1", "role": "staff", "scopes": []})
        payload = decode_token(token)
        for claim in ("iss", "sub", "aud", "exp", "nbf", "iat", "jti"):
            assert claim in payload, f"claim '{claim}' absent du access token"

    def test_access_token_has_carocorp_claims(self, patched_keys):
        """Vérifie les claims CaroCorp custom : tid, role, scopes, did, sid."""
        token = create_access_token({
            "sub": "42", "tid": "1", "role": "manager",
            "scopes": ["reservations:read"], "did": "dev_abc", "sid": "sess_xyz",
        })
        payload = decode_token(token)
        assert payload["tid"] == "1"
        assert payload["role"] == "manager"
        assert "reservations:read" in payload["scopes"]
        assert payload["did"] == "dev_abc"
        assert payload["sid"] == "sess_xyz"

    def test_access_token_type_is_access(self, patched_keys):
        """Le claim 'type' doit valoir 'access' (§1.2)."""
        token = create_access_token({"sub": "1"})
        payload = decode_token(token)
        assert payload["type"] == TokenType.ACCESS

    def test_access_token_sid_present(self, patched_keys):
        """Decision D2 — sid présent dans l'access token (§06 §6.12 anti-IDOR)."""
        token = create_access_token({"sub": "1", "sid": "session-uuid"})
        payload = decode_token(token)
        assert "sid" in payload
        assert payload["sid"] == "session-uuid"

    def test_access_token_fid_absent(self, patched_keys):
        """fid retiré de l'access token en v3 (§1.4 BREAKING)."""
        token = create_access_token({"sub": "1"})
        payload = decode_token(token)
        assert "fid" not in payload

    def test_access_token_sub_is_string(self, patched_keys):
        """RFC 7519 : sub MUST be string — même si passé en int."""
        token = create_access_token({"sub": 99})
        payload = decode_token(token)
        assert isinstance(payload["sub"], str)
        assert payload["sub"] == "99"

    def test_access_token_jti_is_uuid(self, patched_keys):
        """jti doit être un UUID v4 valide."""
        token = create_access_token({"sub": "1"})
        payload = decode_token(token)
        jti = payload["jti"]
        uuid.UUID(jti)  # lève ValueError si invalide


# ── Claims refresh token ─────────────────────────────────────────────────────

class TestRefreshTokenClaims:
    """§1.3 — Refresh token v3 : claims obligatoires."""

    def test_refresh_token_has_no_audience(self, patched_keys):
        """Refresh token sans claim 'aud' (intentionnel §1.3)."""
        token = create_refresh_token({"sub": "42", "tid": "1", "fid": "fam_abc"})
        payload = decode_token(token)
        assert "aud" not in payload

    def test_refresh_token_type_is_refresh(self, patched_keys):
        """Le claim 'type' doit valoir 'refresh'."""
        token = create_refresh_token({"sub": "1", "tid": "1", "fid": "fam_abc"})
        payload = decode_token(token)
        assert payload["type"] == TokenType.REFRESH

    def test_refresh_token_has_fid(self, patched_keys):
        """fid (family_id) obligatoire dans le refresh token (§1.3)."""
        family = str(uuid.uuid4())
        token = create_refresh_token({"sub": "1", "tid": "1", "fid": family})
        payload = decode_token(token)
        assert payload["fid"] == family

    def test_refresh_token_has_sid(self, patched_keys):
        """sid ajouté en v3 dans le refresh token (§1.4 BREAKING)."""
        token = create_refresh_token({"sub": "1", "tid": "1", "fid": "f", "sid": "s123"})
        payload = decode_token(token)
        assert payload["sid"] == "s123"


# ── Validation signature ─────────────────────────────────────────────────────

class TestJWTValidation:
    """§1.6 — Vérification signature RSA et rejet des tokens invalides."""

    def test_decode_valid_access_token(self, patched_keys):
        """Un token RS256 valide doit être décodé sans erreur."""
        token = create_access_token({"sub": "1", "tid": "1", "role": "staff"})
        payload = decode_token(token)
        assert payload["sub"] == "1"

    def test_decode_rejects_expired_token(self, patched_keys):
        """Un token expiré depuis >30s (hors tolérance skew ±30s) lève TokenExpired."""
        expired_token = create_access_token(
            {"sub": "1"},
            expires_delta=timedelta(seconds=-60),  # -60s > tolérance ±30s
        )
        with pytest.raises(TokenExpired):
            decode_token(expired_token)

    def test_decode_rejects_hs256_token(self, patched_keys):
        """Un token signé HS256 (au lieu de RS256) doit être rejeté (TokenInvalid)."""
        import jwt as pyjwt
        hs256_token = pyjwt.encode(
            {"sub": "1", "iat": datetime.now(timezone.utc),
             "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
             "jti": str(uuid.uuid4()), "iss": "test"},
            "some-hmac-secret",
            algorithm="HS256",
        )
        with pytest.raises(TokenInvalid):
            decode_token(hs256_token)

    def test_decode_rejects_malformed_token(self, patched_keys):
        """Un token malformé lève TokenInvalid."""
        with pytest.raises(TokenInvalid):
            decode_token("not.a.valid.jwt.token")

    def test_decode_access_token_checks_audience(self, patched_keys):
        """decode_access_token vérifie le claim 'aud' (§1.6)."""
        # Token valide avec bonne audience → OK
        token = create_access_token({"sub": "1"})
        payload = decode_access_token(token)
        assert payload is not None

    def test_decode_access_token_rejects_wrong_audience(self, patched_keys):
        """decode_access_token rejette un refresh token (pas d'aud) — TokenInvalid."""
        refresh = create_refresh_token({"sub": "1", "tid": "1", "fid": "f"})
        with pytest.raises(TokenInvalid):
            decode_access_token(refresh)

    def test_two_tokens_have_different_jtis(self, patched_keys):
        """Chaque token doit avoir un JTI unique."""
        t1 = create_access_token({"sub": "1"})
        t2 = create_access_token({"sub": "1"})
        p1, p2 = decode_token(t1), decode_token(t2)
        assert p1["jti"] != p2["jti"]


# ── JWKS endpoint ────────────────────────────────────────────────────────────

class TestJWKSEndpoint:
    """§1.5 — Endpoint /.well-known/jwks.json."""

    def test_jwks_returns_200(self):
        """L'endpoint JWKS doit retourner 200 avec les clés publiques."""
        from fastapi.testclient import TestClient
        from app.main import create_application
        from unittest.mock import patch

        mock_jwks = {
            "keys": [{
                "kty": "RSA", "use": "sig", "alg": "RS256",
                "n": "sIm1l0", "e": "AQAB", "kid": "access-v1",
            }]
        }
        with patch("app.api.jwks.get_jwks_response", return_value=mock_jwks):
            app = create_application()
            client = TestClient(app)
            response = client.get("/.well-known/jwks.json")
        assert response.status_code == 200

    def test_jwks_contains_keys_array(self):
        """JWKS doit contenir un tableau 'keys' non vide."""
        from fastapi.testclient import TestClient
        from app.main import create_application
        from unittest.mock import patch

        mock_jwks = {"keys": [{"kty": "RSA", "kid": "test"}]}
        with patch("app.api.jwks.get_jwks_response", return_value=mock_jwks):
            app = create_application()
            client = TestClient(app)
            response = client.get("/.well-known/jwks.json")

        data = response.json()
        assert "keys" in data
        assert len(data["keys"]) > 0
