"""Tests cycle de vie des tokens — rotation, replay, family revocation (Phase 9).

Couvre spec §02-TOKEN-LIFECYCLE §2.1-2.9 :
  - Émission access + refresh tokens (issue_tokens)
  - Rotation atomique via Lua (rotate_refresh_token)
  - Replay detection → family entière révoquée
  - Révocation au logout (revoke_on_logout)
  - Révocation globale (revoke_all_user_tokens)
"""
import uuid
from datetime import timedelta
from unittest.mock import patch, MagicMock, call

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from app.services.token import TokenService
from app.core.security import decode_token
from app.core.exceptions import TokenRevoked, TokenReplayDetected
from app.constants import Limits, TokenType


# ── Fixtures partagées ───────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def rsa_keypair():
    priv = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    return priv, priv.public_key()


@pytest.fixture(scope="module")
def patched_keys(rsa_keypair):
    priv, pub = rsa_keypair
    with (
        patch("app.core.security._get_private_key", return_value=priv),
        patch("app.core.security._get_public_key", return_value=pub),
        patch("app.core.security._get_refresh_private_key", return_value=priv),
        patch("app.core.security._get_refresh_public_key", return_value=pub),
    ):
        yield


@pytest.fixture
def token_service():
    return TokenService()


@pytest.fixture
def mock_redis():
    with patch("app.services.token.redis_sec") as mock:
        mock.get_refresh_jti.return_value = "old-jti"
        mock.family_exists.return_value = True
        yield mock


@pytest.fixture
def mock_rbac():
    with patch("app.services.rbac.get_role_scopes_sync", return_value=["reservations:read", "stock:read"]):
        yield


# ── Émission tokens (§2.1) ───────────────────────────────────────────────────

class TestIssueTokens:
    """TokenService.issue_tokens() — structure et enregistrement Redis."""

    def test_returns_three_elements(self, patched_keys, mock_redis, mock_rbac, token_service):
        result = token_service.issue_tokens(
            user_id=1, tenant_id=1, role="staff",
            device_id="dev_abc", session_id="sess_123",
        )
        assert len(result) == 3

    def test_access_token_is_decodable(self, patched_keys, mock_redis, mock_rbac, token_service):
        at, _, _ = token_service.issue_tokens(1, 1, "staff", "dev_abc", "sess_123")
        payload = decode_token(at)
        assert payload["sub"] == "1"
        assert payload["did"] == "dev_abc"
        assert payload["sid"] == "sess_123"
        assert payload["role"] == "staff"
        assert payload["type"] == TokenType.ACCESS

    def test_refresh_token_has_family_id(self, patched_keys, mock_redis, mock_rbac, token_service):
        _, rt, _ = token_service.issue_tokens(1, 1, "staff", "dev_abc", "sess_123")
        payload = decode_token(rt)
        assert "fid" in payload
        assert payload["type"] == TokenType.REFRESH

    def test_expires_in_is_900(self, patched_keys, mock_redis, mock_rbac, token_service):
        """expires_in doit être JWT_ACCESS_TOKEN_EXPIRE_SECONDS (900s = 15min)."""
        _, _, expires_in = token_service.issue_tokens(1, 1, "staff", "dev_abc", "sess_123")
        assert expires_in == Limits.ACCESS_TOKEN_EXPIRE_SECONDS

    def test_redis_whitelist_called(self, patched_keys, mock_redis, mock_rbac, token_service):
        token_service.issue_tokens(1, 1, "staff", "dev_abc", "sess_123")
        mock_redis.store_refresh_jti.assert_called_once()

    def test_redis_family_called(self, patched_keys, mock_redis, mock_rbac, token_service):
        token_service.issue_tokens(1, 1, "staff", "dev_abc", "sess_123")
        mock_redis.store_token_family.assert_called_once()

    def test_redis_jti_meta_called(self, patched_keys, mock_redis, mock_rbac, token_service):
        token_service.issue_tokens(1, 1, "staff", "dev_abc", "sess_123")
        mock_redis.store_jti_meta.assert_called_once()


# ── Rotation via Lua (§2.6) ──────────────────────────────────────────────────

