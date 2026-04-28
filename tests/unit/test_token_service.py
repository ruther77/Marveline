"""Tests unitaires pour app/services/token.py — v3 lifecycle (issue/rotate/revoke).

Couvre :
    - issue_tokens (claims v3, redis whitelist, scopes RBAC)
    - is_refresh_whitelisted / is_access_blacklisted
    - rotate_refresh_token (chemin Lua + fallback _manual_rotate)
    - revoke_on_logout (blacklist access, suppr whitelist + session)
    - revoke_all_user_tokens
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.exceptions import TokenReplayDetected, TokenRevoked
from app.core.security import decode_token
from app.services.token import TokenService, token_service
from app.core.config import settings

SCOPES_STAFF = ["users:read", "items:read", "reports:read"]


# ── Fixtures RSA + RBAC ───────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def rsa_test_keys():
    """Paire RSA 2048 temporaire (generee une seule fois par module)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture(autouse=True)
def mock_jwt_keys(rsa_test_keys):
    """Patch les cles JWT — evite la dependance aux fichiers PEM."""
    private_key, public_key = rsa_test_keys
    with patch("app.core.security._get_private_key", return_value=private_key), \
         patch("app.core.security._get_public_key", return_value=public_key):
        yield private_key, public_key


@pytest.fixture(autouse=True)
def mock_rbac():
    """Patch RBAC — get_role_scopes retourne des scopes fixes (async)."""
    with patch("app.services.rbac.get_role_scopes", new=AsyncMock(return_value=SCOPES_STAFF)):
        yield


# ── Helper ────────────────────────────────────────────────────────────────────

async def _issue_rt(user_id=1, tenant_id=1, device_id="dev1", session_id="sess1") -> str:
    """Genere un refresh token de test via issue_tokens (redis_sec mocke)."""
    with patch("app.services.token.redis_sec", new_callable=AsyncMock):
        _, rt, _ = await token_service.issue_tokens(
            user_id=user_id, tenant_id=tenant_id, role="staff",
            device_id=device_id, session_id=session_id,
        )
    return rt


# ── issue_tokens ──────────────────────────────────────────────────────────────

