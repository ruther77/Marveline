"""Repository FinanceEntity — CRUD entités finance."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance.entity import FinanceEntity


class AsyncFinanceEntityRepository:
    """Repository async pour FinanceEntity (référentiel global, sans tenant)."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, entity_id: int) -> Optional[FinanceEntity]:
        result = await self._db.execute(
            select(FinanceEntity).where(FinanceEntity.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[FinanceEntity]:
        result = await self._db.execute(
            select(FinanceEntity).where(FinanceEntity.code == code)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[FinanceEntity]:
        result = await self._db.execute(
            select(FinanceEntity).order_by(FinanceEntity.id)
        )
        return list(result.scalars().all())

    async def create(
        self,
        nom: str,
        type: str,
        code: Optional[str] = None,
        description: Optional[str] = None,
    ) -> FinanceEntity:
        entity = FinanceEntity(nom=nom, type=type, code=code, description=description)
        self._db.add(entity)
        await self._db.flush()
        return entity
