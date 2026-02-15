"""Tests unitaires pour app/core/redis.py — RedisClient.

Couvre 7 domaines : CSRF, refresh whitelist, access blacklist,
token families, brute force, sessions, health.
Utilise Redis réel (Docker).
"""
import json
import time
import pytest

from app.core.redis import RedisClient, get_redis_client, redis_client
from app.constants import RedisKeys, SessionConfig


# ── Fixture ──────────────────────────────────────────────────────────────

@pytest.fixture
def rc() -> RedisClient:
    """Instance fraîche de RedisClient (singleton global)."""
    return redis_client


# ── Singleton ────────────────────────────────────────────────────────────

class TestSingleton:
    def test_get_redis_client_returns_same_instance(self):
        a = get_redis_client()
        b = get_redis_client()
        assert a is b

    def test_global_redis_client_is_singleton(self):
        assert redis_client is get_redis_client()


# ── Ping / Health ────────────────────────────────────────────────────────

class TestPingHealth:
    def test_ping_returns_true(self, rc: RedisClient):
        assert rc.ping() is True

    def test_health_check_healthy(self, rc: RedisClient):
        result = rc.health_check()
        assert result["status"] == "healthy"
        assert result["connected"] is True
        assert "redis_version" in result
        assert "uptime_seconds" in result

    def test_health_check_returns_dict(self, rc: RedisClient):
        result = rc.health_check()
        assert isinstance(result, dict)


# ── CSRF Tokens ──────────────────────────────────────────────────────────

class TestCSRF:
    def test_store_csrf_token(self, rc: RedisClient):
        assert rc.store_csrf_token(user_id=1, token="tok_abc", ttl_seconds=60) is True

    def test_validate_csrf_token_valid(self, rc: RedisClient):
        rc.store_csrf_token(user_id=1, token="tok_val", ttl_seconds=60)
        assert rc.validate_csrf_token(user_id=1, token="tok_val") is True

    def test_validate_csrf_token_missing(self, rc: RedisClient):
        assert rc.validate_csrf_token(user_id=1, token="nonexistent") is False

    def test_validate_csrf_wrong_user(self, rc: RedisClient):
        rc.store_csrf_token(user_id=1, token="tok_user1", ttl_seconds=60)
        assert rc.validate_csrf_token(user_id=2, token="tok_user1") is False

    def test_revoke_csrf_token(self, rc: RedisClient):
        rc.store_csrf_token(user_id=1, token="tok_rev", ttl_seconds=60)
        assert rc.revoke_csrf_token(user_id=1, token="tok_rev") is True
        assert rc.validate_csrf_token(user_id=1, token="tok_rev") is False

    def test_revoke_csrf_token_nonexistent(self, rc: RedisClient):
        assert rc.revoke_csrf_token(user_id=1, token="nope") is False

    def test_revoke_all_csrf_tokens(self, rc: RedisClient):
        rc.store_csrf_token(user_id=10, token="t1", ttl_seconds=60)
        rc.store_csrf_token(user_id=10, token="t2", ttl_seconds=60)
        rc.store_csrf_token(user_id=10, token="t3", ttl_seconds=60)
        count = rc.revoke_all_csrf_tokens(user_id=10)
        assert count == 3
        assert rc.validate_csrf_token(user_id=10, token="t1") is False

    def test_revoke_all_csrf_tokens_no_tokens(self, rc: RedisClient):
        assert rc.revoke_all_csrf_tokens(user_id=999) == 0

    def test_csrf_ttl_respected(self, rc: RedisClient):
        rc.store_csrf_token(user_id=1, token="tok_ttl", ttl_seconds=1)
        assert rc.validate_csrf_token(user_id=1, token="tok_ttl") is True
        time.sleep(1.5)
        assert rc.validate_csrf_token(user_id=1, token="tok_ttl") is False


# ── Refresh Token Whitelist ──────────────────────────────────────────────

