"""Repository — TypePreparation + RecetteTypePreparation (restaurant, tenant_id=3)."""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.recette_type_preparation import RecetteTypePreparation
from app.models.restaurant.type_preparation import TypePreparation

_TENANT_RESTAURANT = 3
_DEFAULT_PER_PAGE = 20
_MAX_PER_PAGE = 100


class AsyncTypePreparationRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs) -> TypePreparation:
        obj = TypePreparation(tenant_id=_TENANT_RESTAURANT, **kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, tp_id: int) -> Optional[TypePreparation]:
        stmt = select(TypePreparation).where(
            TypePreparation.id == tp_id,
            TypePreparation.tenant_id == _TENANT_RESTAURANT,
            TypePreparation.is_active.is_(True),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_actives(
        self,
        page: int = 1,
        per_page: int = _DEFAULT_PER_PAGE,
    ) -> tuple[list[TypePreparation], int]:
        effective_per_page = min(per_page, _MAX_PER_PAGE)
        base = select(TypePreparation).where(
            TypePreparation.tenant_id == _TENANT_RESTAURANT,
            TypePreparation.is_active.is_(True),
        )
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0
        data_stmt = (
            base.order_by(TypePreparation.nom)
            .offset((page - 1) * effective_per_page)
            .limit(effective_per_page)
        )
        rows = await self.db.execute(data_stmt)
        return list(rows.scalars().all()), total


class AsyncRecetteTypePreparationRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs) -> RecetteTypePreparation:
        obj = RecetteTypePreparation(tenant_id=_TENANT_RESTAURANT, **kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, rec_id: int) -> Optional[RecetteTypePreparation]:
        stmt = select(RecetteTypePreparation).where(
            RecetteTypePreparation.id == rec_id,
            RecetteTypePreparation.tenant_id == _TENANT_RESTAURANT,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_type_preparation(
        self, tp_id: int
    ) -> list[RecetteTypePreparation]:
        stmt = select(RecetteTypePreparation).where(
            RecetteTypePreparation.type_preparation_id == tp_id,
            RecetteTypePreparation.tenant_id == _TENANT_RESTAURANT,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, rec_id: int) -> bool:
        obj = await self.get_by_id(rec_id)
        if obj is None:
            return False
        await self.db.delete(obj)
        await self.db.flush()
        return True
