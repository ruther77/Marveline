"""Repository — CategorieIngredient (restaurant, tenant_id=3)."""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.categorie_ingredient import CategorieIngredient
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant

_TENANT_RESTAURANT = 3


class AsyncCategorieIngredientRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, nom: str, image_url: Optional[str] = None, is_proteine: bool = False) -> CategorieIngredient:
        obj = CategorieIngredient(
            nom=nom,
            image_url=image_url,
            is_proteine=is_proteine,
            tenant_id=_TENANT_RESTAURANT,
        )
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, cat_id: int) -> Optional[CategorieIngredient]:
        stmt = select(CategorieIngredient).where(
            CategorieIngredient.id == cat_id,
            CategorieIngredient.tenant_id == _TENANT_RESTAURANT,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, cat_id: int, changes: dict) -> Optional[CategorieIngredient]:
        obj = await self.get_by_id(cat_id)
        if obj is None:
            return None
        for key, value in changes.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, cat_id: int) -> bool:
        obj = await self.get_by_id(cat_id)
        if obj is None:
            return False
        await self.db.delete(obj)
        await self.db.flush()
        return True

    async def count_usages(self, cat_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(IngredientRestaurant)
            .where(
                IngredientRestaurant.categorie_id == cat_id,
                IngredientRestaurant.tenant_id == _TENANT_RESTAURANT,
                IngredientRestaurant.is_active.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def list_all(self) -> list[CategorieIngredient]:
        stmt = (
            select(CategorieIngredient)
            .where(CategorieIngredient.tenant_id == _TENANT_RESTAURANT)
            .order_by(CategorieIngredient.nom)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
