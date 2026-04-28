"""Repository — InstancePreparation (restaurant, tenant_id=3).

ADR-14 : `portions_restantes` lu directement DB — get_by_id_lock utilise
SELECT FOR UPDATE pour les décréments atomiques (POST /lignes).
"""
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.instance_preparation import InstancePreparation

_TENANT_RESTAURANT = 3
_DEFAULT_PER_PAGE = 20
_MAX_PER_PAGE = 100


class AsyncInstancePreparationRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs) -> InstancePreparation:
        obj = InstancePreparation(tenant_id=_TENANT_RESTAURANT, **kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, inst_id: int) -> Optional[InstancePreparation]:
        stmt = select(InstancePreparation).where(
            InstancePreparation.id == inst_id,
            InstancePreparation.tenant_id == _TENANT_RESTAURANT,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_lock(self, inst_id: int) -> Optional[InstancePreparation]:
        """SELECT FOR UPDATE — pour décrément atomique portions_restantes (ADR-14)."""
        stmt = (
            select(InstancePreparation)
            .where(
                InstancePreparation.id == inst_id,
                InstancePreparation.tenant_id == _TENANT_RESTAURANT,
            )
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_date(
        self,
        date_cuisine: date,
        page: int = 1,
        per_page: int = _DEFAULT_PER_PAGE,
    ) -> tuple[list[InstancePreparation], int]:
        effective_per_page = min(per_page, _MAX_PER_PAGE)
        base = select(InstancePreparation).where(
            InstancePreparation.tenant_id == _TENANT_RESTAURANT,
            InstancePreparation.date_cuisine == date_cuisine,
        )
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0
        data_stmt = (
            base.order_by(InstancePreparation.created_at)
            .offset((page - 1) * effective_per_page)
            .limit(effective_per_page)
        )
        rows = await self.db.execute(data_stmt)
        return list(rows.scalars().all()), total

    async def list_vides_today(self, date_cuisine: date) -> list[InstancePreparation]:
        """Instances épuisées aujourd'hui (portions_restantes = 0) — dashboard ruptures."""
        stmt = select(InstancePreparation).where(
            InstancePreparation.tenant_id == _TENANT_RESTAURANT,
            InstancePreparation.date_cuisine == date_cuisine,
            InstancePreparation.portions_restantes == 0,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_actives_today(self, date_cuisine: date) -> int:
        """Nombre de marmites avec portions_restantes > 0 aujourd'hui (stats dashboard)."""
        stmt = select(func.count()).where(
            InstancePreparation.tenant_id == _TENANT_RESTAURANT,
            InstancePreparation.date_cuisine == date_cuisine,
            InstancePreparation.portions_restantes > 0,
        )
        return (await self.db.execute(stmt)).scalar() or 0
