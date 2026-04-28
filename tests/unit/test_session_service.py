"""Tests unitaires pour app/services/session.py — v3 async (DB + Redis dual-write).

Couvre :
    - generate_device_id (IPv4 /24, IPv6, SHA-256)
    - create_session (DB + Redis, mfa_verified)
    - _enforce_max_sessions (éviction Redis + DB, CSRF inclus — D1 with_for_update, D2 CSRF)
    - revoke_session / revoke_all_sessions
    - list_sessions / get_session / update_activity
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.session import (
    SessionService,
    session_service,
    generate_device_id,
)
from app.constants import SessionConfig
from app.models.account_session import AccountSession


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session(session_id: str, user_id: int = 1, device_id: str = "dev_abc") -> MagicMock:
    """Mock AccountSession avec attributs réalistes."""
    sess = MagicMock(spec=AccountSession)
    sess.session_id = session_id
    sess.account_id = user_id
    sess.device_id = device_id
    sess.tenant_id = 1
    sess.revoked_at = None
    sess.revoke_reason = None
    sess.mfa_verified = False
    sess.ip_address = "192.168.1.1"
    sess.user_agent = "TestAgent/1.0"
    sess.created_at = datetime.now(timezone.utc)
    sess.last_active_at = datetime.now(timezone.utc)
    return sess


def _membership_mock(membership_id: int = 1) -> MagicMock:
    """Crée un TenantMembership mock pour le lookup dans create_session."""
    m = MagicMock()
    m.id = membership_id
    return m


def _async_db_mock(first_result=None, all_result=None, scalar_one_or_none=None) -> AsyncMock:
    """Mock AsyncSession SQLAlchemy — couvre execute/add/flush async."""
    db = AsyncMock()

    scalars = MagicMock()
    scalars.first.return_value = first_result
    scalars.all.return_value = all_result or []

    result = MagicMock()
    result.scalars.return_value = scalars
    result.scalar_one_or_none.return_value = scalar_one_or_none

    db.execute.return_value = result
    return db


def _redis_mock() -> MagicMock:
    """Mock redis_sec — toutes méthodes async."""
    r = MagicMock()
    r.store_session = AsyncMock()
    r.revoke_refresh_jti = AsyncMock()
    r.delete_session = AsyncMock()
    r.revoke_csrf_token = AsyncMock()
    r.revoke_all_user_sessions = AsyncMock()
    r.revoke_sessions_except_device = AsyncMock()
    r.update_session_activity = AsyncMock()
    return r


# ── generate_device_id ────────────────────────────────────────────────────────

class TestGenerateDeviceId:

    def test_returns_32_hex_chars(self):
        did = generate_device_id("Mozilla/5.0", "192.168.1.100")
        assert isinstance(did, str)
        assert len(did) == 32
        assert all(c in "0123456789abcdef" for c in did)

    def test_deterministic(self):
        assert (
            generate_device_id("Mozilla/5.0", "192.168.1.100")
            == generate_device_id("Mozilla/5.0", "192.168.1.100")
        )

    def test_same_ipv4_subnet_same_device_id(self):
        """Deux IPs dans le même /24 → même device_id."""
        did1 = generate_device_id("Mozilla/5.0", "192.168.1.50")
        did2 = generate_device_id("Mozilla/5.0", "192.168.1.99")
        assert did1 == did2

    def test_different_subnet_different_device_id(self):
        did1 = generate_device_id("Mozilla/5.0", "192.168.1.1")
        did2 = generate_device_id("Mozilla/5.0", "10.0.0.1")
        assert did1 != did2

    def test_different_user_agent_different_device_id(self):
        did1 = generate_device_id("Mozilla/5.0", "192.168.1.1")
        did2 = generate_device_id("curl/7.0", "192.168.1.1")
        assert did1 != did2

    def test_ipv6_handled(self):
        did = generate_device_id("Mozilla/5.0", "2001:db8::1")
        assert isinstance(did, str)
        assert len(did) == 32


# ── create_session ────────────────────────────────────────────────────────────

class TestCreateSession:

    async def test_returns_uuid_string(self):
        db = _async_db_mock(all_result=[], scalar_one_or_none=_membership_mock())
        with patch("app.services.session.redis_sec", _redis_mock()):
            sid = await session_service.create_session(
                db=db, user_id=1, tenant_id=1,
                device_id="dev_x", ip_address="127.0.0.1",
            )
        uuid.UUID(sid)  # lève ValueError si pas un UUID valide

    async def test_db_add_and_flush_called(self):
        db = _async_db_mock(all_result=[], scalar_one_or_none=_membership_mock())
        with patch("app.services.session.redis_sec", _redis_mock()):
            await session_service.create_session(
                db=db, user_id=1, tenant_id=1,
                device_id="dev_x", ip_address="127.0.0.1",
            )
        db.add.assert_called_once()
        db.flush.assert_called_once()

    async def test_redis_store_session_called_with_user_id(self):
        db = _async_db_mock(all_result=[], scalar_one_or_none=_membership_mock())
        redis = _redis_mock()
        with patch("app.services.session.redis_sec", redis):
            await session_service.create_session(
                db=db, user_id=42, tenant_id=5,
                device_id="dev_y", ip_address="10.0.0.1",
            )
        redis.store_session.assert_called_once()
        kwargs = redis.store_session.call_args.kwargs
        assert kwargs.get("user_id") == 42

    async def test_mfa_verified_stored_on_db_object(self):
        db = _async_db_mock(all_result=[], scalar_one_or_none=_membership_mock())
        with patch("app.services.session.redis_sec", _redis_mock()):
            await session_service.create_session(
                db=db, user_id=1, tenant_id=1,
                device_id="dev_x", ip_address="1.2.3.4",
                mfa_verified=True,
            )
        added = db.add.call_args.args[0]
        assert added.mfa_verified is True

    async def test_user_agent_optional(self):
        db = _async_db_mock(all_result=[], scalar_one_or_none=_membership_mock())
        with patch("app.services.session.redis_sec", _redis_mock()):
            sid = await session_service.create_session(
                db=db, user_id=1, tenant_id=1,
                device_id="dev_x", ip_address="1.2.3.4",
            )
        assert sid  # pas d'exception


# ── _enforce_max_sessions ─────────────────────────────────────────────────────

class TestEnforceMaxSessions:
    """_enforce_max_sessions testé via create_session."""

    async def test_no_eviction_below_max(self):
        existing = [
            _make_session(f"sid{i}", device_id=f"dev{i}")
            for i in range(SessionConfig.MAX_SESSIONS_PER_USER - 1)
        ]
        db = _async_db_mock(all_result=existing, scalar_one_or_none=_membership_mock())
        redis = _redis_mock()
        with patch("app.services.session.redis_sec", redis):
            await session_service.create_session(
                db=db, user_id=1, tenant_id=1,
                device_id="new_dev", ip_address="1.2.3.4",
            )
        redis.revoke_refresh_jti.assert_not_called()

    async def test_evicts_oldest_when_at_max(self):
        existing = [
            _make_session(f"sid{i}", device_id=f"dev{i}")
            for i in range(SessionConfig.MAX_SESSIONS_PER_USER)
        ]
        db = _async_db_mock(all_result=existing, scalar_one_or_none=_membership_mock())
        redis = _redis_mock()
        with patch("app.services.session.redis_sec", redis):
            await session_service.create_session(
                db=db, user_id=1, tenant_id=1,
                device_id="new_dev", ip_address="1.2.3.4",
            )
        assert redis.revoke_refresh_jti.call_count == 1
        assert redis.delete_session.call_count == 1

    async def test_evicts_multiple_when_over_max(self):
        extra = 2
        existing = [
            _make_session(f"sid{i}", device_id=f"dev{i}")
            for i in range(SessionConfig.MAX_SESSIONS_PER_USER + extra - 1)
        ]
        db = _async_db_mock(all_result=existing, scalar_one_or_none=_membership_mock())
        redis = _redis_mock()
        with patch("app.services.session.redis_sec", redis):
            await session_service.create_session(
                db=db, user_id=1, tenant_id=1,
                device_id="new_dev", ip_address="1.2.3.4",
            )
        assert redis.revoke_refresh_jti.call_count == extra

    async def test_eviction_revokes_csrf_token(self):
        """D2 — CSRF token révoqué pour chaque session évincée (évite CSRF orphelins)."""
        existing = [
            _make_session(f"evict-sid{i}", device_id=f"dev{i}")
            for i in range(SessionConfig.MAX_SESSIONS_PER_USER)
        ]
        db = _async_db_mock(all_result=existing, scalar_one_or_none=_membership_mock())
        redis = _redis_mock()
        with patch("app.services.session.redis_sec", redis):
            await session_service.create_session(
                db=db, user_id=1, tenant_id=1,
                device_id="new_dev", ip_address="1.2.3.4",
            )
        # 1 session évincée → revoke_csrf_token appelé 1 fois avec la plus ancienne
        redis.revoke_csrf_token.assert_called_once_with("evict-sid0")


# ── revoke_session ────────────────────────────────────────────────────────────

class TestRevokeSession:

    async def test_revokes_existing_session(self):
        sess = _make_session("sess-123", user_id=1, device_id="dev_abc")
        db = _async_db_mock(first_result=sess)
        redis = _redis_mock()
        with patch("app.services.session.redis_sec", redis):
            result = await session_service.revoke_session(db, "sess-123", user_id=1)
        assert result is True
        assert sess.revoked_at is not None
        redis.revoke_refresh_jti.assert_called_once_with(1, "dev_abc", "sess-123")
        redis.delete_session.assert_called_once_with(1, "dev_abc", "sess-123")
        redis.revoke_csrf_token.assert_called_once_with("sess-123")

    async def test_returns_false_when_not_found(self):
        db = _async_db_mock(first_result=None)
        redis = _redis_mock()
        with patch("app.services.session.redis_sec", redis):
            result = await session_service.revoke_session(db, "ghost", user_id=1)
        assert result is False
        redis.revoke_refresh_jti.assert_not_called()

    async def test_custom_reason_stored(self):
        sess = _make_session("sess-abc", device_id="dev_x")
        db = _async_db_mock(first_result=sess)
        with patch("app.services.session.redis_sec", _redis_mock()):
            await session_service.revoke_session(db, "sess-abc", user_id=1, reason="admin_revoke")
        assert sess.revoke_reason == "admin_revoke"

    async def test_default_reason_user_logout(self):
        sess = _make_session("sess-def", device_id="dev_y")
        db = _async_db_mock(first_result=sess)
        with patch("app.services.session.redis_sec", _redis_mock()):
            await session_service.revoke_session(db, "sess-def", user_id=1)
        assert sess.revoke_reason == "user_logout"


# ── revoke_all_sessions ───────────────────────────────────────────────────────

class TestRevokeAllSessions:

    async def test_marks_all_sessions_revoked(self):
        sessions = [_make_session(f"sid{i}") for i in range(3)]
        db = _async_db_mock(all_result=sessions)
        redis = _redis_mock()
        with patch("app.services.session.redis_sec", redis):
            count = await session_service.revoke_all_sessions(db, user_id=1)
        assert count == 3
        for sess in sessions:
            assert sess.revoked_at is not None
        redis.revoke_all_user_sessions.assert_called_once_with(1)

    async def test_returns_zero_if_no_sessions(self):
        db = _async_db_mock(all_result=[], scalar_one_or_none=_membership_mock())
        redis = _redis_mock()
        with patch("app.services.session.redis_sec", redis):
            count = await session_service.revoke_all_sessions(db, user_id=99)
        assert count == 0
        redis.revoke_all_user_sessions.assert_called_once_with(99)

    async def test_custom_reason(self):
        sessions = [_make_session("s1")]
        db = _async_db_mock(all_result=sessions)
        with patch("app.services.session.redis_sec", _redis_mock()):
            await session_service.revoke_all_sessions(db, user_id=1, reason="password_reset")
        assert sessions[0].revoke_reason == "password_reset"


# ── list_sessions ─────────────────────────────────────────────────────────────

class TestListSessions:

    async def test_returns_active_sessions(self):
        sessions = [_make_session(f"sid{i}") for i in range(3)]
        db = _async_db_mock(all_result=sessions)
        result = await session_service.list_sessions(db, user_id=1)
        assert len(result) == 3

    async def test_returns_empty_list(self):
        db = _async_db_mock(all_result=[], scalar_one_or_none=_membership_mock())
        result = await session_service.list_sessions(db, user_id=1)
        assert result == []


# ── get_session ───────────────────────────────────────────────────────────────

class TestGetSession:

    async def test_returns_session(self):
        sess = _make_session("sess-xyz")
        db = _async_db_mock(first_result=sess)
        result = await session_service.get_session(db, "sess-xyz")
        assert result is sess

    async def test_returns_none_when_not_found(self):
        db = _async_db_mock(first_result=None)
        result = await session_service.get_session(db, "missing")
        assert result is None


# ── update_activity ───────────────────────────────────────────────────────────

class TestUpdateActivity:

    async def test_updates_last_active_at(self):
        before = datetime.now(timezone.utc)
        sess = _make_session("sess-1", device_id="dev_z")
        db = _async_db_mock(first_result=sess)
        redis = _redis_mock()
        with patch("app.services.session.redis_sec", redis):
            result = await session_service.update_activity(
                db, "sess-1", user_id=1, device_id="dev_z",
            )
        assert result is True
        assert sess.last_active_at >= before
        redis.update_session_activity.assert_called_once_with(1, "dev_z", "sess-1")

    async def test_returns_false_when_not_found(self):
        db = _async_db_mock(first_result=None)
        redis = _redis_mock()
        with patch("app.services.session.redis_sec", redis):
            result = await session_service.update_activity(
                db, "ghost", user_id=1, device_id="dev_z",
            )
        assert result is False
        redis.update_session_activity.assert_not_called()


# ── singleton ─────────────────────────────────────────────────────────────────

class TestSingleton:

    def test_session_service_is_singleton(self):
        from app.services.session import session_service as s1, session_service as s2
        assert s1 is s2

    def test_is_instance_of_session_service(self):
        assert isinstance(session_service, SessionService)
