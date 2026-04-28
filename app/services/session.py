"""Service de gestion des sessions utilisateur (DB PostgreSQL + Redis-SEC).

Architecture CaroCorp v3 (§6.6-6.10) :
    - Session DB (account_sessions) : source de vérité, audit, révocation
    - Session Redis (HASH) : hot path, TTL 7 jours, données courantes
    - Index Redis SET : user_sessions_index:{uid} = SET["did:sid"]
    - Max 5 sessions par user (éviction DB + Redis de la plus ancienne)
    - Device ID : fingerprint déterministe SHA-256 (User-Agent + IP prefix)

Toutes les méthodes sont async (redis.asyncio, PHASE 2).
Ordre opérations : Redis first, DB flush ensuite (P2-04).
"""
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_sec
from app.constants import SessionConfig
from app.models.account_session import AccountSession
from app.models.tenant_membership import TenantMembership

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = SessionConfig.SESSION_TTL_SECONDS


def generate_device_id(user_agent: str, ip_address: str) -> str:
    """Génère un device_id déterministe à partir du User-Agent et de l'IP (§8.1)."""
    ip_parts = ip_address.split(".")
    if len(ip_parts) == 4:
        ip_prefix = ".".join(ip_parts[:3])
    else:
        ip_prefix = ip_address[:16]

    fingerprint = f"{user_agent.strip()}|{ip_prefix}"
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    return digest[:32]


