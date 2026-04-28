"""Client Redis dual pour CaroCorp Auth v3 (§3.1-3.7).

Architecture :
    - Redis-SEC (6382, noeviction) : whitelist, blacklist, families, CSRF,
      brute force, MFA sessions, password reset. FAIL-CLOSED.
    - Redis-CACHE (6383, allkeys-lru) : API key cache, feature flags,
      RBAC scope cache, compteurs metier. FAIL-OPEN.

Lua scripts :
    Charges au demarrage via SCRIPT LOAD, executees via EVALSHA.
    0 KEYS — tout en ARGV pour compat Redis Cluster (§3.6).
"""
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings
from app.constants import CredentialStuffingThresholds, Limits, RedisKeys, SessionConfig

logger = logging.getLogger(__name__)

# Repertoire des scripts Lua
LUA_DIR = Path(__file__).resolve().parent.parent / "lua"


class RedisSecClient:
    """Client Redis-SEC async — donnees critiques de securite.

    Comportement si down : FAIL-CLOSED (auth impossible).
    Policy : noeviction — aucune cle ne doit etre evincee.
    Toutes les méthodes sont async (redis.asyncio >= 5.0).
    """

    def __init__(self):
        self._client: Optional[AsyncRedis] = None
        self._lua_shas: dict[str, str] = {}

    @property
    def client(self) -> AsyncRedis:
        if self._client is None:
            self._client = aioredis.from_url(
                settings.REDIS_SEC_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
        return self._client

    async def ping(self) -> bool:
        try:
            return await self.client.ping()
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    # ========== Lua Script Loader (§3.6) ==========

    async def load_lua_scripts(self) -> None:
        """Charge les scripts Lua via SCRIPT LOAD au demarrage."""
        if not LUA_DIR.exists():
            logger.warning("Lua directory not found: %s", LUA_DIR)
            return

        for lua_file in sorted(LUA_DIR.glob("*.lua")):
            script_name = lua_file.stem
            try:
                script_body = lua_file.read_text(encoding="utf-8")
                sha = await self.client.script_load(script_body)
                self._lua_shas[script_name] = sha
                logger.info("Lua script loaded: %s → SHA %s", script_name, sha[:12])
            except Exception:
                logger.exception("Failed to load Lua script: %s", script_name)

    async def evalsha(self, script_name: str, *args: str) -> any:
        """Execute un script Lua via EVALSHA (0 KEYS, tout en ARGV)."""
        sha = self._lua_shas.get(script_name)
        if not sha:
            raise RuntimeError(f"Lua script not loaded: {script_name}")
        return await self.client.evalsha(sha, 0, *args)

    # ========== CSRF Tokens (§04 §4.3) ==========

    async def store_csrf_token(
        self,
        session_id: str,
        token: str,
        ttl_seconds: int = SessionConfig.SESSION_TTL_SECONDS,  # 7j — aligné sur durée session
    ) -> bool:
        """Stocke le token CSRF pour une session. Key : csrf:{session_id} = token.

        TTL aligné sur la durée de session (SESSION_TTL_SECONDS = 7j),
        pas 900s — sinon le CSRF expire bien avant la session (P2-01).
        """
        try:
            key = RedisKeys.csrf_token(session_id)
            return bool(await self.client.setex(key, ttl_seconds, token))
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def validate_csrf_token(self, session_id: str, token: str) -> bool:
        """Valide le token CSRF d'une session (timing-safe compare_digest)."""
        try:
            key = RedisKeys.csrf_token(session_id)
            stored = await self.client.get(key)
            if not stored:
                return False
            stored_str = stored.decode() if isinstance(stored, bytes) else stored
            return hmac.compare_digest(stored_str, token)
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def revoke_csrf_token(self, session_id: str) -> bool:
        """Révoque le token CSRF d'une session."""
        try:
            return await self.client.delete(RedisKeys.csrf_token(session_id)) > 0
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def revoke_all_csrf_tokens(self, user_id: int) -> int:
        """Révoque les CSRF de toutes les sessions d'un user via user_sessions_index."""
        try:
            idx_key = RedisKeys.user_sessions_index(user_id)
            members = await self.client.smembers(idx_key)
            count = 0
            for member in members:
                member_str = member.decode() if isinstance(member, bytes) else member
                sid = member_str.split(":", 1)[-1]  # format "did:sid" → sid
                count += await self.client.delete(RedisKeys.csrf_token(sid))
            return count
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    # ========== Refresh Token Whitelist (§3.2 — v3 key pattern) ==========

    async def store_refresh_jti(
        self,
        jti: str,
        user_id: int,
        tenant_id: int,
        family_id: str,
        device_id: str,
        session_id: str,
        ttl_seconds: int,
    ) -> bool:
        """Stocke un JTI refresh dans la whitelist v3.

        Key : whitelist:refresh:{uid}:{did}:{sid} = JTI (STRING)
        TTL : EXPIREAT absolu (calcule depuis ttl_seconds).
        """
        try:
            key = RedisKeys.refresh_whitelist(uid=user_id, did=device_id, sid=session_id)
            expire_at = int(datetime.now(timezone.utc).timestamp()) + ttl_seconds
            pipe = self.client.pipeline()
            pipe.set(key, jti)
            pipe.expireat(key, expire_at)
            await pipe.execute()
            return True
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def get_refresh_jti(self, user_id: int, device_id: str, session_id: str) -> Optional[str]:
        """Recupere le JTI refresh actif pour une session."""
        try:
            key = RedisKeys.refresh_whitelist(uid=user_id, did=device_id, sid=session_id)
            return await self.client.get(key)
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return None

    async def revoke_refresh_jti(self, user_id: int, device_id: str, session_id: str) -> bool:
        """Supprime le JTI refresh d'une session (whitelist)."""
        try:
            key = RedisKeys.refresh_whitelist(uid=user_id, did=device_id, sid=session_id)
            return await self.client.delete(key) > 0
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    # ========== Access Token Blacklist (§3.2) ==========

    async def blacklist_access_jti(self, jti: str, ttl_seconds: int) -> bool:
        """blacklist:jti:{jti} = "1", TTL residuel."""
        try:
            key = RedisKeys.access_blacklist(jti)
            return await self.client.setex(key, ttl_seconds, "1")
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def is_access_blacklisted(self, jti: str) -> bool:
        try:
            key = RedisKeys.access_blacklist(jti)
            return await self.client.exists(key) == 1
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    # ========== JTI Meta (§3.2 — pour TTL residuel blacklist) ==========

    async def store_jti_meta(self, jti_access: str, exp_timestamp: int, ttl_seconds: int | None = None) -> bool:
        """jti:meta:{jti_access} = exp_timestamp, TTL = access_lifetime + clock_skew + buffer."""
        if ttl_seconds is None:
            ttl_seconds = settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS + settings.JWT_CLOCK_SKEW_SECONDS + 60
        try:
            key = RedisKeys.jti_meta(jti_access)
            return await self.client.setex(key, ttl_seconds, str(exp_timestamp))
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def get_jti_meta(self, jti_access: str) -> Optional[int]:
        """Recupere le exp_timestamp d'un access token."""
        try:
            key = RedisKeys.jti_meta(jti_access)
            data = await self.client.get(key)
            return int(data) if data else None
        except (aioredis.ConnectionError, aioredis.TimeoutError, ValueError):
            return None

    # ========== Token Family (§3.2 — SET de JTIs) ==========

    async def store_token_family(self, family_id: str, jti: str, ttl_seconds: int) -> bool:
        """family:{fid} = SET de JTIs, EXPIREAT absolu."""
        try:
            key = RedisKeys.token_family(family_id)
            expire_at = int(datetime.now(timezone.utc).timestamp()) + ttl_seconds
            pipe = self.client.pipeline()
            pipe.sadd(key, jti)
            pipe.expireat(key, expire_at)
            await pipe.execute()
            return True
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def add_jti_to_family(self, family_id: str, jti: str) -> bool:
        """Ajoute un JTI au SET de la famille (rotation)."""
        try:
            key = RedisKeys.token_family(family_id)
            await self.client.sadd(key, jti)
            return True
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def is_jti_in_family(self, family_id: str, jti: str) -> bool:
        """Verifie si un JTI est dans la famille."""
        try:
            key = RedisKeys.token_family(family_id)
            return await self.client.sismember(key, jti)
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def family_exists(self, family_id: str) -> bool:
        """Verifie si la famille existe (non expirée)."""
        try:
            key = RedisKeys.token_family(family_id)
            return await self.client.exists(key) == 1
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def revoke_token_family(self, family_id: str) -> bool:
        """Supprime la famille entiere (replay detection)."""
        try:
            key = RedisKeys.token_family(family_id)
            return await self.client.delete(key) > 0
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    # ========== User Sessions Index (§3.2) ==========

    async def add_session_to_index(self, user_id: int, device_id: str, session_id: str, ttl_seconds: int) -> bool:
        """Ajoute did:sid au SET user_sessions_index:{uid}."""
        try:
            key = RedisKeys.user_sessions_index(user_id)
            member = f"{device_id}:{session_id}"
            pipe = self.client.pipeline()
            pipe.sadd(key, member)
            pipe.expire(key, ttl_seconds)
            await pipe.execute()
            return True
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def remove_session_from_index(self, user_id: int, device_id: str, session_id: str) -> bool:
        """Retire did:sid du SET user_sessions_index:{uid}."""
        try:
            key = RedisKeys.user_sessions_index(user_id)
            member = f"{device_id}:{session_id}"
            await self.client.srem(key, member)
            return True
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def list_user_session_ids(self, user_id: int) -> list[str]:
        """Retourne la liste des "did:sid" actifs pour un user."""
        try:
            key = RedisKeys.user_sessions_index(user_id)
            return list(await self.client.smembers(key))
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return []

    async def revoke_all_user_sessions(self, user_id: int) -> int:
        """Revoque toutes les sessions d'un user via Lua atomique (spec §2.7, §3.6 NC-09)."""
        try:
            now = int(time.time())
            result = await self.evalsha("revoke_all_user_tokens", str(user_id), str(now))
            return int(result) if result is not None else 0
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    async def revoke_single_session(self, user_id: int, device_id: str, session_id: str) -> None:
        """Révoque une session unique via Lua atomique (DEL session+csrf, SREM index)."""
        now = str(int(time.time()))
        await self.evalsha("revoke_single_session", str(user_id), device_id, session_id, now)

    async def revoke_sessions_except_device(self, user_id: int, current_did: str) -> int:
        """Révoque toutes les sessions sauf celle du device courant (spec §4.5 NC-06)."""
        try:
            idx_key = RedisKeys.user_sessions_index(user_id)
            members = await self.client.smembers(idx_key)
            if not members:
                return 0
            count = 0
            for member in members:
                member_str = member.decode() if isinstance(member, bytes) else member
                if current_did and member_str.startswith(f"{current_did}:"):
                    continue
                parts = member_str.split(":", 1)
                if len(parts) == 2:
                    did, sid = parts
                    await self.revoke_single_session(user_id, did, sid)
                    count += 1
            return count
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    async def logout_device(self, user_id: int, device_id: str) -> int:
        """Révoque toutes les sessions d'un device (§4.3 S-09.1) via Lua atomique."""
        try:
            now = str(int(time.time()))
            result = await self.evalsha("logout_device", str(user_id), device_id, now)
            return int(result) if result is not None else 0
        except RuntimeError:
            return await self._logout_device_fallback(user_id, device_id)
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    async def _logout_device_fallback(self, user_id: int, device_id: str) -> int:
        """Fallback non-atomique pour logout_device si Lua non chargé (dev uniquement)."""
        try:
            idx_key = RedisKeys.user_sessions_index(user_id)
            members = await self.client.smembers(idx_key)
            prefix = f"{device_id}:"
            count = 0
            for member in members:
                member_str = member.decode() if isinstance(member, bytes) else member
                if member_str.startswith(prefix):
                    sid = member_str[len(prefix):]
                    await self.revoke_single_session(user_id, device_id, sid)
                    count += 1
            return count
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    async def logout_other_sessions(self, user_id: int, current_did: str, current_sid: str) -> int:
        """Révoque toutes les sessions sauf {current_did}:{current_sid} (§4.5 S-09.3)."""
        try:
            now = str(int(time.time()))
            result = await self.evalsha(
                "logout_other_sessions",
                str(user_id),
                current_did,
                current_sid,
                now,
            )
            return int(result) if result is not None else 0
        except RuntimeError:
            return await self.revoke_sessions_except_device(user_id, current_did)
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    # ========== Devices révoqués (§7.1 S-08.1) ==========

    async def mark_device_revoked(self, device_id: str, ttl_seconds: int = 86400) -> None:
        """Marque un device comme révoqué dans Redis-SEC (§7.1 S-08.1)."""
        try:
            await self.client.setex(RedisKeys.revoked_device(device_id), ttl_seconds, "1")
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            logger.warning("Redis-SEC down: cannot mark device %s as revoked", device_id[:8])

    async def is_device_revoked(self, device_id: str) -> bool:
        """Vérifie si un device est marqué comme révoqué. FAIL-CLOSED.

        FAIL-CLOSED : si Redis-SEC est indisponible, un device révoqué pour
        compromission ne doit pas pouvoir accéder à l'API (§7.1 S-08.1).
        """
        try:
            return await self.client.exists(RedisKeys.revoked_device(device_id)) == 1
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            logger.critical(
                "Redis-SEC down — FAIL-CLOSED on is_device_revoked(did=%.8s)", device_id
            )
            return True  # FAIL-CLOSED (P0-02)

    async def incr_revoked_device_attempt(self, device_id: str, ttl_seconds: int = 86400) -> int:
        """Incrémente le compteur de tentatives d'un device révoqué (§7.1)."""
        try:
            key = RedisKeys.revoked_device_attempt(device_id)
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl_seconds)
            results = await pipe.execute()
            return int(results[0])
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    # ========== Sessions Redis (§3.2 — HASH) ==========

    async def store_session(
        self,
        user_id: int,
        device_id: str,
        session_id: str,
        data: dict,
        ttl_seconds: int = SessionConfig.SESSION_TTL_SECONDS,
    ) -> bool:
        """Stocke session:{uid}:{did}:{sid} comme HASH + index."""
        try:
            key = RedisKeys.session(uid=user_id, did=device_id, sid=session_id)
            pipe = self.client.pipeline()
            pipe.hset(key, mapping=data)
            pipe.expire(key, ttl_seconds)
            await pipe.execute()

            await self.add_session_to_index(user_id, device_id, session_id, ttl_seconds)
            return True
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def get_session(self, user_id: int, device_id: str, session_id: str) -> Optional[dict]:
        """Recupere une session depuis Redis (HGETALL)."""
        try:
            key = RedisKeys.session(uid=user_id, did=device_id, sid=session_id)
            data = await self.client.hgetall(key)
            return data if data else None
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return None

    async def delete_session(self, user_id: int, device_id: str, session_id: str) -> bool:
        """Supprime une session + retire de l'index."""
        try:
            key = RedisKeys.session(uid=user_id, did=device_id, sid=session_id)
            await self.client.delete(key)
            await self.remove_session_from_index(user_id, device_id, session_id)
            return True
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def update_session_activity(
        self,
        user_id: int,
        device_id: str,
        session_id: str,
        ttl_seconds: int = SessionConfig.SESSION_TTL_SECONDS,
    ) -> bool:
        """Met a jour last_activity et refresh le TTL."""
        try:
            key = RedisKeys.session(uid=user_id, did=device_id, sid=session_id)
            if not await self.client.exists(key):
                return False
            now_iso = datetime.now(timezone.utc).isoformat()
            pipe = self.client.pipeline()
            pipe.hset(key, "last_activity", now_iso)
            pipe.expire(key, ttl_seconds)
            await pipe.execute()
            return True
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    # ========== Brute Force Counters (§3.2, §7.1) ==========

    async def increment_brute_force(self, key: str, ttl_seconds: int) -> int:
        """Incremente un compteur brute force avec TTL glissant."""
        try:
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl_seconds)
            results = await pipe.execute()
            return results[0]
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    async def get_brute_force_count(self, key: str) -> int:
        try:
            count = await self.client.get(key)
            return int(count) if count else 0
        except (aioredis.ConnectionError, aioredis.TimeoutError, ValueError):
            return 0

    async def reset_brute_force(self, key: str) -> bool:
        try:
            await self.client.delete(key)
            return True
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def set_brute_force_lock(self, identifier: str, ttl_seconds: int) -> bool:
        try:
            key = f"{RedisKeys.BRUTE_FORCE_LOCK}{identifier}"
            return await self.client.setex(key, ttl_seconds, "1")
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def is_brute_force_locked(self, identifier: str) -> bool:
        try:
            key = f"{RedisKeys.BRUTE_FORCE_LOCK}{identifier}"
            return await self.client.exists(key) == 1
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            logger.warning("Redis-SEC unavailable in is_brute_force_locked — FAIL-CLOSED for %s", identifier)
            return True  # FAIL-CLOSED : Redis down → bloquer par sécurité (spec §07 §7.1)

    async def get_brute_force_lock_ttl(self, identifier: str) -> int:
        try:
            key = f"{RedisKeys.BRUTE_FORCE_LOCK}{identifier}"
            ttl = await self.client.ttl(key)
            return max(ttl, 0)
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    async def set_brute_force_alert_sent(self, identifier: str, ttl_seconds: int) -> bool:
        try:
            key = f"{RedisKeys.BRUTE_FORCE_ALERT}{identifier}"
            return await self.client.set(key, "1", ex=ttl_seconds, nx=True)
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    # ========== Credential Stuffing Global (§7.2 NIVEAU 3) ==========

    async def increment_credential_stuffing(self, minute_key: str) -> int:
        """Incrémente le compteur global credential stuffing de la minute courante."""
        try:
            pipe = self.client.pipeline()
            pipe.incr(minute_key)
            pipe.expire(minute_key, CredentialStuffingThresholds.MINUTE_WINDOW_SECONDS)
            results = await pipe.execute()
            return results[0]
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    async def is_captcha_required(self) -> bool:
        """Vérifie si le flag captcha:required est actif (FAIL-CLOSED)."""
        try:
            return await self.client.exists(RedisKeys.CAPTCHA_REQUIRED) == 1
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return True  # FAIL-CLOSED

    async def set_captcha_required(self, ttl: int = 1800) -> None:
        """Active le flag captcha:required (TTL 30 min par défaut)."""
        try:
            await self.client.setex(RedisKeys.CAPTCHA_REQUIRED, ttl, "1")
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            logger.warning("Redis indisponible : impossible d'activer captcha:required")

    async def is_login_blocked(self) -> bool:
        """Vérifie si le login global est bloqué (FAIL-CLOSED)."""
        try:
            return await self.client.exists(RedisKeys.LOGIN_BLOCKED) == 1
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return True  # FAIL-CLOSED

    async def set_login_blocked(self, ttl: int = 300) -> None:
        """Bloque tous les logins pendant ttl secondes."""
        try:
            await self.client.setex(RedisKeys.LOGIN_BLOCKED, ttl, "1")
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            logger.warning("Redis indisponible : impossible d'activer login:blocked")

    # ========== Password Reset Rate Limiting ==========

    async def increment_password_reset_rate(
        self,
        email: str,
        ttl_seconds: int = Limits.PASSWORD_RESET_WINDOW_MINUTES * 60,
    ) -> int:
        try:
            key = f"{RedisKeys.PASSWORD_RESET_RATE}{email.lower()}"
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl_seconds)
            results = await pipe.execute()
            return results[0]
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    async def get_password_reset_rate(self, email: str) -> int:
        try:
            key = f"{RedisKeys.PASSWORD_RESET_RATE}{email.lower()}"
            count = await self.client.get(key)
            return int(count) if count else 0
        except (aioredis.ConnectionError, aioredis.TimeoutError, ValueError):
            return 0

    # ========== WebSocket Ticket éphémère (P1-1) ==========

    WS_TICKET_TTL_SECONDS = 30

    async def store_ws_ticket(self, ticket_id: str, claims: dict) -> bool:
        """Stocke un ticket WS éphémère (usage unique, TTL 30s). FAIL-CLOSED."""
        try:
            key = RedisKeys.ws_ticket(ticket_id)
            return bool(await self.client.setex(
                key, self.WS_TICKET_TTL_SECONDS, json.dumps(claims),
            ))
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def consume_ws_ticket(self, ticket_id: str) -> dict | None:
        """Récupère ET supprime un ticket WS de façon atomique (GETDEL).

        Returns:
            dict claims si ticket valide, None si absent/expiré.
        """
        try:
            key = RedisKeys.ws_ticket(ticket_id)
            raw = await self.client.getdel(key)
            if raw is None:
                return None
            return json.loads(raw)
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return None

    # ========== Mode dégradé (§S-08.4) ==========

    async def set_degraded_flag(self, flag_key: str, ttl_seconds: int = 3600) -> bool:
        """Active un flag de dégradation dans Redis-SEC (§S-08.4)."""
        try:
            return bool(await self.client.setex(flag_key, ttl_seconds, "1"))
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            logger.warning("Redis-SEC down: cannot set degraded flag %s", flag_key)
            return False

    async def clear_degraded_flag(self, flag_key: str) -> bool:
        """Désactive un flag de dégradation."""
        try:
            return bool(await self.client.delete(flag_key))
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def is_degraded(self, flag_key: str) -> bool:
        """Vérifie si un flag de dégradation est actif. FAIL-OPEN."""
        try:
            return await self.client.exists(flag_key) == 1
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False  # FAIL-OPEN

    async def get_degradation_level(self) -> str:
        """Retourne le niveau de dégradation actuel (§S-08.4 4 niveaux)."""
        try:
            if await self.is_degraded(RedisKeys.DEGRADED_EMERGENCY_BYPASS):
                return "EMERGENCY_BYPASS"
            if await self.is_degraded(RedisKeys.DEGRADED_AUTH_DOWN):
                return "AUTH_DOWN"
            if await self.is_degraded(RedisKeys.DEGRADED_READ_ONLY):
                return "READ_ONLY"
            return "NOMINAL"
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return "AUTH_DOWN"

    # ========== OAuth State (PKCE / state single-use) ==========

    async def store_oauth_state(self, state: str, data: dict, ttl: int = 300) -> None:
        """Stocke l'état OAuth PKCE (single-use, TTL 5 min). FAIL-CLOSED."""
        try:
            key = f"oauth_state:{state}"
            await self.client.setex(key, ttl, json.dumps(data))
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("redis_sec.store_oauth_state failed: %s", e)
            raise  # FAIL-CLOSED : si stockage impossible → bloquer le flow

    async def consume_oauth_state(self, state: str) -> Optional[dict]:
        """Récupère ET supprime l'état OAuth de façon atomique (GETDEL). FAIL-CLOSED.

        Returns:
            dict si l'état existe, None s'il est absent ou expiré.
        Raises:
            ConnectionError si Redis est down (FAIL-CLOSED).
        """
        try:
            key = f"oauth_state:{state}"
            raw = await self.client.getdel(key)
            if raw is None:
                return None
            return json.loads(raw)
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("redis_sec.consume_oauth_state failed: %s", e)
            raise  # FAIL-CLOSED

    # ========== Health Check ==========

    async def health_check(self) -> dict:
        try:
            if not await self.ping():
                return {"status": "unhealthy", "instance": "redis-sec", "connected": False}
            info = await self.client.info("server")
            return {
                "status": "healthy",
                "instance": "redis-sec",
                "connected": True,
                "redis_version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds"),
            }
        except Exception as e:
            return {"status": "unhealthy", "instance": "redis-sec", "connected": False, "error": str(e)}


