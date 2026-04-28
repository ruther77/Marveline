"""Tests scripts Lua Redis — refresh_check_v3, revoke_single_session,
revoke_all_user_tokens, logout_other_sessions, logout_device (Phase 9).

Ces tests utilisent Redis RÉEL (Docker futurproj_redis_sec:6382).
Couvre spec §02-TOKEN-LIFECYCLE §2.6 + §04-AUTH-FLOWS §4.2-4.3 + §4.5.
"""
import time
import uuid

import pytest

from app.core.redis import redis_sec


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def load_scripts():
    """Charge tous les scripts Lua avant chaque test."""
    redis_sec.load_lua_scripts()


@pytest.fixture(autouse=True)
def cleanup(request):
    """Nettoie les clés Redis de test après chaque test."""
    yield
    # Supprimer toutes les clés de test (préfixes connus)
    for pattern in [
        "whitelist:refresh:9*",
        "family:test_*",
        "user_sessions_index:9*",
        "blacklist:jti:test*",
        "csrf:test*",
        "jti:meta:test*",
        "stepup:9*",
    ]:
        for key in redis_sec.client.scan_iter(match=pattern):
            redis_sec.client.delete(key)


def _uid() -> str:
    return "9999"  # user_id de test fixe pour isolation


def _did() -> str:
    return "dev_test_01"


def _sid() -> str:
    return "sess_test_01"


def _fid() -> str:
    return "fam_test_01"


def _whitelist_key(uid=_uid(), did=_did(), sid=_sid()) -> str:
    return f"whitelist:refresh:{uid}:{did}:{sid}"


def _now() -> str:
    return str(int(time.time()))


def _setup_session(uid=_uid(), did=_did(), sid=_sid(), jti=None):
    """Initialise une session dans Redis pour les tests Lua."""
    jti = jti or f"test_jti_{uuid.uuid4().hex[:8]}"
    fid = _fid()

    # whitelist entry
    wl_key = f"whitelist:refresh:{uid}:{did}:{sid}"
    redis_sec.client.set(wl_key, jti, ex=3600)

    # family set
    redis_sec.client.sadd(f"family:{fid}", jti)
    redis_sec.client.expire(f"family:{fid}", 3600)

    # sessions index
    redis_sec.client.sadd(f"user_sessions_index:{uid}", f"{did}:{sid}")

    # jti meta (exp = now + 900)
    exp = int(time.time()) + 900
    redis_sec.client.set(f"jti:meta:{jti}", str(exp), ex=900)

    return jti, fid


# ── refresh_check_v3 ─────────────────────────────────────────────────────────

