"""Repository — AlerteStockRestaurant (restaurant, tenant_id=3)."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.alerte_stock_restaurant import AlerteStockRestaurant

_TENANT_RESTAURANT = 3


class AsyncAlerteStockRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        entite_type: str,
        entite_id: int,
        seuil_type: str,
    ) -> AlerteStockRestaurant:
        obj = AlerteStockRestaurant(
            tenant_id=_TENANT_RESTAURANT,
            entite_type=entite_type,
            entite_id=entite_id,
            seuil_type=seuil_type,
        )
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_active_by_entite(
        self, entite_type: str, entite_id: int
    ) -> Optional[AlerteStockRestaurant]:
        """Retourne l'alerte active (non résolue) pour une entité, ou None."""
        stmt = select(AlerteStockRestaurant).where(
            AlerteStockRestaurant.tenant_id == _TENANT_RESTAURANT,
            AlerteStockRestaurant.entite_type == entite_type,
            AlerteStockRestaurant.entite_id == entite_id,
            AlerteStockRestaurant.resolu_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_actives(self) -> list[AlerteStockRestaurant]:
        stmt = (
            select(AlerteStockRestaurant)
            .where(
                AlerteStockRestaurant.tenant_id == _TENANT_RESTAURANT,
                AlerteStockRestaurant.resolu_at.is_(None),
            )
            .order_by(AlerteStockRestaurant.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def resoudre(
        self,
        alerte_id: int,
        resolu_by_id: Optional[int] = None,
    ) -> bool:
        stmt = select(AlerteStockRestaurant).where(
            AlerteStockRestaurant.id == alerte_id,
            AlerteStockRestaurant.tenant_id == _TENANT_RESTAURANT,
        )
        result = await self.db.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            return False
        obj.resolu_at = datetime.now(tz=timezone.utc)
        obj.resolu_by_id = resolu_by_id
        await self.db.flush()
        return True

    async def resoudre_by_entite(
        self,
        entite_type: str,
        entite_id: int,
        resolu_by_id: Optional[int] = None,
    ) -> bool:
        """Résout l'alerte active d'une entité (après réapprovisionnement)."""
        obj = await self.get_active_by_entite(entite_type, entite_id)
        if obj is None:
            return False
        obj.resolu_at = datetime.now(tz=timezone.utc)
        obj.resolu_by_id = resolu_by_id
        await self.db.flush()
        return True

    async def count_actives(self) -> int:
        stmt = select(func.count()).where(
            AlerteStockRestaurant.tenant_id == _TENANT_RESTAURANT,
            AlerteStockRestaurant.resolu_at.is_(None),
        )
        return (await self.db.execute(stmt)).scalar() or 0
