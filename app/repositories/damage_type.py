"""Repository pour DamageType."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.damage_type import DamageType
from app.repositories.base import BaseRepository


class DamageTypeRepository(BaseRepository[DamageType]):
    """Repository types de dommages avec isolation multi-tenant."""

    def __init__(self, db: Session):
        super().__init__(db, DamageType)

    def get_by_name(self, name: str, tenant_id: int) -> Optional[DamageType]:
        """Récupère un type de dommage par son nom."""
        query = select(DamageType).filter(
            DamageType.name == name,
            DamageType.tenant_id == tenant_id,
            DamageType.is_active == True,  # noqa: E712
        )
        return self.db.execute(query).scalar_one_or_none()

    def name_exists(
        self, name: str, tenant_id: int, exclude_id: Optional[int] = None
    ) -> bool:
        """Vérifie si un nom existe déjà pour ce tenant."""
        query = select(DamageType).filter(
            DamageType.name == name,
            DamageType.tenant_id == tenant_id,
            DamageType.is_active == True,  # noqa: E712
        )
        if exclude_id:
            query = query.filter(DamageType.id != exclude_id)
        return self.db.execute(query).scalar_one_or_none() is not None

    def list_active(self, tenant_id: int) -> list[DamageType]:
        """Liste tous les types actifs d'un tenant, triés par nom."""
        query = (
            select(DamageType)
            .filter(
                DamageType.tenant_id == tenant_id,
                DamageType.is_active == True,  # noqa: E712
            )
            .order_by(DamageType.name)
        )
        return list(self.db.execute(query).scalars().all())


class AsyncDamageTypeRepository:
    """Version async de DamageTypeRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        from typing import Optional
        self.db: AsyncSession = db

    async def get_by_name(self, name: str, tenant_id: int) -> Optional[DamageType]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(DamageType).filter(DamageType.name == name, DamageType.tenant_id == tenant_id, DamageType.is_active == True)  # noqa: E712
        )
        return result.scalar_one_or_none()

    async def name_exists(self, name: str, tenant_id: int, exclude_id: Optional[int] = None) -> bool:
        from sqlalchemy import select
        q = select(DamageType).filter(DamageType.name == name, DamageType.tenant_id == tenant_id, DamageType.is_active == True)  # noqa: E712
        if exclude_id:
            q = q.filter(DamageType.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def list_active(self, tenant_id: int) -> list[DamageType]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(DamageType).filter(DamageType.tenant_id == tenant_id, DamageType.is_active == True).order_by(DamageType.name)  # noqa: E712
        )
        return list(result.scalars().all())

    async def get_by_id(self, dt_id: int, tenant_id: int) -> Optional[DamageType]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(DamageType).filter(DamageType.id == dt_id, DamageType.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> DamageType:
        obj = DamageType(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: DamageType, data: dict) -> DamageType:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def soft_delete(self, obj: DamageType) -> DamageType:
        obj.is_active = False
        await self.db.flush()
        return obj
