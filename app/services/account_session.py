"""Service AccountSession — sessions liées à un membership (IAM v2).

Responsabilités :
    - Ouvrir une session après login réussi (membership résolu)
    - Valider une session active (non révoquée, non expirée)
    - Révoquer une session individuelle (logout)
    - Révoquer toutes les sessions d'un membership sauf la courante
    - Lister les sessions actives par membership ou par tenant
    - Marquer MFA vérifié (acr=2) après challenge TOTP réussi

Isolation tenant : tenant_id dénormalisé dans AccountSession — pas de JOIN.
Chaque query est filtrée par membership_id ou tenant_id selon le contexte.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ErrorMessages, Limits
from app.models.account_session import AccountSession
from app.repositories.account_session import AsyncAccountSessionRepository

logger = logging.getLogger(__name__)

_SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 jours (refresh token TTL)


class AccountSessionService:
    """Service de gestion des sessions IAM v2.

    Une session = un account dans un membership précis.
    La clé primaire logique est session_id (claim 'sid' dans JWT).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._repo = AsyncAccountSessionRepository(db)

    async def open(
        self,
        account_id: int,
        membership_id: int,
        tenant_id: int,
        device_id: str,
        ip_address: str,
        user_agent: Optional[str] = None,
    ) -> AccountSession:
        """Crée une nouvelle session après login réussi.

        Returns:
            Session créée avec session_id unique et expires_at = now + 7j.
        """
        session_id = secrets.token_hex(32)  # 64 chars hex = claim 'sid'
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=_SESSION_TTL_SECONDS)

        session = AccountSession(
            session_id=session_id,
            account_id=account_id,
            membership_id=membership_id,
            tenant_id=tenant_id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
            mfa_verified=False,
        )
        created = await self._repo.create(session)
        logger.info(
            "Session opened: account_id=%s membership_id=%s session_id=%s",
            account_id,
            membership_id,
            session_id,
        )
        return created

    async def validate(self, session_id: str) -> AccountSession:
        """Retourne la session active ou lève 401.

        Utilisé dans le middleware de validation JWT (chemin chaud).
        """
        session = await self._repo.get_active_by_session_id(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.SESSION_REVOKED,
            )
        return session

    async def get_by_session_id(self, session_id: str) -> Optional[AccountSession]:
        """Lookup brut par session_id (sans filtre actif)."""
        return await self._repo.get_by_session_id(session_id)

    async def revoke(
        self,
        session_id: str,
        requesting_membership_id: int,
        reason: str = "logout",
    ) -> None:
        """Révoque une session individuelle.

        Vérifie que la session appartient bien au membership demandeur (isolation).
        """
        session = await self._repo.get_by_session_id(session_id)
        if not session or session.membership_id != requesting_membership_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.NOT_FOUND,
            )
        if session.revoked_at is not None:
            return  # idempotent
        await self._repo.revoke(session, reason)
        logger.info(
            "Session revoked: session_id=%s membership_id=%s reason=%s",
            session_id,
            requesting_membership_id,
            reason,
        )

    async def revoke_all_except(
        self,
        membership_id: int,
        current_session_id: str,
        reason: str = "revoke_others",
    ) -> int:
        """Révoque toutes les sessions actives d'un membership sauf la courante.

        Returns:
            Nombre de sessions révoquées.
        """
        count = await self._repo.revoke_all_by_membership(
            membership_id=membership_id,
            reason=reason,
            except_session_id=current_session_id,
        )
        logger.info(
            "Revoked %d sessions for membership_id=%s (kept: %s)",
            count,
            membership_id,
            current_session_id,
        )
        return count

    async def revoke_all(self, membership_id: int, reason: str) -> int:
        """Révoque toutes les sessions actives d'un membership (ex: revoke membership).

        Returns:
            Nombre de sessions révoquées.
        """
        count = await self._repo.revoke_all_by_membership(
            membership_id=membership_id,
            reason=reason,
        )
        logger.info(
            "Revoked all %d sessions for membership_id=%s reason=%s",
            count,
            membership_id,
            reason,
        )
        return count

    async def list_by_membership(
        self,
        membership_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AccountSession], int]:
        """Liste les sessions actives d'un membership avec pagination."""
        return await self._repo.list_active_by_membership(
            membership_id, skip=skip, limit=limit
        )

    async def list_by_tenant(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AccountSession], int]:
        """Liste les sessions actives d'un tenant (usage admin)."""
        return await self._repo.list_active_by_tenant(
            tenant_id, skip=skip, limit=limit
        )

    async def mark_mfa_verified(self, session_id: str) -> None:
        """Marque la session comme MFA vérifié (acr=2 — step-up TOTP réussi)."""
        session = await self._repo.get_by_session_id(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.NOT_FOUND,
            )
        session.mfa_verified = True
        await self.db.flush()
        logger.info("MFA verified for session_id=%s", session_id)

    async def touch(self, session_id: str) -> None:
        """Met à jour last_active_at (sliding window activity tracking)."""
        await self._repo.touch(session_id)
