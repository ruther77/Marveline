"""Tests unitaires pour app/core/redis.py — RedisSecClient.

Couvre 8 domaines : CSRF, refresh whitelist, access blacklist,
token families, brute force, sessions, password reset, health.
Utilise Redis réel (Docker).
"""
import json
import time
import pytest

from app.core.redis import RedisSecClient, redis_sec, redis_client
from app.constants import RedisKeys, SessionConfig


# ── Fixture ──────────────────────────────────────────────────────────────

@pytest.fixture
def rc() -> RedisSecClient:
    """Instance fraîche de RedisSecClient (singleton global)."""
    return redis_sec


@pytest.fixture(autouse=True)
async def _load_lua_scripts():
    """Charge les scripts Lua avant chaque test (idempotent, requis pour evalsha)."""
    await redis_sec.load_lua_scripts()


# ── Singleton ────────────────────────────────────────────────────────────

class TestSingleton:
    def test_get_redis_sec_returns_same_instance(self):
        a = redis_sec
        b = redis_sec
        assert a is b

    def test_global_redis_client_is_redis_sec(self):
        assert redis_client is redis_sec


# ── Ping / Health ────────────────────────────────────────────────────────

class TestPingHealth:
    async def test_ping_returns_true(self, rc: RedisSecClient):
        assert await rc.ping() is True

    async def test_health_check_healthy(self, rc: RedisSecClient):
        result = await rc.health_check()
        assert result["status"] == "healthy"
        assert result["connected"] is True
        assert "redis_version" in result
        assert "uptime_seconds" in result

    async def test_health_check_returns_dict(self, rc: RedisSecClient):
        result = await rc.health_check()
        assert isinstance(result, dict)


# ── CSRF Tokens ──────────────────────────────────────────────────────────
# API v3 (refactor §04 §4.3) : CSRF indexé par session_id (pas user_id).
# store_csrf_token(session_id, token, ttl)
# validate_csrf_token(session_id, token) → bool
# revoke_csrf_token(session_id) → bool  (plus de param token)
# revoke_all_csrf_tokens(user_id) → int  (exception : itère via user_sessions_index)

class TestCSRF:
    async def test_store_csrf_token(self, rc: RedisSecClient):
        assert await rc.store_csrf_token(session_id="sid_1", token="tok_abc", ttl_seconds=60) is True

    async def test_validate_csrf_token_valid(self, rc: RedisSecClient):
        await rc.store_csrf_token(session_id="sid_1", token="tok_val", ttl_seconds=60)
        assert await rc.validate_csrf_token(session_id="sid_1", token="tok_val") is True

    async def test_validate_csrf_token_missing(self, rc: RedisSecClient):
        assert await rc.validate_csrf_token(session_id="sid_1", token="nonexistent") is False

    async def test_validate_csrf_wrong_session(self, rc: RedisSecClient):
        await rc.store_csrf_token(session_id="sid_1", token="tok_sid1", ttl_seconds=60)
        assert await rc.validate_csrf_token(session_id="sid_2", token="tok_sid1") is False

    async def test_revoke_csrf_token(self, rc: RedisSecClient):
        await rc.store_csrf_token(session_id="sid_1", token="tok_rev", ttl_seconds=60)
        assert await rc.revoke_csrf_token(session_id="sid_1") is True
        assert await rc.validate_csrf_token(session_id="sid_1", token="tok_rev") is False

    async def test_revoke_csrf_token_nonexistent(self, rc: RedisSecClient):
        assert await rc.revoke_csrf_token(session_id="sid_nope") is False

    async def test_revoke_all_csrf_tokens(self, rc: RedisSecClient):
        await rc.store_csrf_token(session_id="sid_10_1", token="t1", ttl_seconds=60)
        await rc.store_csrf_token(session_id="sid_10_2", token="t2", ttl_seconds=60)
        await rc.store_csrf_token(session_id="sid_10_3", token="t3", ttl_seconds=60)
        await rc.add_session_to_index(user_id=10, device_id="d1", session_id="sid_10_1", ttl_seconds=300)
        await rc.add_session_to_index(user_id=10, device_id="d2", session_id="sid_10_2", ttl_seconds=300)
        await rc.add_session_to_index(user_id=10, device_id="d3", session_id="sid_10_3", ttl_seconds=300)
        count = await rc.revoke_all_csrf_tokens(user_id=10)
        assert count == 3
        assert await rc.validate_csrf_token(session_id="sid_10_1", token="t1") is False

    async def test_revoke_all_csrf_tokens_no_tokens(self, rc: RedisSecClient):
        assert await rc.revoke_all_csrf_tokens(user_id=999) == 0

    async def test_csrf_ttl_respected(self, rc: RedisSecClient):
        await rc.store_csrf_token(session_id="sid_1", token="tok_ttl", ttl_seconds=1)
        assert await rc.validate_csrf_token(session_id="sid_1", token="tok_ttl") is True
        time.sleep(1.5)
        assert await rc.validate_csrf_token(session_id="sid_1", token="tok_ttl") is False


# ── Refresh Token Whitelist ──────────────────────────────────────────────

class TestRefreshWhitelist:
    # API v3 : whitelist:refresh:{uid}:{did}:{sid} = JTI (STRING)
    # Les 3 coords (user_id, device_id, session_id) identifient une session.

    async def test_store_and_get_refresh_jti(self, rc: RedisSecClient):
        assert await rc.store_refresh_jti(
            jti="jti_1", user_id=1, tenant_id=1, family_id="fam_1",
            device_id="dev1", session_id="sid1", ttl_seconds=300,
        ) is True
        stored = await rc.get_refresh_jti(user_id=1, device_id="dev1", session_id="sid1")
        assert stored == "jti_1"

    async def test_get_refresh_jti_nonexistent(self, rc: RedisSecClient):
        assert await rc.get_refresh_jti(user_id=99, device_id="devX", session_id="sidX") is None

    async def test_revoke_refresh_jti(self, rc: RedisSecClient):
        await rc.store_refresh_jti(
            jti="jti_rev", user_id=2, tenant_id=1, family_id="f1",
            device_id="dev2", session_id="sid_rev", ttl_seconds=300,
        )
        assert await rc.revoke_refresh_jti(user_id=2, device_id="dev2", session_id="sid_rev") is True
        assert await rc.get_refresh_jti(user_id=2, device_id="dev2", session_id="sid_rev") is None

    async def test_revoke_refresh_jti_nonexistent(self, rc: RedisSecClient):
        assert await rc.revoke_refresh_jti(user_id=99, device_id="ghost", session_id="ghost") is False

    async def test_revoke_all_sessions_for_user(self, rc: RedisSecClient):
        await rc.store_refresh_jti(
            jti="u5_a", user_id=5, tenant_id=1, family_id="f1",
            device_id="d1", session_id="s1", ttl_seconds=300,
        )
        await rc.store_refresh_jti(
            jti="u5_b", user_id=5, tenant_id=1, family_id="f2",
            device_id="d2", session_id="s2", ttl_seconds=300,
        )
        await rc.store_refresh_jti(
            jti="u6_a", user_id=6, tenant_id=1, family_id="f3",
            device_id="d3", session_id="s3", ttl_seconds=300,
        )
        await rc.add_session_to_index(5, "d1", "s1", 300)
        await rc.add_session_to_index(5, "d2", "s2", 300)
        await rc.add_session_to_index(6, "d3", "s3", 300)
        count = await rc.revoke_all_user_sessions(user_id=5)
        assert count == 2
        assert await rc.get_refresh_jti(user_id=5, device_id="d1", session_id="s1") is None
        assert await rc.get_refresh_jti(user_id=5, device_id="d2", session_id="s2") is None
        # user 6 intouché
        assert await rc.get_refresh_jti(user_id=6, device_id="d3", session_id="s3") == "u6_a"