class TestIssueTokens:

    async def test_returns_three_tuple(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock):
            result = await token_service.issue_tokens(
                user_id=1, tenant_id=1, role="staff",
                device_id="d1", session_id="s1",
            )
        assert isinstance(result, tuple) and len(result) == 3

    async def test_access_and_refresh_are_jwt(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock):
            at, rt, _ = await token_service.issue_tokens(1, 1, "staff", "d1", "s1")
        assert at.count(".") == 2
        assert rt.count(".") == 2

    async def test_expires_in_is_positive_int(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock):
            _, _, exp = await token_service.issue_tokens(1, 1, "staff", "d1", "s1")
        assert isinstance(exp, int) and exp > 0

    async def test_access_claims_v3_structure(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock):
            at, _, _ = await token_service.issue_tokens(5, 2, "staff", "did2", "sid2")
        payload = decode_token(at)
        assert payload["sub"] == "5"
        assert payload["tid"] == "2"
        assert payload["did"] == "did2"
        assert payload["sid"] == "sid2"
        assert payload["role"] == "staff"   # spec $01 $1.2 : claim obligatoire
        assert "email" not in payload

    async def test_access_claims_include_scopes(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock):
            at, _, _ = await token_service.issue_tokens(7, 3, "staff", "d1", "s1")
        payload = decode_token(at)
        assert payload.get("scopes") == SCOPES_STAFF

    async def test_refresh_claims_include_fid_did_sid(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock):
            _, rt, _ = await token_service.issue_tokens(1, 1, "staff", "d1", "s1")
        payload = decode_token(rt)
        assert "fid" in payload
        assert payload["did"] == "d1"
        assert payload["sid"] == "s1"

    async def test_redis_whitelist_and_family_stored(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            await token_service.issue_tokens(42, 5, "staff", "did1", "sid1")
        mock_redis.store_refresh_jti.assert_awaited_once()
        mock_redis.store_token_family.assert_awaited_once()


# ── is_refresh_whitelisted ────────────────────────────────────────────────────

class TestIsRefreshWhitelisted:

    async def test_whitelisted_when_jti_present(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            mock_redis.get_refresh_jti.return_value = "some-jti"
            assert await token_service.is_refresh_whitelisted(1, "did", "sid") is True

    async def test_not_whitelisted_when_absent(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            mock_redis.get_refresh_jti.return_value = None
            assert await token_service.is_refresh_whitelisted(1, "did", "sid") is False


# ── is_access_blacklisted ─────────────────────────────────────────────────────

class TestIsAccessBlacklisted:

    async def test_blacklisted(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            mock_redis.is_access_blacklisted.return_value = True
            assert await token_service.is_access_blacklisted("jti-abc") is True

    async def test_not_blacklisted(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            mock_redis.is_access_blacklisted.return_value = False
            assert await token_service.is_access_blacklisted("jti-abc") is False


# ── rotate_refresh_token — fallback _manual_rotate ───────────────────────────

class TestRotateRefreshTokenFailClosed:
    """Lua non disponible -> _manual_rotate refuse la rotation (fail-closed F1)."""

    async def test_lua_unavailable_raises_runtime_error(self):
        """Quand evalsha leve RuntimeError, _manual_rotate propage RuntimeError."""
        rt = await _issue_rt()

        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            mock_redis.evalsha.side_effect = RuntimeError("Lua not loaded")

            with pytest.raises(RuntimeError, match="Lua scripts requis"):
                await token_service.rotate_refresh_token(rt, 1, 1, "staff")


# ── rotate_refresh_token — chemin Lua ────────────────────────────────────────

class TestRotateRefreshTokenLua:

    async def test_lua_ok_path_succeeds(self):
        rt = await _issue_rt()

        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            mock_redis.evalsha.return_value = "OK:some-new-jti"

            new_at, new_rt, exp = await token_service.rotate_refresh_token(rt, 1, 1, "staff")

        assert new_at.count(".") == 2
        assert isinstance(exp, int)

    async def test_lua_replay_detected_raises(self):
        rt = await _issue_rt()

        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            mock_redis.evalsha.return_value = "REPLAY_DETECTED"

            with pytest.raises(TokenReplayDetected):
                await token_service.rotate_refresh_token(rt, 1, 1, "staff")

    async def test_lua_token_invalid_raises(self):
        rt = await _issue_rt()

        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            mock_redis.evalsha.return_value = "TOKEN_INVALID"

            with pytest.raises(TokenRevoked):
                await token_service.rotate_refresh_token(rt, 1, 1, "staff")

    async def test_lua_unexpected_result_raises(self):
        rt = await _issue_rt()

        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            mock_redis.evalsha.return_value = "UNKNOWN_RESULT"

            with pytest.raises(TokenRevoked):
                await token_service.rotate_refresh_token(rt, 1, 1, "staff")


# ── revoke_on_logout ──────────────────────────────────────────────────────────

class TestRevokeOnLogout:

    async def test_blacklists_access_jti(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock):
            at, _, _ = await token_service.issue_tokens(1, 1, "staff", "d1", "s1")

        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            await token_service.revoke_on_logout(at, user_id=1, device_id="d1", session_id="s1")

        mock_redis.blacklist_access_jti.assert_awaited_once()
        jti_arg = mock_redis.blacklist_access_jti.call_args.args[0]
        assert isinstance(jti_arg, str)

    async def test_revokes_refresh_whitelist(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock):
            at, _, _ = await token_service.issue_tokens(1, 1, "staff", "d1", "s1")

        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            await token_service.revoke_on_logout(at, user_id=1, device_id="d1", session_id="s1")

        mock_redis.revoke_refresh_jti.assert_awaited_once_with(1, "d1", "s1")

    async def test_deletes_session_from_redis(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock):
            at, _, _ = await token_service.issue_tokens(1, 1, "staff", "d1", "s1")

        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            await token_service.revoke_on_logout(at, user_id=1, device_id="d1", session_id="s1")

        mock_redis.delete_session.assert_awaited_once_with(1, "d1", "s1")


# ── revoke_all_user_tokens ────────────────────────────────────────────────────

class TestRevokeAllUserTokens:

    async def test_delegates_to_redis_and_returns_count(self):
        with patch("app.services.token.redis_sec", new_callable=AsyncMock) as mock_redis:
            mock_redis.revoke_all_user_sessions.return_value = 3
            result = await token_service.revoke_all_user_tokens(user_id=5)
        mock_redis.revoke_all_user_sessions.assert_awaited_once_with(5)
        assert result == 3


# ── singleton ─────────────────────────────────────────────────────────────────

class TestSingleton:

    def test_token_service_is_singleton(self):
        from app.services.token import token_service as t1, token_service as t2
        assert t1 is t2

    def test_is_instance_of_token_service(self):
        assert isinstance(token_service, TokenService)