class TestRefreshWhitelist:
    def test_store_and_get_refresh_jti(self, rc: RedisClient):
        assert rc.store_refresh_jti(
            jti="jti_1", user_id=1, tenant_id=1, family_id="fam_1", ttl_seconds=300
        ) is True
        data = rc.get_refresh_jti("jti_1")
        assert data is not None
        assert data["user_id"] == 1
        assert data["tenant_id"] == 1
        assert data["family_id"] == "fam_1"

    def test_get_refresh_jti_nonexistent(self, rc: RedisClient):
        assert rc.get_refresh_jti("jti_nope") is None

    def test_revoke_refresh_jti(self, rc: RedisClient):
        rc.store_refresh_jti(jti="jti_rev", user_id=1, tenant_id=1, family_id="f1", ttl_seconds=300)
        assert rc.revoke_refresh_jti("jti_rev") is True
        assert rc.get_refresh_jti("jti_rev") is None

    def test_revoke_refresh_jti_nonexistent(self, rc: RedisClient):
        assert rc.revoke_refresh_jti("jti_ghost") is False

    def test_revoke_all_refresh_tokens_for_user(self, rc: RedisClient):
        rc.store_refresh_jti(jti="u1_a", user_id=5, tenant_id=1, family_id="f1", ttl_seconds=300)
        rc.store_refresh_jti(jti="u1_b", user_id=5, tenant_id=1, family_id="f2", ttl_seconds=300)
        rc.store_refresh_jti(jti="u2_a", user_id=6, tenant_id=1, family_id="f3", ttl_seconds=300)
        count = rc.revoke_all_refresh_tokens(user_id=5)
        assert count == 2
        assert rc.get_refresh_jti("u1_a") is None
        assert rc.get_refresh_jti("u1_b") is None
        # user 6 untouched
        assert rc.get_refresh_jti("u2_a") is not None


# ── Access Token Blacklist ───────────────────────────────────────────────

class TestAccessBlacklist:
    def test_blacklist_and_check(self, rc: RedisClient):
        assert rc.blacklist_access_jti("acc_1", ttl_seconds=60) is True
        assert rc.is_access_blacklisted("acc_1") is True

    def test_not_blacklisted(self, rc: RedisClient):
        assert rc.is_access_blacklisted("acc_clean") is False

    def test_blacklist_ttl_expires(self, rc: RedisClient):
        rc.blacklist_access_jti("acc_exp", ttl_seconds=1)
        assert rc.is_access_blacklisted("acc_exp") is True
        time.sleep(1.5)
        assert rc.is_access_blacklisted("acc_exp") is False


# ── Token Family ─────────────────────────────────────────────────────────

class TestTokenFamily:
    def test_store_and_get_family(self, rc: RedisClient):
        rc.store_token_family(family_id="fam_a", user_id=1, ttl_seconds=300)
        data = rc.get_token_family("fam_a")
        assert data is not None
        assert data["user_id"] == 1
        assert data["active"] is True

    def test_get_nonexistent_family(self, rc: RedisClient):
        assert rc.get_token_family("fam_nope") is None

    def test_revoke_family(self, rc: RedisClient):
        rc.store_token_family(family_id="fam_rev", user_id=1, ttl_seconds=300)
        assert rc.revoke_token_family("fam_rev") is True
        data = rc.get_token_family("fam_rev")
        assert data is not None
        assert data["active"] is False

    def test_revoke_nonexistent_family(self, rc: RedisClient):
        assert rc.revoke_token_family("fam_ghost") is False


# ── Brute Force Counters ────────────────────────────────────────────────

class TestBruteForce:
    def test_increment_returns_count(self, rc: RedisClient):
        count = rc.increment_brute_force("bf_email:", "a@b.com", ttl_seconds=60)
        assert count == 1
        count2 = rc.increment_brute_force("bf_email:", "a@b.com", ttl_seconds=60)
        assert count2 == 2

    def test_get_brute_force_count(self, rc: RedisClient):
        rc.increment_brute_force("bf_email:", "c@d.com", ttl_seconds=60)
        rc.increment_brute_force("bf_email:", "c@d.com", ttl_seconds=60)
        assert rc.get_brute_force_count("bf_email:", "c@d.com") == 2

    def test_get_brute_force_count_zero(self, rc: RedisClient):
        assert rc.get_brute_force_count("bf_email:", "unknown@x.com") == 0

    def test_reset_brute_force(self, rc: RedisClient):
        rc.increment_brute_force("bf_email:", "e@f.com", ttl_seconds=60)
        assert rc.reset_brute_force("bf_email:", "e@f.com") is True
        assert rc.get_brute_force_count("bf_email:", "e@f.com") == 0

    def test_set_and_check_lock(self, rc: RedisClient):
        rc.set_brute_force_lock("locked@x.com", ttl_seconds=60)
        assert rc.is_brute_force_locked("locked@x.com") is True

    def test_not_locked(self, rc: RedisClient):
        assert rc.is_brute_force_locked("free@x.com") is False

    def test_lock_ttl(self, rc: RedisClient):
        rc.set_brute_force_lock("ttl@x.com", ttl_seconds=120)
        ttl = rc.get_brute_force_lock_ttl("ttl@x.com")
        assert 0 < ttl <= 120

    def test_lock_ttl_no_lock(self, rc: RedisClient):
        assert rc.get_brute_force_lock_ttl("nolock@x.com") == 0

    def test_alert_sent_idempotent(self, rc: RedisClient):
        # First call: True (marked)
        assert rc.set_brute_force_alert_sent("alert@x.com", ttl_seconds=60) is True
        # Second call: False (already marked, NX prevents overwrite)
        result = rc.set_brute_force_alert_sent("alert@x.com", ttl_seconds=60)
        assert result is None or result is False

    def test_per_ip_counter_separate(self, rc: RedisClient):
        rc.increment_brute_force("bf_ip:", "1.2.3.4", ttl_seconds=60)
        rc.increment_brute_force("bf_email:", "user@x.com", ttl_seconds=60)
        assert rc.get_brute_force_count("bf_ip:", "1.2.3.4") == 1
        assert rc.get_brute_force_count("bf_email:", "user@x.com") == 1


