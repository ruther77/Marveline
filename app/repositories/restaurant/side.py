"""Repository — SideRestaurant (restaurant, tenant_id=3)."""
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.side_restaurant import SideRestaurant
from app.models.restaurant.variante_side import VarianteSide

_TENANT_RESTAURANT = 3


class AsyncSideRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs) -> SideRestaurant:
        obj = SideRestaurant(tenant_id=_TENANT_RESTAURANT, **kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, side_id: int, *, include_inactive: bool = False) -> Optional[SideRestaurant]:
        stmt = select(SideRestaurant).where(
            SideRestaurant.id == side_id,
            SideRestaurant.tenant_id == _TENANT_RESTAURANT,
        )
        if not include_inactive:
            stmt = stmt.where(SideRestaurant.is_active.is_(True))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_actives(self) -> list[SideRestaurant]:
        return await self.list_all(actifs_seulement=True)

    async def list_all(self, actifs_seulement: bool = False) -> list[SideRestaurant]:
        stmt = (
            select(SideRestaurant)
            .where(SideRestaurant.tenant_id == _TENANT_RESTAURANT)
            .order_by(SideRestaurant.nom)
        )
        if actifs_seulement:
            stmt = stmt.where(SideRestaurant.is_active.is_(True))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, side_id: int, **kwargs) -> Optional[SideRestaurant]:
        obj = await self.get_by_id(side_id, include_inactive=True)
        if obj is None:
            return None
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def count_plats_par_side(self, side_ids: list[int]) -> dict[int, int]:
        """Compte le nombre de plats liés à chaque side."""
        if not side_ids:
            return {}
        stmt = (
            select(VarianteSide.side_id, func.count(VarianteSide.id))
            .where(VarianteSide.side_id.in_(side_ids), VarianteSide.is_active.is_(True))
            .group_by(VarianteSide.side_id)
        )
        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
