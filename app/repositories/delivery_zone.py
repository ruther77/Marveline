"""Repository pour DeliveryZone."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.delivery_zone import DeliveryZone
from app.repositories.base import BaseRepository


class DeliveryZoneRepository(BaseRepository[DeliveryZone]):
    """Repository zones de livraison avec isolation multi-tenant."""

    def __init__(self, db: Session):
        super().__init__(db, DeliveryZone)

    def get_by_department_code(
        self, code: str, tenant_id: int
    ) -> Optional[DeliveryZone]:
        """Récupère une zone par son code département."""
        query = select(DeliveryZone).filter(
            DeliveryZone.department_code == code,
            DeliveryZone.tenant_id == tenant_id,
            DeliveryZone.is_active == True,  # noqa: E712
        )
        return self.db.execute(query).scalar_one_or_none()

    def code_exists(
        self, code: str, tenant_id: int, exclude_id: Optional[int] = None
    ) -> bool:
        """Vérifie si un code département existe déjà pour ce tenant."""
        query = select(DeliveryZone).filter(
            DeliveryZone.department_code == code,
            DeliveryZone.tenant_id == tenant_id,
            DeliveryZone.is_active == True,  # noqa: E712
        )
        if exclude_id:
            query = query.filter(DeliveryZone.id != exclude_id)
        return self.db.execute(query).scalar_one_or_none() is not None

    def list_active(self, tenant_id: int) -> list[DeliveryZone]:
        """Liste toutes les zones actives d'un tenant, triées par code."""
        query = (
            select(DeliveryZone)
            .filter(
                DeliveryZone.tenant_id == tenant_id,
                DeliveryZone.is_active == True,  # noqa: E712
            )
            .order_by(DeliveryZone.department_code)
        )
        return list(self.db.execute(query).scalars().all())


class AsyncDeliveryZoneRepository:
    """Version async de DeliveryZoneRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get_by_department_code(self, code: str, tenant_id: int) -> Optional[DeliveryZone]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(DeliveryZone).filter(DeliveryZone.department_code == code, DeliveryZone.tenant_id == tenant_id, DeliveryZone.is_active == True)  # noqa: E712
        )
        return result.scalar_one_or_none()

    async def code_exists(self, code: str, tenant_id: int, exclude_id: Optional[int] = None) -> bool:
        from sqlalchemy import select
        q = select(DeliveryZone).filter(DeliveryZone.department_code == code, DeliveryZone.tenant_id == tenant_id, DeliveryZone.is_active == True)  # noqa: E712
        if exclude_id:
            q = q.filter(DeliveryZone.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def list_active(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DeliveryZone]:
        from sqlalchemy import select
        query = (
            select(DeliveryZone)
            .filter(
                DeliveryZone.tenant_id == tenant_id,
                DeliveryZone.is_active == True,  # noqa: E712
            )
            .order_by(DeliveryZone.department_code)
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_active(self, tenant_id: int) -> int:
        from sqlalchemy import select, func
        result = await self.db.execute(
            select(func.count())
            .select_from(DeliveryZone)
            .filter(
                DeliveryZone.tenant_id == tenant_id,
                DeliveryZone.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one()

    async def get_by_id(self, zone_id: int, tenant_id: int) -> Optional[DeliveryZone]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(DeliveryZone).filter(DeliveryZone.id == zone_id, DeliveryZone.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> DeliveryZone:
        obj = DeliveryZone(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: DeliveryZone, data: dict) -> DeliveryZone:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def soft_delete(self, obj: DeliveryZone) -> DeliveryZone:
        obj.is_active = False
        await self.db.flush()
        return obj