# ── Access Token Blacklist ───────────────────────────────────────────────

class TestAccessBlacklist:
    async def test_blacklist_and_check(self, rc: RedisSecClient):
        assert await rc.blacklist_access_jti("acc_1", ttl_seconds=60) is True
        assert await rc.is_access_blacklisted("acc_1") is True

    async def test_not_blacklisted(self, rc: RedisSecClient):
        assert await rc.is_access_blacklisted("acc_clean") is False

    async def test_blacklist_ttl_expires(self, rc: RedisSecClient):
        await rc.blacklist_access_jti("acc_exp", ttl_seconds=1)
        assert await rc.is_access_blacklisted("acc_exp") is True
        time.sleep(1.5)
        assert await rc.is_access_blacklisted("acc_exp") is False


# ── Token Family ─────────────────────────────────────────────────────────

class TestTokenFamily:
    # API v3 : family:{fid} = SET de JTIs
    # store_token_family(family_id, jti, ttl) → add JTI au SET
    # family_exists(fid) → bool
    # is_jti_in_family(fid, jti) → bool
    # revoke_token_family(fid) → supprime la clé entière

    async def test_store_and_family_exists(self, rc: RedisSecClient):
        await rc.store_token_family(family_id="fam_a", jti="jti_test_a", ttl_seconds=300)
        assert await rc.family_exists("fam_a") is True

    async def test_is_jti_in_family(self, rc: RedisSecClient):
        await rc.store_token_family(family_id="fam_b", jti="jti_b1", ttl_seconds=300)
        assert await rc.is_jti_in_family("fam_b", "jti_b1")   # 1 ou True selon redis-py version
        assert not await rc.is_jti_in_family("fam_b", "jti_other")

    async def test_family_not_exists(self, rc: RedisSecClient):
        assert await rc.family_exists("fam_nope") is False

    async def test_revoke_family_deletes_key(self, rc: RedisSecClient):
        await rc.store_token_family(family_id="fam_rev", jti="jti_rev", ttl_seconds=300)
        assert await rc.revoke_token_family("fam_rev") is True
        assert await rc.family_exists("fam_rev") is False

    async def test_revoke_nonexistent_family(self, rc: RedisSecClient):
        assert await rc.revoke_token_family("fam_ghost") is False


# ── Brute Force Counters ────────────────────────────────────────────────

class TestBruteForce:
    # API v3 : increment_brute_force(key, ttl_seconds) — clé complète
    # Utiliser RedisKeys.brute_force_user/ip/device pour construire la clé.

    async def test_increment_returns_count(self, rc: RedisSecClient):
        key = RedisKeys.brute_force_user(uid=1001)
        count = await rc.increment_brute_force(key, ttl_seconds=60)
        assert count == 1
        count2 = await rc.increment_brute_force(key, ttl_seconds=60)
        assert count2 == 2

    async def test_get_brute_force_count(self, rc: RedisSecClient):
        key = RedisKeys.brute_force_user(uid=1002)
        await rc.increment_brute_force(key, ttl_seconds=60)
        await rc.increment_brute_force(key, ttl_seconds=60)
        assert await rc.get_brute_force_count(key) == 2

    async def test_get_brute_force_count_zero(self, rc: RedisSecClient):
        key = RedisKeys.brute_force_user(uid=9999)
        assert await rc.get_brute_force_count(key) == 0

    async def test_reset_brute_force(self, rc: RedisSecClient):
        key = RedisKeys.brute_force_user(uid=1003)
        await rc.increment_brute_force(key, ttl_seconds=60)
        assert await rc.reset_brute_force(key) is True
        assert await rc.get_brute_force_count(key) == 0

    async def test_set_and_check_lock(self, rc: RedisSecClient):
        await rc.set_brute_force_lock("locked@x.com", ttl_seconds=60)
        assert await rc.is_brute_force_locked("locked@x.com") is True

    async def test_not_locked(self, rc: RedisSecClient):
        assert await rc.is_brute_force_locked("free@x.com") is False

    async def test_lock_ttl(self, rc: RedisSecClient):
        await rc.set_brute_force_lock("ttl@x.com", ttl_seconds=120)
        ttl = await rc.get_brute_force_lock_ttl("ttl@x.com")
        assert 0 < ttl <= 120

    async def test_lock_ttl_no_lock(self, rc: RedisSecClient):
        assert await rc.get_brute_force_lock_ttl("nolock@x.com") == 0

    async def test_alert_sent_idempotent(self, rc: RedisSecClient):
        assert await rc.set_brute_force_alert_sent("alert@x.com", ttl_seconds=60) is True
        result = await rc.set_brute_force_alert_sent("alert@x.com", ttl_seconds=60)
        assert result is None or result is False

    async def test_ip_counter_separate_from_user(self, rc: RedisSecClient):
        key_ip = RedisKeys.brute_force_ip(ip_hash="1.2.3.4")
        key_user = RedisKeys.brute_force_user(uid=2001)
        await rc.increment_brute_force(key_ip, ttl_seconds=60)
        await rc.increment_brute_force(key_user, ttl_seconds=60)
        assert await rc.get_brute_force_count(key_ip) == 1
        assert await rc.get_brute_force_count(key_user) == 1


