"""Repository pour les API Keys avec isolation multi-tenant."""
from typing import Optional
from sqlalchemy import and_
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository
from app.models.api_key import ApiKey


class ApiKeyRepository(BaseRepository[ApiKey]):
    """Repository pour CRUD et recherche des API keys.

    Herite de BaseRepository pour:
        - Isolation multi-tenant automatique
        - Soft delete
        - Pagination
        - Cache Redis
    """

    def __init__(self, db: Session):
        super().__init__(db, ApiKey)

    def get_by_key_hash(self, key_hash: str) -> Optional[ApiKey]:
        """Recherche une API key par son hash SHA-256.

        Utilisee lors de l'authentification par API key.
        PAS de filtre tenant_id ici (le tenant est determine APRES le lookup).

        Args:
            key_hash: SHA-256 du full key

        Returns:
            ApiKey si trouvee et active, None sinon
        """
        return (
            self.db.query(ApiKey)
            .filter(
                and_(
                    ApiKey.key_hash == key_hash,
                    ApiKey.is_active.is_(True),
                )
            )
            .first()
        )

    def list_by_tenant(
        self,
        tenant_id: int,
        include_inactive: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ApiKey], int]:
        """Liste les API keys d'un tenant avec pagination.

        Args:
            tenant_id: ID du tenant
            include_inactive: Inclure les cles desactivees
            skip: Offset pour pagination
            limit: Nombre max de resultats

        Returns:
            Tuple (liste de cles, total count)
        """
        query = self.db.query(ApiKey).filter(ApiKey.tenant_id == tenant_id)
        if not include_inactive:
            query = query.filter(ApiKey.is_active.is_(True))

        total = query.count()
        items = (
            query
            .order_by(ApiKey.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total

    def get_by_id_and_tenant(
        self,
        api_key_id: int,
        tenant_id: int,
    ) -> Optional[ApiKey]:
        """Recupere une API key par ID avec isolation tenant.

        Args:
            api_key_id: ID de la cle
            tenant_id: ID du tenant

        Returns:
            ApiKey ou None
        """
        return (
            self.db.query(ApiKey)
            .filter(
                and_(
                    ApiKey.id == api_key_id,
                    ApiKey.tenant_id == tenant_id,
                )
            )
            .first()
        )

    def prefix_exists(self, key_prefix: str, tenant_id: int) -> bool:
        """Verifie si un prefixe existe deja pour ce tenant.

        Args:
            key_prefix: Prefixe a verifier
            tenant_id: ID du tenant

        Returns:
            True si le prefixe existe
        """
        return (
            self.db.query(ApiKey)
            .filter(
                and_(
                    ApiKey.key_prefix == key_prefix,
                    ApiKey.tenant_id == tenant_id,
                )
            )
            .first()
        ) is not None

    def update_last_used(
        self,
        api_key: ApiKey,
        ip_address: Optional[str] = None,
    ) -> None:
        """Met a jour les statistiques d'utilisation.

        Args:
            api_key: Instance ApiKey a mettre a jour
            ip_address: IP du client
        """
        from datetime import datetime, timezone

        api_key.last_used_at = datetime.now(timezone.utc)
        api_key.usage_count += 1
        if ip_address:
            api_key.last_used_ip = ip_address
        self.db.add(api_key)

class AsyncApiKeyRepository:
    """Version async de ApiKeyRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy import select
        self.db: AsyncSession = db
        self._select = select

    async def get_by_key_hash(self, key_hash: str) -> Optional[ApiKey]:
        from sqlalchemy import select, and_
        result = await self.db.execute(
            select(ApiKey).where(and_(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True)))
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self, tenant_id: int, include_inactive: bool = False, skip: int = 0, limit: int = 100
    ) -> tuple[list[ApiKey], int]:
        from sqlalchemy import select, func
        q = select(ApiKey).where(ApiKey.tenant_id == tenant_id)
        if not include_inactive:
            q = q.where(ApiKey.is_active.is_(True))
        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar() or 0
        items_result = await self.db.execute(
            q.order_by(ApiKey.created_at.desc()).offset(skip).limit(limit)
        )
        return list(items_result.scalars().all()), total

    async def get_by_id_and_tenant(self, api_key_id: int, tenant_id: int) -> Optional[ApiKey]:
        from sqlalchemy import select, and_
        result = await self.db.execute(
            select(ApiKey).where(and_(ApiKey.id == api_key_id, ApiKey.tenant_id == tenant_id))
        )
        return result.scalar_one_or_none()

    async def prefix_exists(self, key_prefix: str, tenant_id: int) -> bool:
        from sqlalchemy import select, and_
        result = await self.db.execute(
            select(ApiKey).where(and_(ApiKey.key_prefix == key_prefix, ApiKey.tenant_id == tenant_id))
        )
        return result.scalar_one_or_none() is not None

    async def update_last_used(self, api_key: ApiKey, ip_address: Optional[str] = None) -> None:
        from datetime import datetime, timezone
        api_key.last_used_at = datetime.now(timezone.utc)
        api_key.usage_count += 1
        if ip_address:
            api_key.last_used_ip = ip_address
        await self.db.flush()

    async def create(self, data: dict) -> ApiKey:
        obj = ApiKey(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def soft_delete(self, obj: ApiKey) -> ApiKey:
        obj.is_active = False
        await self.db.flush()
        return obj