class SessionService:
    """Service de gestion des sessions — CaroCorp Auth v3 §6.6-6.10."""

    async def create_session(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
        device_id: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        mfa_verified: bool = False,
    ) -> str:
        """Crée une session DB + Redis simultanément (IAM v2 — AccountSession)."""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=SESSION_TTL_SECONDS)

        # Résoudre membership_id depuis (account_id, tenant_id) — requis par AccountSession
        membership_row = await db.execute(
            select(TenantMembership).where(
                TenantMembership.account_id == user_id,
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.status == "active",
            )
        )
        membership = membership_row.scalar_one_or_none()
        if not membership:
            raise ValueError(
                f"No active membership for account {user_id} in tenant {tenant_id}"
            )

        await self._enforce_max_sessions(db, user_id)

        db_session = AccountSession(
            session_id=session_id,
            account_id=user_id,
            membership_id=membership.id,
            tenant_id=tenant_id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=now,
            last_active_at=now,
            expires_at=expires_at,
            mfa_verified=mfa_verified,
        )
        db.add(db_session)
        await db.flush()

        session_data = {
            "session_id": session_id,
            "user_id": str(user_id),
            "tenant_id": str(tenant_id),
            "device_id": device_id,
            "ip_address": ip_address,
            "user_agent": user_agent or "",
            "created_at": now.isoformat(),
            "last_activity": now.isoformat(),
            "mfa_verified": "1" if mfa_verified else "0",
        }
        await redis_sec.store_session(
            user_id=user_id,
            device_id=device_id,
            session_id=session_id,
            data=session_data,
            ttl_seconds=SESSION_TTL_SECONDS,
        )

        logger.info(
            "Session created: sid=%s user=%s device=%.8s ip=%s",
            session_id, user_id, device_id, ip_address,
        )

        return session_id

    async def get_session(self, db: AsyncSession, session_id: str) -> Optional[AccountSession]:
        """Récupère une session active depuis la DB."""
        result = await db.execute(
            select(AccountSession).filter(
                AccountSession.session_id == session_id,
                AccountSession.revoked_at.is_(None),
            )
        )
        return result.scalars().first()

    async def list_sessions(self, db: AsyncSession, user_id: int) -> list[AccountSession]:
        """Liste les sessions actives d'un user."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(AccountSession)
            .filter(
                AccountSession.account_id == user_id,
                AccountSession.revoked_at.is_(None),
                AccountSession.expires_at > now,
            )
            .order_by(AccountSession.created_at.desc())
        )
        return result.scalars().all()

    async def revoke_session(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: int,
        reason: str = "user_logout",
    ) -> bool:
        """Révoque une session spécifique (Redis first, DB ensuite — P2-04)."""
        result = await db.execute(
            select(AccountSession).filter(
                AccountSession.session_id == session_id,
                AccountSession.account_id == user_id,
                AccountSession.revoked_at.is_(None),
            )
        )
        db_session = result.scalars().first()

        if not db_session:
            return False

        device_id = db_session.device_id

        # Redis first (P2-04) — révocation tokens avant marquage DB
        await redis_sec.revoke_refresh_jti(user_id, device_id, session_id)
        await redis_sec.delete_session(user_id, device_id, session_id)
        await redis_sec.revoke_csrf_token(session_id)  # spec §04 §4.3 — CSRF lié à la session

        # DB ensuite
        db_session.revoked_at = datetime.now(timezone.utc)
        db_session.revoke_reason = reason
        await db.flush()

        logger.info(
            "Session revoked: sid=%s user=%s device=%.8s reason=%s",
            session_id, user_id, device_id, reason,
        )

        return True

    async def revoke_all_sessions(
        self,
        db: AsyncSession,
        user_id: int,
        reason: str = "logout_all",
    ) -> int:
        """Révoque toutes les sessions actives d'un user (Redis first, DB ensuite — P2-04)."""
        result = await db.execute(
            select(AccountSession).filter(
                AccountSession.account_id == user_id,
                AccountSession.revoked_at.is_(None),
            )
        )
        active_sessions = result.scalars().all()

        # Redis first (P2-04)
        await redis_sec.revoke_all_user_sessions(user_id)

        # DB ensuite
        revoke_time = datetime.now(timezone.utc)
        count = 0
        for sess in active_sessions:
            sess.revoked_at = revoke_time
            sess.revoke_reason = reason
            count += 1

        if count:
            await db.flush()
            logger.info("All sessions revoked: user=%s count=%s", user_id, count)

        return count

    async def revoke_all_sessions_except_device(
        self,
        db: AsyncSession,
        user_id: int,
        current_did: str,
        reason: str = "password_change",
    ) -> int:
        """Révoque toutes les sessions sauf le device courant (spec §4.5 NC-06)."""
        q = select(AccountSession).filter(
            AccountSession.account_id == user_id,
            AccountSession.revoked_at.is_(None),
        )
        if current_did:
            q = q.filter(AccountSession.device_id != current_did)

        result = await db.execute(q)
        active_sessions = result.scalars().all()

        # Redis first (P2-04)
        await redis_sec.revoke_sessions_except_device(user_id, current_did)

        # DB ensuite
        revoke_time = datetime.now(timezone.utc)
        count = 0
        for sess in active_sessions:
            sess.revoked_at = revoke_time
            sess.revoke_reason = reason
            count += 1

        if count:
            await db.flush()
            logger.info(
                "Sessions revoked except device: user=%s did=%s count=%s",
                user_id, current_did, count,
            )

        return count

    async def update_activity(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: int,
        device_id: str,
    ) -> bool:
        """Met à jour last_active_at (DB + Redis)."""
        result = await db.execute(
            select(AccountSession).filter(
                AccountSession.session_id == session_id,
                AccountSession.revoked_at.is_(None),
            )
        )
        db_session = result.scalars().first()

        if not db_session:
            return False

        db_session.last_active_at = datetime.now(timezone.utc)
        await db.flush()

        await redis_sec.update_session_activity(user_id, device_id, session_id)

        return True

    async def _enforce_max_sessions(self, db: AsyncSession, user_id: int) -> None:
        """Évince les sessions les plus anciennes si MAX_SESSIONS_PER_USER atteint (§6.8)."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(AccountSession)
            .filter(
                AccountSession.account_id == user_id,
                AccountSession.revoked_at.is_(None),
                AccountSession.expires_at > now,
            )
            .order_by(AccountSession.created_at.asc())
            .with_for_update()  # D1 — évite race condition création simultanée (§6.8)
        )
        active_sessions = result.scalars().all()

        to_evict = len(active_sessions) - SessionConfig.MAX_SESSIONS_PER_USER + 1
        if to_evict <= 0:
            return

        eviction_time = datetime.now(timezone.utc)
        for sess in active_sessions[:to_evict]:
            # Redis first (P2-04)
            await redis_sec.revoke_refresh_jti(user_id, sess.device_id, sess.session_id)
            await redis_sec.delete_session(user_id, sess.device_id, sess.session_id)
            await redis_sec.revoke_csrf_token(sess.session_id)  # D2 — évite CSRF orphelins

            sess.revoked_at = eviction_time
            sess.revoke_reason = "max_sessions_eviction"

            logger.info(
                "Session evicted (max=%s): sid=%s user=%s device=%.8s",
                SessionConfig.MAX_SESSIONS_PER_USER,
                sess.session_id,
                user_id,
                sess.device_id,
            )

        await db.flush()


# Singleton
session_service = SessionService()