# ── Sessions ─────────────────────────────────────────────────────────────

class TestSessions:
    # API v3 : session:{uid}:{did}:{sid} = HASH
    # store_session(user_id, device_id, session_id, data, ttl_seconds)
    # get_session(user_id, device_id, session_id) → dict | None
    # delete_session(user_id, device_id, session_id)
    # update_session_activity(user_id, device_id, session_id, ttl_seconds)
    # list_user_session_ids(user_id) → list["did:sid"]

    async def test_store_and_get_session(self, rc: RedisSecClient):
        data = {"ip": "1.2.3.4", "ua": "Chrome"}
        assert await rc.store_session(
            user_id=1, device_id="dev1", session_id="sess_1",
            data=data, ttl_seconds=300,
        ) is True
        result = await rc.get_session(user_id=1, device_id="dev1", session_id="sess_1")
        assert result is not None
        assert result["ip"] == "1.2.3.4"

    async def test_get_nonexistent_session(self, rc: RedisSecClient):
        assert await rc.get_session(user_id=99, device_id="devX", session_id="sidX") is None

    async def test_delete_session(self, rc: RedisSecClient):
        await rc.store_session(
            user_id=1, device_id="dev_del", session_id="sess_del",
            data={"info": "test"}, ttl_seconds=300,
        )
        assert await rc.delete_session(user_id=1, device_id="dev_del", session_id="sess_del") is True
        assert await rc.get_session(user_id=1, device_id="dev_del", session_id="sess_del") is None

    async def test_store_session_adds_to_user_index(self, rc: RedisSecClient):
        await rc.store_session(
            user_id=20, device_id="dev20", session_id="sess_idx1",
            data={"info": "indexed"}, ttl_seconds=300,
        )
        idx_key = RedisKeys.user_sessions_index(20)
        members = await rc.client.smembers(idx_key)
        assert "dev20:sess_idx1" in members

    async def test_delete_session_removes_from_user_index(self, rc: RedisSecClient):
        await rc.store_session(
            user_id=21, device_id="dev21", session_id="sess_del21",
            data={"info": "will_delete"}, ttl_seconds=300,
        )
        await rc.delete_session(user_id=21, device_id="dev21", session_id="sess_del21")
        idx_key = RedisKeys.user_sessions_index(21)
        members = await rc.client.smembers(idx_key)
        assert "dev21:sess_del21" not in members

    async def test_list_user_session_ids(self, rc: RedisSecClient):
        for i in range(3):
            await rc.store_session(
                user_id=30, device_id=f"dev30_{i}", session_id=f"sid30_{i}",
                data={"n": i}, ttl_seconds=300,
            )
        ids = await rc.list_user_session_ids(user_id=30)
        assert len(ids) == 3

    async def test_list_user_session_ids_empty(self, rc: RedisSecClient):
        assert await rc.list_user_session_ids(user_id=9990) == []

    async def test_revoke_all_user_sessions(self, rc: RedisSecClient):
        for i in range(4):
            await rc.store_session(
                user_id=40, device_id=f"dev40_{i}", session_id=f"sid40_{i}",
                data={"info": "x"}, ttl_seconds=300,
            )
            await rc.store_refresh_jti(
                jti=f"jti40_{i}", user_id=40, tenant_id=1, family_id=f"fam_{i}",
                device_id=f"dev40_{i}", session_id=f"sid40_{i}", ttl_seconds=300,
            )
        count = await rc.revoke_all_user_sessions(user_id=40)
        assert count == 4
        assert await rc.list_user_session_ids(user_id=40) == []

    async def test_update_session_activity(self, rc: RedisSecClient):
        await rc.store_session(
            user_id=50, device_id="dev50", session_id="act_s",
            data={"last_activity": "old"}, ttl_seconds=300,
        )
        assert await rc.update_session_activity(
            user_id=50, device_id="dev50", session_id="act_s", ttl_seconds=300,
        ) is True
        updated = await rc.get_session(user_id=50, device_id="dev50", session_id="act_s")
        assert updated["last_activity"] != "old"

    async def test_update_session_activity_nonexistent(self, rc: RedisSecClient):
        assert await rc.update_session_activity(
            user_id=99, device_id="ghost", session_id="no_sess", ttl_seconds=300,
        ) is False

    async def test_session_ttl_expires(self, rc: RedisSecClient):
        await rc.store_session(
            user_id=60, device_id="dev60", session_id="ttl_sess",
            data={"info": "x"}, ttl_seconds=1,
        )
        assert await rc.get_session(user_id=60, device_id="dev60", session_id="ttl_sess") is not None
        time.sleep(1.5)
        assert await rc.get_session(user_id=60, device_id="dev60", session_id="ttl_sess") is None