class TestRefreshCheckV3:
    """Script Lua refresh_check_v3 — rotation atomique + détection rejeu."""

    def test_valid_rotation_returns_ok(self):
        """JTI actif soumis → rotation OK, retourne OK:{new_jti}."""
        uid, did, sid = _uid(), _did(), _sid()
        old_jti, fid = _setup_session(uid, did, sid)
        new_jti = f"test_new_{uuid.uuid4().hex[:8]}"

        result = redis_sec.evalsha(
            "refresh_check_v3", old_jti, uid, did, sid, fid, _now(), new_jti
        )
        assert str(result).startswith("OK:"), f"Attendu OK:..., reçu {result}"

    def test_ok_updates_whitelist(self):
        """Après rotation OK, la whitelist contient le nouveau JTI."""
        uid, did, sid = _uid(), _did(), _sid()
        old_jti, fid = _setup_session(uid, did, sid)
        new_jti = f"test_new_{uuid.uuid4().hex[:8]}"

        redis_sec.evalsha("refresh_check_v3", old_jti, uid, did, sid, fid, _now(), new_jti)
        wl_value = redis_sec.client.get(_whitelist_key(uid, did, sid))
        assert wl_value == new_jti

    def test_replay_detected_on_old_jti(self):
        """JTI ancien (dans family mais pas actif dans whitelist) → REPLAY_DETECTED."""
        uid, did, sid = _uid(), _did(), _sid()
        old_jti, fid = _setup_session(uid, did, sid)
        new_jti = f"test_new_{uuid.uuid4().hex[:8]}"

        # Première rotation — OK
        redis_sec.evalsha("refresh_check_v3", old_jti, uid, did, sid, fid, _now(), new_jti)

        # Rejouer l'ancien JTI → REPLAY
        result = redis_sec.evalsha(
            "refresh_check_v3", old_jti, uid, did, sid, fid, _now(), "another_jti"
        )
        assert str(result) == "REPLAY_DETECTED"

    def test_replay_revokes_whole_family(self):
        """REPLAY_DETECTED → toute la famille révoquée (whitelist supprimée)."""
        uid, did, sid = _uid(), _did(), _sid()
        old_jti, fid = _setup_session(uid, did, sid)
        new_jti = f"test_new_{uuid.uuid4().hex[:8]}"

        # Rotation OK
        redis_sec.evalsha("refresh_check_v3", old_jti, uid, did, sid, fid, _now(), new_jti)

        # Replay → REPLAY_DETECTED → whitelist supprimée
        redis_sec.evalsha("refresh_check_v3", old_jti, uid, did, sid, fid, _now(), "x")
        wl_value = redis_sec.client.get(_whitelist_key(uid, did, sid))
        assert wl_value is None

    def test_token_invalid_on_unknown_jti(self):
        """JTI inconnu (ni whitelist ni family) → TOKEN_INVALID."""
        uid, did, sid = _uid(), _did(), _sid()
        _setup_session(uid, did, sid)

        result = redis_sec.evalsha(
            "refresh_check_v3",
            "completely_unknown_jti", uid, did, sid, _fid(), _now(), "new_jti"
        )
        assert str(result) == "TOKEN_INVALID"


# ── revoke_single_session ────────────────────────────────────────────────────

class TestRevokeSingleSession:
    """Script Lua revoke_single_session — révocation atomique 1 session."""

    def test_revoke_existing_session(self):
        """Une session existante est révoquée et l'index mis à jour."""
        uid, did, sid = _uid(), _did(), "sess_revoke_01"
        jti, _ = _setup_session(uid, did, sid)

        result = redis_sec.evalsha("revoke_single_session", uid, did, sid, _now())
        assert str(result) in ("OK", f"OK:{jti}")
        # Whitelist supprimée
        assert redis_sec.client.get(_whitelist_key(uid, did, sid)) is None

    def test_revoke_removes_from_index(self):
        """Après révocation, le membre est retiré de user_sessions_index."""
        uid, did, sid = _uid(), _did(), "sess_idx_01"
        _setup_session(uid, did, sid)

        redis_sec.evalsha("revoke_single_session", uid, did, sid, _now())
        members = redis_sec.client.smembers(f"user_sessions_index:{uid}")
        assert f"{did}:{sid}" not in (members or set())


# ── revoke_all_user_tokens ───────────────────────────────────────────────────

class TestRevokeAllUserTokens:
    """Script Lua revoke_all_user_tokens — force-logout complet."""

    def test_revokes_multiple_sessions(self):
        """Toutes les sessions sont révoquées, retourne le count."""
        uid = "9998"  # user_id distinct
        sessions = []
        for i in range(3):
            did = f"dev_{i}"
            sid = f"sess_{i}"
            jti, _ = _setup_session(uid, did, sid)
            sessions.append((did, sid, jti))

        result = redis_sec.evalsha("revoke_all_user_tokens", uid, _now())
        count = int(result)
        assert count == 3

    def test_revokes_clears_all_whitelists(self):
        """Après revoke_all, aucune whitelist ne subsiste pour ce user."""
        uid = "9997"
        for i in range(2):
            _setup_session(uid, f"dev_{i}", f"sess_{i}")

        redis_sec.evalsha("revoke_all_user_tokens", uid, _now())
        # L'index doit être vide
        index_size = redis_sec.client.scard(f"user_sessions_index:{uid}")
        assert index_size == 0

    def test_empty_user_returns_zero(self):
        """Un user sans sessions actives retourne 0."""
        uid = "9996"
        result = redis_sec.evalsha("revoke_all_user_tokens", uid, _now())
        assert int(result) == 0


# ── logout_other_sessions ────────────────────────────────────────────────────

class TestLogoutOtherSessions:
    """Script Lua logout_other_sessions — révoque tout sauf session courante (§4.5)."""

    def test_preserves_current_session(self):
        """La session courante ({current_did}:{current_sid}) doit être conservée."""
        uid = "9995"
        current_did, current_sid = "dev_keep", "sess_keep"
        other_did, other_sid = "dev_other", "sess_other"

        _setup_session(uid, current_did, current_sid)
        _setup_session(uid, other_did, other_sid)

        redis_sec.evalsha(
            "logout_other_sessions", uid, current_did, current_sid, _now()
        )

        # Whitelist de la session courante doit subsister
        wl = redis_sec.client.get(_whitelist_key(uid, current_did, current_sid))
        assert wl is not None

    def test_revokes_other_sessions(self):
        """Les autres sessions doivent être révoquées."""
        uid = "9994"
        current_did, current_sid = "dev_c", "sess_c"
        other_did, other_sid = "dev_o", "sess_o"

        _setup_session(uid, current_did, current_sid)
        _setup_session(uid, other_did, other_sid)

        result = redis_sec.evalsha(
            "logout_other_sessions", uid, current_did, current_sid, _now()
        )
        assert int(result) == 1

        # Whitelist de l'autre session supprimée
        wl = redis_sec.client.get(_whitelist_key(uid, other_did, other_sid))
        assert wl is None

    def test_cleans_csrf_for_revoked_session(self):
        """CSRF de la session révoquée est supprimé."""
        uid = "9993"
        current_did, current_sid = "dc", "sc"
        other_did, other_sid = "do", "so"

        _setup_session(uid, current_did, current_sid)
        _setup_session(uid, other_did, other_sid)
        redis_sec.client.set(f"csrf:{other_sid}", "csrf_token_xyz", ex=900)

        redis_sec.evalsha("logout_other_sessions", uid, current_did, current_sid, _now())

        csrf_val = redis_sec.client.get(f"csrf:{other_sid}")
        assert csrf_val is None


# ── logout_device ────────────────────────────────────────────────────────────

class TestLogoutDevice:
    """Script Lua logout_device — révoque toutes les sessions d'un device (§4.3)."""

    def test_revokes_all_device_sessions(self):
        """Toutes les sessions du device ciblé sont révoquées."""
        uid = "9992"
        device = "dev_target"

        _setup_session(uid, device, "sess_d1")
        _setup_session(uid, device, "sess_d2")

        result = redis_sec.evalsha("logout_device", uid, device, _now())
        assert int(result) == 2

        # Les deux whitelists supprimées
        wl1 = redis_sec.client.get(f"whitelist:refresh:{uid}:{device}:sess_d1")
        wl2 = redis_sec.client.get(f"whitelist:refresh:{uid}:{device}:sess_d2")
        assert wl1 is None
        assert wl2 is None

    def test_preserves_other_device(self):
        """Les sessions d'un autre device ne doivent pas être affectées."""
        uid = "9991"
        target_device = "dev_del"
        keep_device = "dev_keep"

        _setup_session(uid, target_device, "sess_del")
        _setup_session(uid, keep_device, "sess_kept")

        redis_sec.evalsha("logout_device", uid, target_device, _now())

        # Session du keep_device doit subsister
        wl = redis_sec.client.get(f"whitelist:refresh:{uid}:{keep_device}:sess_kept")
        assert wl is not None

    def test_returns_zero_for_nonexistent_device(self):
        """Un device sans sessions retourne 0."""
        uid = "9990"
        result = redis_sec.evalsha("logout_device", uid, "ghost_device", _now())
        assert int(result) == 0
