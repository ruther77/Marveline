"""Repository TenantMembership — appartenance account↔tenant (IAM v2)."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tenant_membership import TenantMembership


class AsyncTenantMembershipRepository:
    """Repository async pour TenantMembership.

    Les requêtes sont filtrées par tenant_id quand pertinent.
    Pas d'héritage AsyncBaseRepository car TenantMembership n'a pas TenantMixin.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, membership_id: int) -> Optional[TenantMembership]:
        """Récupère un membership par ID (sans filtre tenant — usage admin)."""
        result = await self.db.execute(
            select(TenantMembership)
            .options(selectinload(TenantMembership.role))
            .filter(TenantMembership.id == membership_id)
        )
        return result.scalar_one_or_none()

    async def get_active(
        self,
        account_id: int,
        tenant_id: int,
    ) -> Optional[TenantMembership]:
        """Récupère le membership actif pour (account, tenant).

        Un seul membership actif possible grâce à l'index UNIQUE partiel
        WHERE revoked_at IS NULL.

        Returns:
            TenantMembership actif ou None (compte non-membre ou suspendu)
        """
        result = await self.db.execute(
            select(TenantMembership)
            .options(selectinload(TenantMembership.role))
            .filter(
                and_(
                    TenantMembership.account_id == account_id,
                    TenantMembership.tenant_id == tenant_id,
                    TenantMembership.revoked_at.is_(None),
                    TenantMembership.status == "active",
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_active_or_suspended(
        self,
        account_id: int,
        tenant_id: int,
    ) -> Optional[TenantMembership]:
        """Récupère le membership non-révoqué (actif ou suspendu)."""
        result = await self.db.execute(
            select(TenantMembership)
            .options(selectinload(TenantMembership.role))
            .filter(
                and_(
                    TenantMembership.account_id == account_id,
                    TenantMembership.tenant_id == tenant_id,
                    TenantMembership.revoked_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_by_account(self, account_id: int) -> list[TenantMembership]:
        """Liste tous les memberships actifs d'un compte (multi-tenant)."""
        result = await self.db.execute(
            select(TenantMembership)
            .options(selectinload(TenantMembership.role))
            .filter(
                and_(
                    TenantMembership.account_id == account_id,
                    TenantMembership.revoked_at.is_(None),
                    TenantMembership.status == "active",
                )
            )
            .order_by(TenantMembership.activated_at)
        )
        return list(result.scalars().all())

    async def list_by_tenant(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        include_revoked: bool = False,
    ) -> tuple[list[TenantMembership], int]:
        """Liste les memberships d'un tenant avec pagination."""
        limit = min(limit, 1000)

        stmt = (
            select(TenantMembership, func.count().over().label("_total"))
            .options(selectinload(TenantMembership.role))
            .filter(TenantMembership.tenant_id == tenant_id)
        )
        if not include_revoked:
            stmt = stmt.filter(TenantMembership.revoked_at.is_(None))

        stmt = stmt.order_by(TenantMembership.activated_at.desc()).offset(skip).limit(limit)

        result = await self.db.execute(stmt)
        rows = result.all()
        items = [row[0] for row in rows]
        total = rows[0][1] if rows else 0
        return (items, total)

    async def create(self, membership: TenantMembership) -> TenantMembership:
        """Persiste un nouveau membership."""
        self.db.add(membership)
        await self.db.flush()
        await self.db.refresh(membership)
        return membership

    async def revoke(
        self,
        membership: TenantMembership,
        reason: str,
    ) -> TenantMembership:
        """Révoque un membership (soft — jamais de DELETE).

        Post-condition : revoked_at IS NOT NULL, status = "offboarding".
        """
        membership.revoked_at = datetime.now(timezone.utc)
        membership.revoke_reason = reason
        membership.status = "offboarding"
        await self.db.flush()
        return membership

    async def suspend(self, membership: TenantMembership) -> TenantMembership:
        """Suspend un membership (status = suspended)."""
        membership.status = "suspended"
        membership.suspended_at = datetime.now(timezone.utc)
        await self.db.flush()
        return membership

    async def reactivate(self, membership: TenantMembership) -> TenantMembership:
        """Réactive un membership suspendu."""
        membership.status = "active"
        membership.suspended_at = None
        await self.db.flush()
        return membership