class TestRotateRefreshToken:
    """TokenService.rotate_refresh_token() — via Lua atomique."""

    def test_rotate_ok_returns_triple(self, patched_keys, mock_rbac, token_service):
        """Rotation OK → retourne (new_at, new_rt, expires_in)."""
        _, old_rt, _ = TokenService().issue_tokens(1, 1, "staff", "dev", "sess")

        with patch("app.services.token.redis_sec") as mock_redis:
            mock_redis.evalsha.return_value = "OK:new-jti"
            mock_redis.store_jti_meta.return_value = None
            result = token_service.rotate_refresh_token(old_rt, 1, 1, "staff")

        assert len(result) == 3

    def test_rotate_builds_new_access_token(self, patched_keys, mock_rbac, token_service):
        """Après rotation, le nouvel access token a les bons claims."""
        _, old_rt, _ = TokenService().issue_tokens(1, 1, "manager", "d1", "s1")

        with patch("app.services.token.redis_sec") as mock_redis:
            mock_redis.evalsha.return_value = "OK:new-jti"
            mock_redis.store_jti_meta.return_value = None
            new_at, _, _ = token_service.rotate_refresh_token(old_rt, 1, 1, "manager")

        payload = decode_token(new_at)
        assert payload["sub"] == "1"
        assert payload["role"] == "manager"

    def test_rotate_replay_detected_raises(self, patched_keys, mock_rbac, token_service):
        """REPLAY_DETECTED → lève TokenReplayDetected."""
        _, old_rt, _ = TokenService().issue_tokens(1, 1, "staff", "d2", "s2")

        with patch("app.services.token.redis_sec") as mock_redis:
            mock_redis.evalsha.return_value = "REPLAY_DETECTED"
            with pytest.raises(TokenReplayDetected):
                token_service.rotate_refresh_token(old_rt, 1, 1, "staff")

    def test_rotate_token_invalid_raises(self, patched_keys, mock_rbac, token_service):
        """TOKEN_INVALID → lève TokenRevoked."""
        _, old_rt, _ = TokenService().issue_tokens(1, 1, "staff", "d3", "s3")

        with patch("app.services.token.redis_sec") as mock_redis:
            mock_redis.evalsha.return_value = "TOKEN_INVALID"
            with pytest.raises(TokenRevoked):
                token_service.rotate_refresh_token(old_rt, 1, 1, "staff")

    def test_rotate_fallback_if_lua_not_loaded(self, patched_keys, mock_rbac, token_service):
        """Si Lua non chargé (RuntimeError) → fallback _manual_rotate."""
        _, old_rt, _ = TokenService().issue_tokens(1, 1, "staff", "d4", "s4")
        old_payload = decode_token(old_rt)
        old_jti = old_payload["jti"]

        with patch("app.services.token.redis_sec") as mock_redis:
            mock_redis.evalsha.side_effect = RuntimeError("Lua not loaded")
            mock_redis.get_refresh_jti.return_value = old_jti
            mock_redis.store_refresh_jti.return_value = True
            mock_redis.add_jti_to_family.return_value = True
            mock_redis.store_jti_meta.return_value = None
            result = token_service.rotate_refresh_token(old_rt, 1, 1, "staff")

        assert len(result) == 3


# ── Révocation au logout (§4.2) ──────────────────────────────────────────────

class TestRevokeOnLogout:
    """TokenService.revoke_on_logout() — blacklist JTI + suppression whitelist."""

    def test_revoke_blacklists_access_jti(self, patched_keys, mock_rbac, token_service):
        at, _, _ = TokenService().issue_tokens(1, 1, "staff", "d5", "s5")
        at_jti = decode_token(at)["jti"]

        with patch("app.services.token.redis_sec") as mock_redis:
            token_service.revoke_on_logout(at, user_id=1, device_id="d5", session_id="s5")
            mock_redis.blacklist_access_jti.assert_called_once()
            call_args = mock_redis.blacklist_access_jti.call_args
            assert call_args[0][0] == at_jti

    def test_revoke_removes_refresh_whitelist(self, patched_keys, mock_rbac, token_service):
        at, _, _ = TokenService().issue_tokens(1, 1, "staff", "d6", "s6")

        with patch("app.services.token.redis_sec") as mock_redis:
            token_service.revoke_on_logout(at, user_id=1, device_id="d6", session_id="s6")
            mock_redis.revoke_refresh_jti.assert_called_once_with(1, "d6", "s6")

    def test_revoke_deletes_session(self, patched_keys, mock_rbac, token_service):
        at, _, _ = TokenService().issue_tokens(1, 1, "staff", "d7", "s7")

        with patch("app.services.token.redis_sec") as mock_redis:
            token_service.revoke_on_logout(at, user_id=1, device_id="d7", session_id="s7")
            mock_redis.delete_session.assert_called_once_with(1, "d7", "s7")


# ── Révocation globale (§4.3) ────────────────────────────────────────────────

class TestRevokeAllUserTokens:
    """TokenService.revoke_all_user_tokens() — force-logout toutes les sessions."""

    def test_revoke_all_calls_redis(self, token_service):
        with patch("app.services.token.redis_sec") as mock_redis:
            mock_redis.revoke_all_user_sessions.return_value = 3
            count = token_service.revoke_all_user_tokens(user_id=42)
            mock_redis.revoke_all_user_sessions.assert_called_once_with(42)
            assert count == 3

    def test_is_access_blacklisted_delegates_to_redis(self, token_service):
        with patch("app.services.token.redis_sec") as mock_redis:
            mock_redis.is_access_blacklisted.return_value = True
            result = token_service.is_access_blacklisted("some-jti")
            assert result is True
            mock_redis.is_access_blacklisted.assert_called_once_with("some-jti")