class RedisCacheClient:
    """Client Redis-CACHE async — cache applicatif.

    Comportement si down : FAIL-OPEN (degradation, pas panne).
    Policy : allkeys-lru — eviction acceptable.
    """

    def __init__(self):
        self._client: Optional[AsyncRedis] = None

    @property
    def client(self) -> AsyncRedis:
        if self._client is None:
            self._client = aioredis.from_url(
                settings.REDIS_CACHE_URL,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=True,
                health_check_interval=60,
            )
        return self._client

    async def ping(self) -> bool:
        try:
            return await self.client.ping()
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    # ========== Generic Cache ==========

    async def cache_get(self, key: str) -> Optional[str]:
        try:
            return await self.client.get(key)
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return None

    async def cache_set(self, key: str, value: str, ttl_seconds: int) -> bool:
        try:
            return await self.client.setex(key, ttl_seconds, value)
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def cache_delete(self, key: str) -> bool:
        try:
            return await self.client.delete(key) > 0
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    # ========== RBAC Scope Cache (§3.1) ==========

    async def get_cached_scopes(self, role_name: str) -> Optional[list[str]]:
        try:
            key = RedisKeys.rbac_scope_cache(role_name)
            data = await self.client.get(key)
            return json.loads(data) if data else None
        except (aioredis.ConnectionError, aioredis.TimeoutError, ValueError):
            return None

    async def set_cached_scopes(self, role_name: str, scopes: list[str], ttl_seconds: int = 300) -> bool:
        try:
            key = RedisKeys.rbac_scope_cache(role_name)
            return await self.client.setex(key, ttl_seconds, json.dumps(scopes))
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    async def invalidate_cached_scopes(self, role_name: str) -> bool:
        try:
            key = RedisKeys.rbac_scope_cache(role_name)
            return await self.client.delete(key) > 0
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return False

    # ========== Compteurs metier ==========

    async def incr_reservation_counter(self, year: int) -> int:
        try:
            key = RedisKeys.reservation_counter(year)
            return await self.client.incr(key)
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    async def incr_invoice_counter(self, year: int) -> int:
        try:
            key = RedisKeys.invoice_counter(year)
            return await self.client.incr(key)
        except (aioredis.ConnectionError, aioredis.TimeoutError):
            return 0

    # ========== Health Check ==========

    async def health_check(self) -> dict:
        try:
            if not await self.ping():
                return {"status": "degraded", "instance": "redis-cache", "connected": False}
            info = await self.client.info("server")
            return {
                "status": "healthy",
                "instance": "redis-cache",
                "connected": True,
                "redis_version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds"),
            }
        except Exception as e:
            return {"status": "degraded", "instance": "redis-cache", "connected": False, "error": str(e)}


# ========== Singletons ==========

redis_sec = RedisSecClient()
redis_cache = RedisCacheClient()

# Backward compat — ancien code utilisant redis_client
redis_client = redis_sec
