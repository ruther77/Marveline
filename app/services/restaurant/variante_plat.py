"""Service — VariantePlat restaurant.

Enrichit les réponses avec les noms des relations (base, protéine) via batch query.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.models.restaurant.type_preparation import TypePreparation
from app.models.restaurant.variante_plat import VariantePlat
from app.repositories.restaurant.variante_plat import AsyncVariantePlatRepo
from app.schemas.restaurant.variante_plat import (
    VariantePlatCreate,
    VariantePlatResponse,
    VariantePlatUpdate,
)


class VariantePlatService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AsyncVariantePlatRepo(db)

    async def _enrich(self, items: list[VariantePlat]) -> list[VariantePlatResponse]:
        """Enrichit une liste de VariantePlat avec type_preparation_nom et ingredient_proteine_nom."""
        tp_ids = {i.type_preparation_id for i in items if i.type_preparation_id}
        ing_ids = {i.ingredient_proteine_id for i in items if i.ingredient_proteine_id}

        tp_map: dict[int, str] = {}
        if tp_ids:
            stmt = select(TypePreparation.id, TypePreparation.nom).where(TypePreparation.id.in_(tp_ids))
            rows = await self._db.execute(stmt)
            tp_map = {r.id: r.nom for r in rows.all()}

        ing_map: dict[int, str] = {}
        if ing_ids:
            stmt = select(IngredientRestaurant.id, IngredientRestaurant.nom).where(IngredientRestaurant.id.in_(ing_ids))
            rows = await self._db.execute(stmt)
            ing_map = {r.id: r.nom for r in rows.all()}

        result = []
        for obj in items:
            resp = VariantePlatResponse.model_validate(obj)
            resp.type_preparation_nom = tp_map.get(obj.type_preparation_id) if obj.type_preparation_id else None
            resp.ingredient_proteine_nom = ing_map.get(obj.ingredient_proteine_id) if obj.ingredient_proteine_id else None
            result.append(resp)
        return result

    async def _enrich_one(self, obj: VariantePlat) -> VariantePlatResponse:
        enriched = await self._enrich([obj])
        return enriched[0]

    async def create(self, payload: VariantePlatCreate) -> VariantePlatResponse:
        obj = await self._repo.create(**payload.model_dump())
        return await self._enrich_one(obj)

    async def get_by_id(self, var_id: int) -> VariantePlatResponse:
        obj = await self._repo.get_by_id(var_id)
        if obj is None:
            raise NotFound("VariantePlat")
        return await self._enrich_one(obj)

    async def update(self, var_id: int, payload: VariantePlatUpdate) -> VariantePlatResponse:
        obj = await self._repo.update(var_id, **payload.model_dump(exclude_unset=True))
        if obj is None:
            raise NotFound("VariantePlat")
        return await self._enrich_one(obj)

    async def list_actives(
        self, type_filtre: str | None = None
    ) -> list[VariantePlatResponse]:
        items = await self._repo.list_actives(type_filtre)
        return await self._enrich(items)

    async def list_all(
        self,
        type_filtre: str | None = None,
        actifs_seulement: bool = False,
    ) -> list[VariantePlatResponse]:
        items = await self._repo.list_all(type_filtre, actifs_seulement)
        return await self._enrich(items)
