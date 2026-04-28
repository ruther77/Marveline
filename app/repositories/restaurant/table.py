"""Repository — TableRestaurant (restaurant, tenant_id=3).

Le statut (LIBRE/OCCUPEE/SERVIE) est calculé côté service — pas stocké.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.table_restaurant import TableRestaurant

_TENANT_RESTAURANT = 3


class AsyncTableRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs) -> TableRestaurant:
        obj = TableRestaurant(tenant_id=_TENANT_RESTAURANT, **kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, table_id: int) -> Optional[TableRestaurant]:
        stmt = select(TableRestaurant).where(
            TableRestaurant.id == table_id,
            TableRestaurant.tenant_id == _TENANT_RESTAURANT,
            TableRestaurant.is_active.is_(True),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_actives(self) -> list[TableRestaurant]:
        stmt = (
            select(TableRestaurant)
            .where(
                TableRestaurant.tenant_id == _TENANT_RESTAURANT,
                TableRestaurant.is_active.is_(True),
            )
            .order_by(TableRestaurant.numero)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
