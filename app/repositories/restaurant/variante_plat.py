"""Repository — VariantePlat (restaurant, tenant_id=3)."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.variante_plat import VariantePlat

_TENANT_RESTAURANT = 3


class AsyncVariantePlatRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs) -> VariantePlat:
        obj = VariantePlat(tenant_id=_TENANT_RESTAURANT, **kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(
        self, var_id: int, *, include_inactive: bool = False
    ) -> Optional[VariantePlat]:
        stmt = select(VariantePlat).where(
            VariantePlat.id == var_id,
            VariantePlat.tenant_id == _TENANT_RESTAURANT,
        )
        if not include_inactive:
            stmt = stmt.where(VariantePlat.is_active.is_(True))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_actives(
        self, type_filtre: Optional[str] = None
    ) -> list[VariantePlat]:
        return await self.list_all(type_filtre=type_filtre, actifs_seulement=True)

    async def list_all(
        self,
        type_filtre: Optional[str] = None,
        actifs_seulement: bool = False,
    ) -> list[VariantePlat]:
        stmt = select(VariantePlat).where(
            VariantePlat.tenant_id == _TENANT_RESTAURANT,
        )
        if actifs_seulement:
            stmt = stmt.where(VariantePlat.is_active.is_(True))
        if type_filtre is not None:
            stmt = stmt.where(VariantePlat.type == type_filtre)
        stmt = stmt.order_by(VariantePlat.nom)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, var_id: int, **kwargs) -> Optional[VariantePlat]:
        obj = await self.get_by_id(var_id, include_inactive=True)
        if obj is None:
            return None
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj
