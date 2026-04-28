"""Service de gestion des tokens JWT : whitelist, blacklist, rotation, replay detection.

Responsabilités:
    - Refresh token whitelist (JTI → Redis, vérifié à chaque refresh)
    - Access token blacklist (JTI → Redis au logout, vérifié à chaque requête)
    - Token family rotation (chaque refresh émet un nouveau refresh token)
    - Replay detection (réutilisation d'un ancien refresh → toute la famille révoquée)

Architecture CaroCorp v3 (§2.1-2.9):
    - Whitelist : whitelist:refresh:{uid}:{did}:{sid} = JTI actif (STRING)
    - Blacklist : blacklist:jti:{jti} = "1" (TTL résiduel)
    - Famille   : family:{fid} = SET de JTIs (pour replay detection Lua)
    - JTI meta  : jti:meta:{jti} = exp_timestamp (TTL résiduel pour Lua §2.6)
    - Rotation atomique : Lua refresh_check_v3 (§2.6)

Toutes les méthodes sont async (redis.asyncio, PHASE 2).
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.core.redis import redis_sec
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from app.constants import Limits

logger = logging.getLogger(__name__)

REFRESH_TTL_SECONDS = Limits.REFRESH_TOKEN_EXPIRE_SECONDS


class TokenService:
    """Service de gestion avancée des tokens JWT — CaroCorp Auth v3 §2.1-2.9."""

    # ========== Helpers: claims builders (§1.4) ==========

    @staticmethod
    async def _build_access_claims(
        user_id: int,
        tenant_id: int,
        role: str,
        device_id: str,
        session_id: str,
        membership_id: Optional[int] = None,
    ) -> dict:
        """Claims access token v3 (§1.2) : sub, tid, mid, did, sid, role, scopes."""
        from app.services.rbac import get_role_scopes
        scopes = await get_role_scopes(role, None)
        claims: dict = {
            "sub": str(user_id),
            "tid": str(tenant_id),
            "did": device_id,
            "sid": session_id,
            "role": role,
            "scopes": scopes,
        }
        if membership_id is not None:
            claims["mid"] = str(membership_id)
        return claims

    @staticmethod
    def _build_refresh_claims(
        user_id: int,
        tenant_id: int,
        family_id: str,
        device_id: str,
        session_id: str,
        membership_id: Optional[int] = None,
    ) -> dict:
        """Claims refresh token v3 (§1.4) : sub, tid, mid, did, sid, fid."""
        claims: dict = {
            "sub": str(user_id),
            "tid": str(tenant_id),
            "did": device_id,
            "sid": session_id,
            "fid": family_id,
        }
        if membership_id is not None:
            claims["mid"] = str(membership_id)
        return claims

    # ========== Login: émettre tokens + enregistrer ==========

    async def issue_tokens(
        self,
        user_id: int,
        tenant_id: int,
        role: str,
        device_id: str,
        session_id: str,
        membership_id: Optional[int] = None,
        app_code: Optional[str] = None,
    ) -> tuple[str, str, int]:
        """Émet une paire access+refresh tokens et enregistre dans Redis.

        ISO-APP-01 : si `app_code` fourni, l'audience JWT est dérivée depuis
        settings.JWT_AUDIENCES[app_code]. Sinon fallback sur JWT_AUDIENCE (legacy).
        """
        family_id = str(uuid.uuid4())

        access_claims = await self._build_access_claims(
            user_id, tenant_id, role, device_id, session_id, membership_id
        )
        refresh_claims = self._build_refresh_claims(
            user_id, tenant_id, family_id, device_id, session_id, membership_id
        )

        audience = settings.JWT_AUDIENCES.get(app_code) if app_code else None
        access_token = create_access_token(access_claims, audience=audience)
        refresh_token = create_refresh_token(refresh_claims, audience=audience)

        access_payload = decode_token(access_token)
        access_jti = access_payload["jti"]
        access_exp = int(access_payload["exp"])

        refresh_payload = decode_token(refresh_token)
        refresh_jti = refresh_payload["jti"]

        # 1. Whitelist
        await redis_sec.store_refresh_jti(
            jti=refresh_jti,
            user_id=user_id,
            tenant_id=tenant_id,
            family_id=family_id,
            device_id=device_id,
            session_id=session_id,
            ttl_seconds=REFRESH_TTL_SECONDS,
        )

        # 2. Famille
        await redis_sec.store_token_family(
            family_id=family_id,
            jti=refresh_jti,
            ttl_seconds=REFRESH_TTL_SECONDS,
        )

        # 3. JTI meta (avant Lua — P1-07 déjà correct, on maintient l'ordre)
        await redis_sec.store_jti_meta(
            jti_access=access_jti,
            exp_timestamp=access_exp,
            ttl_seconds=settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS + 60,
        )

        return access_token, refresh_token, settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS

    # ========== Switch-membership: access token only (§2.10) ==========

    async def issue_access_only(
        self,
        user_id: int,
        tenant_id: int,
        role: str,
        device_id: str,
        session_id: str,
        membership_id: Optional[int] = None,
        app_code: Optional[str] = None,
    ) -> tuple[str, int]:
        """Émet uniquement un access token — sans rotation du refresh cookie.

        Utilisé pour switch-membership : l'access token change de tenant (tid)
        mais le refresh cookie reste inchangé (il appartient au tenant d'origine).
        Le JTI de l'access token est enregistré dans redis_sec (TTL résiduel).

        ISO-APP-01 : audience JWT dérivée de app_code si fourni.
        """
        access_claims = await self._build_access_claims(
            user_id, tenant_id, role, device_id, session_id, membership_id
        )
        audience = settings.JWT_AUDIENCES.get(app_code) if app_code else None
        access_token = create_access_token(access_claims, audience=audience)
        access_payload = decode_token(access_token)
        access_jti = access_payload["jti"]
        access_exp = int(access_payload["exp"])

        await redis_sec.store_jti_meta(
            jti_access=access_jti,
            exp_timestamp=access_exp,
            ttl_seconds=settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS + 60,
        )

        return access_token, settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS

    # ========== Refresh: rotation atomique via Lua (§2.6) ==========

    async def rotate_refresh_token(
        self,
        old_refresh_token: str,
        user_id: int,
        tenant_id: int,
        role: str,
        membership_id: Optional[int] = None,
        app_code: Optional[str] = None,
    ) -> tuple[str, str, int]:
        """Rotation atomique via Lua refresh_check_v3 (§2.6).

        ISO-APP-01 : audience JWT dérivée de app_code si fourni.
        """
        from app.core.exceptions import TokenRevoked, TokenReplayDetected

        old_payload = decode_token(old_refresh_token)
        old_jti = old_payload.get("jti")
        family_id = old_payload.get("fid")
        device_id = old_payload.get("did")
        session_id = old_payload.get("sid")

        if not old_jti or not family_id or not device_id or not session_id:
            raise TokenRevoked()

        audience = settings.JWT_AUDIENCES.get(app_code) if app_code else None
        new_refresh_claims = self._build_refresh_claims(
            user_id, tenant_id, family_id, device_id, session_id
        )
        new_refresh_token = create_refresh_token(new_refresh_claims, audience=audience)
        new_payload = decode_token(new_refresh_token)
        new_jti = new_payload["jti"]

        now = str(int(datetime.now(timezone.utc).timestamp()))
        try:
            result = await redis_sec.evalsha(
                "refresh_check_v3",
                old_jti,
                str(user_id),
                device_id,
                session_id,
                family_id,
                now,
                new_jti,
            )
        except RuntimeError:
            result = await self._manual_rotate(
                old_jti, user_id, tenant_id, device_id, session_id, family_id, new_jti
            )

        result_str = str(result)

        if result_str == "REPLAY_DETECTED":
            logger.warning(
                "Replay detected: jti=%s family=%s user=%s",
                old_jti, family_id, user_id,
            )
            raise TokenReplayDetected()

        if result_str == "TOKEN_INVALID" or not result_str.startswith("OK:"):
            raise TokenRevoked()

        new_access_claims = await self._build_access_claims(
            user_id, tenant_id, role, device_id, session_id, membership_id
        )
        new_access_token = create_access_token(new_access_claims, audience=audience)

        new_access_payload = decode_token(new_access_token)
        new_access_jti = new_access_payload["jti"]
        new_access_exp = int(new_access_payload["exp"])

        await redis_sec.store_jti_meta(
            jti_access=new_access_jti,
            exp_timestamp=new_access_exp,
            ttl_seconds=settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS + 60,
        )

        # P2-06 : sliding window — re-etendre le TTL whitelist a 7j
        wl_key = f"whitelist:refresh:{user_id}:{device_id}:{session_id}"
        await redis_sec.client.expire(wl_key, settings.JWT_REFRESH_TOKEN_EXPIRE_SECONDS)

        return new_access_token, new_refresh_token, settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS

    async def _manual_rotate(
        self,
        old_jti: str,
        user_id: int,
        tenant_id: int,
        device_id: str,
        session_id: str,
        family_id: str,
        new_jti: str,
    ) -> str:
        """Fallback refusé — rotation token interdite sans Lua atomique.

        F1 — FAIL-CLOSED : lever RuntimeError plutôt que tolérer une rotation
        non-atomique en production (race condition token family).
        Le démarrage charge les scripts Lua via main.py → cette méthode
        ne devrait jamais être invoquée en conditions normales.
        """
        logger.critical(
            "Lua scripts non chargés — rotation token interdite. "
            "Redémarrer le serveur pour recharger les scripts. "
            "user=%s device=%s session=%s",
            user_id, device_id, session_id,
        )
        raise RuntimeError("Lua scripts requis pour rotation sécurisée")

    # ========== Logout: révoquer tokens (§4.2) ==========

    async def revoke_on_logout(
        self,
        access_token: str,
        user_id: int,
        device_id: str,
        session_id: str,
        refresh_token: Optional[str] = None,
    ) -> None:
        """Révoque les tokens lors d'un logout (§4.2)."""
        try:
            access_payload = decode_token(access_token)
            access_jti = access_payload.get("jti")
            if access_jti:
                exp = access_payload.get("exp", 0)
                now = int(datetime.now(timezone.utc).timestamp())
                remaining_ttl = max(int(exp) - now, 1)
                await redis_sec.blacklist_access_jti(access_jti, remaining_ttl)
        except Exception as exc:
            logger.warning("Failed to blacklist access JTI on logout: %s", exc)

        await redis_sec.revoke_refresh_jti(user_id, device_id, session_id)
        await redis_sec.delete_session(user_id, device_id, session_id)

    async def revoke_all_user_tokens(self, user_id: int) -> int:
        """Révoque toutes les sessions d'un utilisateur."""
        return await redis_sec.revoke_all_user_sessions(user_id)

    # ========== Validation ==========

    async def is_access_blacklisted(self, jti: str) -> bool:
        """Vérifie si un access token JTI est blacklisté."""
        return await redis_sec.is_access_blacklisted(jti)

    async def is_refresh_whitelisted(self, user_id: int, device_id: str, session_id: str) -> bool:
        """Vérifie si une session a un refresh token actif dans la whitelist."""
        return await redis_sec.get_refresh_jti(user_id, device_id, session_id) is not None


# Singleton
token_service = TokenService()
