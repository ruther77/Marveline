"""Repository Account — identité globale (IAM v2).

Account n'a pas de TenantMixin : les requêtes sont globales.
Isolation tenant gérée au niveau TenantMembership.
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account


class AsyncAccountRepository:
    """Repository async pour Account (identité globale, sans filtre tenant).

    Toutes les requêtes sont globales — l'isolation tenant se fait au
    niveau TenantMembership, pas ici.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, account_id: int) -> Optional[Account]:
        """Récupère un compte par ID (global, sans filtre tenant)."""
        result = await self.db.execute(
            select(Account).filter(Account.id == account_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_id(self, account_id: int) -> Optional[Account]:
        """Récupère un compte actif par ID (is_active=True)."""
        result = await self.db.execute(
            select(Account).filter(
                Account.id == account_id,
                Account.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[Account]:
        """Lookup global par email normalisé (pour login).

        Args:
            email: Email recherché (normalisé lower+strip par event SQLAlchemy)

        Returns:
            Account ou None — pas d'erreur si absent (anti info-leakage)
        """
        email = email.lower().strip()
        result = await self.db.execute(
            select(Account).filter(Account.email == email)
        )
        return result.scalar_one_or_none()

    async def get_active_by_email(self, email: str) -> Optional[Account]:
        """Lookup global par email — uniquement les comptes actifs."""
        email = email.lower().strip()
        result = await self.db.execute(
            select(Account).filter(
                Account.email == email,
                Account.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> Optional[Account]:
        """Lookup par UUID externe (claim 'sub' du JWT)."""
        result = await self.db.execute(
            select(Account).filter(Account.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Vérifie si un email est déjà enregistré (global)."""
        email = email.lower().strip()
        result = await self.db.execute(
            select(Account.id).filter(Account.email == email)
        )
        return result.scalar_one_or_none() is not None

    async def create(self, account: Account) -> Account:
        """Persiste un nouveau compte.

        Note: tenant_id absent — Account est une entité globale.
        """
        self.db.add(account)
        await self.db.flush()
        await self.db.refresh(account)
        return account

    async def flush(self, account: Account) -> Account:
        """Flush les modifications d'un compte existant."""
        await self.db.flush()
        await self.db.refresh(account)
        return account
