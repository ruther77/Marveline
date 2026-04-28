"""Repository pour Supplier."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.supplier import Supplier
from app.repositories.base import BaseRepository


class SupplierRepository(BaseRepository[Supplier]):
    """Repository fournisseurs avec isolation multi-tenant."""

    def __init__(self, db: Session):
        super().__init__(db, Supplier)

    def list_active(self, tenant_id: int) -> list[Supplier]:
        """Liste tous les fournisseurs actifs d'un tenant, triés par nom."""
        query = (
            select(Supplier)
            .filter(
                Supplier.tenant_id == tenant_id,
                Supplier.is_active == True,  # noqa: E712
            )
            .order_by(Supplier.name)
        )
        return list(self.db.execute(query).scalars().all())

    def name_exists(
        self, name: str, tenant_id: int, exclude_id: Optional[int] = None
    ) -> bool:
        """Vérifie si un nom de fournisseur existe déjà pour ce tenant."""
        query = select(Supplier).filter(
            Supplier.name == name,
            Supplier.tenant_id == tenant_id,
            Supplier.is_active == True,  # noqa: E712
        )
        if exclude_id:
            query = query.filter(Supplier.id != exclude_id)
        return self.db.execute(query).scalar_one_or_none() is not None


class AsyncSupplierRepository:
    """Version async de SupplierRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get_by_id(self, supplier_id: int, tenant_id: int):
        from sqlalchemy import select
        from app.models.supplier import Supplier
        result = await self.db.execute(
            select(Supplier).filter(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def list_active(self, tenant_id: int) -> list:
        from sqlalchemy import select
        from app.models.supplier import Supplier
        result = await self.db.execute(
            select(Supplier)
            .filter(Supplier.tenant_id == tenant_id, Supplier.is_active == True)  # noqa: E712
            .order_by(Supplier.name)
        )
        return list(result.scalars().all())

    async def name_exists(self, name: str, tenant_id: int, exclude_id=None) -> bool:
        from sqlalchemy import select
        from app.models.supplier import Supplier
        q = select(Supplier).filter(
            Supplier.name == name,
            Supplier.tenant_id == tenant_id,
            Supplier.is_active == True,  # noqa: E712
        )
        if exclude_id:
            q = q.filter(Supplier.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def create(self, data: dict):
        from app.models.supplier import Supplier
        obj = Supplier(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj, data: dict):
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def soft_delete(self, obj) -> None:
        obj.is_active = False
        await self.db.flush()
