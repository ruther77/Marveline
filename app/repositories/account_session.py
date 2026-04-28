"""Repository AccountSession — sessions liées à un membership (IAM v2)."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_session import AccountSession


class AsyncAccountSessionRepository:
    """Repository async pour AccountSession.

    Responsabilités :
        - Créer / révoquer des sessions
        - Lookup par session_id (chemin chaud — validation JWT à chaque requête)
        - Lister sessions actives par membership ou par tenant
        - Touch (mise à jour last_active_at)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_session_id(self, session_id: str) -> Optional[AccountSession]:
        """Lookup par SID (chemin chaud : validation JWT).

        Retourne la session quelle que soit son état (active ou révoquée)
        pour permettre les vérifications de révocation côté service.
        """
        result = await self.db.execute(
            select(AccountSession).filter(AccountSession.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_session_id(self, session_id: str) -> Optional[AccountSession]:
        """Lookup par SID — uniquement sessions non-révoquées et non-expirées."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(AccountSession).filter(
                and_(
                    AccountSession.session_id == session_id,
                    AccountSession.revoked_at.is_(None),
                    AccountSession.expires_at > now,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_active_by_membership(
        self,
        membership_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AccountSession], int]:
        """Liste les sessions actives d'un membership."""
        limit = min(limit, 200)
        now = datetime.now(timezone.utc)

        stmt = (
            select(AccountSession, func.count().over().label("_total"))
            .filter(
                and_(
                    AccountSession.membership_id == membership_id,
                    AccountSession.revoked_at.is_(None),
                    AccountSession.expires_at > now,
                )
            )
            .order_by(AccountSession.last_active_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        items = [row[0] for row in rows]
        total = rows[0][1] if rows else 0
        return (items, total)

    async def list_active_by_tenant(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AccountSession], int]:
        """Liste les sessions actives d'un tenant (usage admin)."""
        limit = min(limit, 500)
        now = datetime.now(timezone.utc)

        stmt = (
            select(AccountSession, func.count().over().label("_total"))
            .filter(
                and_(
                    AccountSession.tenant_id == tenant_id,
                    AccountSession.revoked_at.is_(None),
                    AccountSession.expires_at > now,
                )
            )
            .order_by(AccountSession.last_active_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        items = [row[0] for row in rows]
        total = rows[0][1] if rows else 0
        return (items, total)

    async def create(self, session: AccountSession) -> AccountSession:
        """Persiste une nouvelle session."""
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def revoke(
        self,
        session: AccountSession,
        reason: str,
    ) -> AccountSession:
        """Révoque une session individuelle."""
        session.revoked_at = datetime.now(timezone.utc)
        session.revoke_reason = reason
        await self.db.flush()
        return session

    async def revoke_all_by_membership(
        self,
        membership_id: int,
        reason: str,
        except_session_id: Optional[str] = None,
    ) -> int:
        """Révoque toutes les sessions actives d'un membership.

        Args:
            membership_id: ID du membership cible
            reason: Motif de révocation (audit trail)
            except_session_id: SID à préserver (ex: session courante)

        Returns:
            Nombre de sessions révoquées
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(AccountSession)
            .where(
                and_(
                    AccountSession.membership_id == membership_id,
                    AccountSession.revoked_at.is_(None),
                )
            )
            .values(revoked_at=now, revoke_reason=reason)
        )
        if except_session_id is not None:
            stmt = stmt.where(AccountSession.session_id != except_session_id)

        result = await self.db.execute(stmt)
        return result.rowcount

    async def revoke_all_by_account(
        self,
        account_id: int,
        reason: str,
        except_device_id: Optional[str] = None,
    ) -> int:
        """Révoque toutes les sessions actives d'un account (cross-membership).

        Utilisé lors d'un reset ou changement de mot de passe pour révoquer
        les sessions sur tous les tenants de l'account.

        Args:
            account_id: ID du compte (accounts.id)
            reason: Motif de révocation
            except_device_id: device_id à préserver (ex: device courant)

        Returns:
            Nombre de sessions révoquées
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(AccountSession)
            .where(
                and_(
                    AccountSession.account_id == account_id,
                    AccountSession.revoked_at.is_(None),
                )
            )
            .values(revoked_at=now, revoke_reason=reason)
        )
        if except_device_id is not None:
            stmt = stmt.where(AccountSession.device_id != except_device_id)

        result = await self.db.execute(stmt)
        return result.rowcount

    async def touch(self, session_id: str) -> None:
        """Met à jour last_active_at (sliding window TTL côté session)."""
        await self.db.execute(
            update(AccountSession)
            .where(AccountSession.session_id == session_id)
            .values(last_active_at=datetime.now(timezone.utc))
        )

    async def list_recent(self, account_id: int, days: int = 30) -> list[AccountSession]:
        """M-05 : sessions recentes d'un compte (adaptive MFA)."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            select(AccountSession)
            .where(
                AccountSession.account_id == account_id,
                AccountSession.created_at >= cutoff,
            )
            .order_by(AccountSession.created_at.desc())
            .limit(50)
        )
        return list(result.scalars().all())
