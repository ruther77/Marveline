"""Service — SideRestaurant (accompagnements).

Enrichit les réponses avec ingredient_nom et nb_plats_lies.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.models.restaurant.side_restaurant import SideRestaurant
from app.repositories.restaurant.side import AsyncSideRepo
from app.schemas.restaurant.side import SideCreate, SideResponse, SideUpdate


class SideService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AsyncSideRepo(db)

    async def _enrich(self, items: list[SideRestaurant]) -> list[SideResponse]:
        ing_ids = {i.ingredient_id for i in items if i.ingredient_id}
        ing_map: dict[int, str] = {}
        if ing_ids:
            stmt = select(IngredientRestaurant.id, IngredientRestaurant.nom).where(
                IngredientRestaurant.id.in_(ing_ids)
            )
            rows = await self._db.execute(stmt)
            ing_map = {r.id: r.nom for r in rows.all()}

        side_ids = [i.id for i in items]
        plats_count = await self._repo.count_plats_par_side(side_ids)

        result = []
        for obj in items:
            resp = SideResponse.model_validate(obj)
            resp.ingredient_nom = ing_map.get(obj.ingredient_id) if obj.ingredient_id else None
            resp.nb_plats_lies = plats_count.get(obj.id, 0)
            result.append(resp)
        return result

    async def create(self, payload: SideCreate) -> SideResponse:
        obj = await self._repo.create(**payload.model_dump())
        enriched = await self._enrich([obj])
        return enriched[0]

    async def update(self, side_id: int, payload: SideUpdate) -> SideResponse:
        obj = await self._repo.update(side_id, **payload.model_dump(exclude_unset=True))
        if obj is None:
            raise NotFound("SideRestaurant")
        enriched = await self._enrich([obj])
        return enriched[0]

    async def get_by_id(self, side_id: int) -> SideResponse:
        obj = await self._repo.get_by_id(side_id)
        if obj is None:
            raise NotFound("SideRestaurant")
        enriched = await self._enrich([obj])
        return enriched[0]

    async def list_actives(self) -> list[SideResponse]:
        items = await self._repo.list_actives()
        return await self._enrich(items)

    async def list_all(self) -> list[SideResponse]:
        items = await self._repo.list_all()
        return await self._enrich(items)