# ── Sessions ─────────────────────────────────────────────────────────────

class TestSessions:
    def test_store_and_get_session(self, rc: RedisClient):
        data = {"user_id": 1, "ip": "1.2.3.4", "ua": "Chrome"}
        assert rc.store_session("sess_1", data, ttl_seconds=300) is True
        result = rc.get_session("sess_1")
        assert result is not None
        assert result["user_id"] == 1
        assert result["ip"] == "1.2.3.4"

    def test_get_nonexistent_session(self, rc: RedisClient):
        assert rc.get_session("sess_nope") is None

    def test_delete_session(self, rc: RedisClient):
        data = {"user_id": 1, "info": "test"}
        rc.store_session("sess_del", data, ttl_seconds=300)
        assert rc.delete_session("sess_del", user_id=1) is True
        assert rc.get_session("sess_del") is None

    def test_store_session_adds_to_user_index(self, rc: RedisClient):
        data = {"user_id": 20, "info": "indexed"}
        rc.store_session("sess_idx1", data, ttl_seconds=300)
        idx_key = f"{RedisKeys.SESSION_USER_INDEX}20"
        members = rc.client.smembers(idx_key)
        assert "sess_idx1" in members

    def test_delete_session_removes_from_user_index(self, rc: RedisClient):
        data = {"user_id": 21, "info": "will_delete"}
        rc.store_session("sess_idx_del", data, ttl_seconds=300)
        rc.delete_session("sess_idx_del", user_id=21)
        idx_key = f"{RedisKeys.SESSION_USER_INDEX}21"
        members = rc.client.smembers(idx_key)
        assert "sess_idx_del" not in members

    def test_list_user_sessions(self, rc: RedisClient):
        for i in range(3):
            rc.store_session(f"list_s{i}", {"user_id": 30, "n": i}, ttl_seconds=300)
        sessions = rc.list_user_sessions(user_id=30)
        assert len(sessions) == 3

    def test_list_user_sessions_cleans_stale(self, rc: RedisClient):
        # Store a session then delete the data key (simulate expiry)
        rc.store_session("stale_s", {"user_id": 31}, ttl_seconds=300)
        rc.client.delete(f"{RedisKeys.SESSION}stale_s")
        sessions = rc.list_user_sessions(user_id=31)
        assert len(sessions) == 0
        # Stale entry should be removed from index
        members = rc.client.smembers(f"{RedisKeys.SESSION_USER_INDEX}31")
        assert "stale_s" not in members

    def test_list_user_sessions_empty(self, rc: RedisClient):
        assert rc.list_user_sessions(user_id=999) == []

    def test_delete_all_user_sessions(self, rc: RedisClient):
        for i in range(4):
            rc.store_session(f"all_s{i}", {"user_id": 40}, ttl_seconds=300)
        count = rc.delete_all_user_sessions(user_id=40)
        assert count == 4
        assert rc.list_user_sessions(user_id=40) == []

    def test_update_session_activity(self, rc: RedisClient):
        data = {"user_id": 50, "last_activity": "old"}
        rc.store_session("act_s", data, ttl_seconds=300)
        assert rc.update_session_activity("act_s", ttl_seconds=300) is True
        updated = rc.get_session("act_s")
        assert updated["last_activity"] != "old"

    def test_update_session_activity_nonexistent(self, rc: RedisClient):
        assert rc.update_session_activity("no_sess", ttl_seconds=300) is False

    def test_session_ttl_expires(self, rc: RedisClient):
        rc.store_session("ttl_sess", {"user_id": 60}, ttl_seconds=1)
        assert rc.get_session("ttl_sess") is not None
        time.sleep(1.5)
        assert rc.get_session("ttl_sess") is None
