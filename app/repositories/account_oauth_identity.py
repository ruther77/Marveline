"""Repository AccountOAuthIdentity — identités OAuth liées aux comptes globaux (IAM v2)."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_oauth_identity import AccountOAuthIdentity


class AsyncAccountOAuthIdentityRepository:
    """Repository async pour AccountOAuthIdentity.

    Requêtes globales (sans filtre tenant) — l'isolation tenant est gérée
    au niveau TenantMembership lors du flow OAuth callback.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_provider_subject(
        self,
        provider: str,
        provider_subject: str,
    ) -> Optional[AccountOAuthIdentity]:
        """Lookup par (provider, provider_subject) — clé unique de l'identité OAuth.

        Returns:
            AccountOAuthIdentity ou None si non trouvé.
        """
        result = await self.db.execute(
            select(AccountOAuthIdentity).filter(
                AccountOAuthIdentity.provider == provider,
                AccountOAuthIdentity.provider_subject == provider_subject,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        account_id: int,
        provider: str,
        provider_subject: str,
        email_at_provider: Optional[str] = None,
    ) -> AccountOAuthIdentity:
        """Lie un compte à une identité OAuth (insert).

        Raises:
            IntegrityError si (provider, provider_subject) déjà lié à un autre compte.
        """
        identity = AccountOAuthIdentity(
            account_id=account_id,
            provider=provider,
            provider_subject=provider_subject,
            email_at_provider=email_at_provider,
        )
        self.db.add(identity)
        await self.db.flush()
        await self.db.refresh(identity)
        return identity