# ── Password Reset Rate Limiting ────────────────────────────────────────
# Note: tokens migrés vers PostgreSQL (NC-05 — spec §04-AUTH-FLOWS §4.4)

class TestPasswordResetRateLimiting:
    async def test_increment_rate_counter(self, rc: RedisSecClient):
        count1 = await rc.increment_password_reset_rate("rate@test.com", ttl_seconds=60)
        assert count1 == 1
        count2 = await rc.increment_password_reset_rate("rate@test.com", ttl_seconds=60)
        assert count2 == 2

    async def test_get_rate_counter(self, rc: RedisSecClient):
        await rc.increment_password_reset_rate("cnt@test.com", ttl_seconds=60)
        await rc.increment_password_reset_rate("cnt@test.com", ttl_seconds=60)
        await rc.increment_password_reset_rate("cnt@test.com", ttl_seconds=60)
        assert await rc.get_password_reset_rate("cnt@test.com") == 3

    async def test_get_rate_counter_zero(self, rc: RedisSecClient):
        assert await rc.get_password_reset_rate("noone@test.com") == 0

    async def test_rate_counter_case_insensitive(self, rc: RedisSecClient):
        await rc.increment_password_reset_rate("MiXeD@Case.COM", ttl_seconds=60)
        assert await rc.get_password_reset_rate("mixed@case.com") == 1

    async def test_rate_counter_ttl_expires(self, rc: RedisSecClient):
        await rc.increment_password_reset_rate("expire@rate.com", ttl_seconds=1)
        assert await rc.get_password_reset_rate("expire@rate.com") == 1
        time.sleep(1.5)
        assert await rc.get_password_reset_rate("expire@rate.com") == 0
