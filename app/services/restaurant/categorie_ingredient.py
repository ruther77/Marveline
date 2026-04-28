"""Service — CategorieIngredient restaurant."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.repositories.restaurant.categorie_ingredient import AsyncCategorieIngredientRepo
from app.schemas.restaurant.categorie_ingredient import (
    CategorieIngredientCreate,
    CategorieIngredientResponse,
    CategorieIngredientUpdate,
)


class CategorieIngredientService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = AsyncCategorieIngredientRepo(db)

    async def create(
        self, payload: CategorieIngredientCreate
    ) -> CategorieIngredientResponse:
        obj = await self._repo.create(
            nom=payload.nom,
            image_url=payload.image_url,
            is_proteine=payload.is_proteine,
        )
        return CategorieIngredientResponse.model_validate(obj)

    async def get_by_id(self, cat_id: int) -> CategorieIngredientResponse:
        obj = await self._repo.get_by_id(cat_id)
        if obj is None:
            raise NotFound("CategorieIngredient")
        return CategorieIngredientResponse.model_validate(obj)

    async def update(
        self, cat_id: int, payload: CategorieIngredientUpdate
    ) -> CategorieIngredientResponse:
        changes = payload.model_dump(exclude_unset=True)
        obj = await self._repo.update(cat_id, changes)
        if obj is None:
            raise NotFound("CategorieIngredient")
        return CategorieIngredientResponse.model_validate(obj)

    async def delete(self, cat_id: int) -> None:
        found = await self._repo.delete(cat_id)
        if not found:
            raise NotFound("CategorieIngredient")

    async def count_usages(self, cat_id: int) -> int:
        await self.get_by_id(cat_id)
        return await self._repo.count_usages(cat_id)

    async def list_all(self) -> list[CategorieIngredientResponse]:
        items = await self._repo.list_all()
        return [CategorieIngredientResponse.model_validate(i) for i in items]
