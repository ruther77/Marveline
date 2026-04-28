"""Service TenantMembership — appartenance account ↔ tenant (IAM v2).

Responsabilités :
    - Créer un membership (invite ou auto-provisioning)
    - Résoudre le membership actif pour (account, tenant)
    - Suspend / réactiver / révoquer un membership
    - Lister memberships par account ou par tenant

Isolation tenant : chaque query est filtrée par tenant_id via le repository.
"""
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ErrorMessages
from app.models.tenant_membership import TenantMembership
from app.repositories.tenant_membership import AsyncTenantMembershipRepository

logger = logging.getLogger(__name__)


class MembershipService:
    """Service de lifecycle TenantMembership (IAM v2)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._repo = AsyncTenantMembershipRepository(db)

    async def get_active(
        self,
        account_id: int,
        tenant_id: int,
    ) -> Optional[TenantMembership]:
        """Retourne le membership actif pour (account, tenant), ou None."""
        return await self._repo.get_active(account_id, tenant_id)

    async def require_active(
        self,
        account_id: int,
        tenant_id: int,
    ) -> TenantMembership:
        """Retourne le membership actif ou lève 403.

        Utilisé dans les flows auth pour garantir l'appartenance au tenant.
        """
        membership = await self._repo.get_active(account_id, tenant_id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorMessages.ACCESS_DENIED,
            )
        return membership

    async def get_by_id(self, membership_id: int) -> Optional[TenantMembership]:
        """Récupère un membership par ID (usage admin, sans filtre tenant)."""
        return await self._repo.get_by_id(membership_id)

    async def list_by_account(self, account_id: int) -> list[TenantMembership]:
        """Liste les memberships actifs d'un compte (multi-tenant)."""
        return await self._repo.list_by_account(account_id)

    async def list_by_tenant(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        include_revoked: bool = False,
    ) -> tuple[list[TenantMembership], int]:
        """Liste les memberships d'un tenant avec pagination."""
        return await self._repo.list_by_tenant(
            tenant_id, skip=skip, limit=limit, include_revoked=include_revoked
        )

    async def provision(
        self,
        account_id: int,
        tenant_id: int,
        role_name: str,
        invited_by: Optional[int] = None,
    ) -> TenantMembership:
        """Crée un membership (invite ou auto-provisioning).

        409 si un membership actif existe déjà pour (account, tenant).
        """
        existing = await self._repo.get_active_or_suspended(account_id, tenant_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un membership actif ou suspendu existe déjà pour ce compte et ce tenant.",
            )

        membership = TenantMembership(
            account_id=account_id,
            tenant_id=tenant_id,
            role_name=role_name,
            status="active",
            invited_by=invited_by,
        )
        return await self._repo.create(membership)

    async def suspend(self, membership_id: int, tenant_id: int) -> TenantMembership:
        """Suspend un membership (idempotent si déjà suspendu)."""
        membership = await self._require_membership_in_tenant(membership_id, tenant_id)

        if membership.status == "suspended":
            return membership

        if membership.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Impossible de suspendre un membership en état '{membership.status}'.",
            )

        return await self._repo.suspend(membership)

    async def reactivate(self, membership_id: int, tenant_id: int) -> TenantMembership:
        """Réactive un membership suspendu."""
        membership = await self._require_membership_in_tenant(membership_id, tenant_id)

        if membership.status != "suspended":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Impossible de réactiver un membership en état '{membership.status}'.",
            )

        return await self._repo.reactivate(membership)

    async def revoke(
        self,
        membership_id: int,
        tenant_id: int,
        reason: str,
    ) -> TenantMembership:
        """Révoque un membership (soft — jamais de DELETE)."""
        membership = await self._require_membership_in_tenant(membership_id, tenant_id)

        if membership.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce membership est déjà révoqué.",
            )

        return await self._repo.revoke(membership, reason)

    async def _require_membership_in_tenant(
        self,
        membership_id: int,
        tenant_id: int,
    ) -> TenantMembership:
        """Récupère un membership et vérifie son appartenance au tenant."""
        membership = await self._repo.get_by_id(membership_id)
        if not membership or membership.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.NOT_FOUND,
            )
        return membership
