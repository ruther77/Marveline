"""Service — IngredientRestaurant.

Statut 3-state : rupture (stock ≤ 0) | bas (0 < stock ≤ alerte) | ok (stock > alerte).
`derniere_entree` : date du dernier mouvement 'entree' (batch anti-N+1).
ADR-14 : stock_actuel lu directement DB, jamais depuis Redis.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.repositories.restaurant.ingredient import AsyncIngredientRepo
from app.schemas.restaurant.ingredient import (
    IngredientCreate,
    IngredientListResponse,
    IngredientResponse,
    IngredientUpdate,
)

_ZERO = Decimal("0")


def _compute_statut(stock_actuel: Decimal, stock_alerte: Decimal) -> str:
    """Calcule le statut 3-state : rupture | bas | ok."""
    if stock_actuel <= _ZERO:
        return "rupture"
    if stock_alerte > _ZERO and stock_actuel <= stock_alerte:
        return "bas"
    return "ok"


def _to_response(
    obj: IngredientRestaurant,
    derniere_entree: Optional[datetime] = None,
) -> IngredientResponse:
    """Construit IngredientResponse avec statut calculé (ADR-14)."""
    stock_actuel = Decimal(str(obj.stock_actuel))
    stock_alerte = Decimal(str(obj.stock_alerte))
    return IngredientResponse(
        id=obj.id,
        nom=obj.nom,
        image_url=obj.image_url,
        unite_stock=obj.unite_stock,
        stock_actuel=stock_actuel,
        stock_alerte=stock_alerte,
        cout_unitaire_cts=obj.cout_unitaire_cts or 0,
        statut=_compute_statut(stock_actuel, stock_alerte),
        derniere_entree=derniere_entree,
        categorie_id=obj.categorie_id,
        categorie=obj.categorie.nom if obj.categorie else None,
    )


class IngredientService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = AsyncIngredientRepo(db)

    async def create(self, payload: IngredientCreate) -> IngredientResponse:
        obj = await self._repo.create(
            nom=payload.nom,
            unite_stock=payload.unite_stock,
            stock_actuel=payload.stock_actuel,
            stock_alerte=payload.stock_alerte,
            categorie_id=payload.categorie_id,
            cout_unitaire_cts=payload.cout_unitaire_cts,
        )
        return _to_response(obj)

    async def get_by_id(self, ing_id: int) -> IngredientResponse:
        obj = await self._repo.get_by_id(ing_id)
        if obj is None:
            raise NotFound("IngredientRestaurant")
        # Single item : query dédiée pour derniere_entree
        entrees = await self._repo.get_dernieres_entrees_batch([obj.id])
        return _to_response(obj, derniere_entree=entrees.get(obj.id))

    async def update(self, ing_id: int, payload: IngredientUpdate) -> IngredientResponse:
        obj = await self._repo.get_by_id(ing_id)
        if obj is None:
            raise NotFound("IngredientRestaurant")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        entrees = await self._repo.get_dernieres_entrees_batch([obj.id])
        return _to_response(obj, derniere_entree=entrees.get(obj.id))

    async def list_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        categorie_id: int | None = None,
        statut: str | None = None,
    ) -> IngredientListResponse:
        items, total = await self._repo.list_paginated(
            page, per_page, search, categorie_id, statut,
        )
        # Batch anti-N+1 : derniere_entree pour tous les ingrédients de la page
        ing_ids = [i.id for i in items]
        entrees = await self._repo.get_dernieres_entrees_batch(ing_ids)
        ruptures_count = await self._repo.count_ruptures()
        return IngredientListResponse(
            items=[_to_response(i, derniere_entree=entrees.get(i.id)) for i in items],
            total=total,
            page=page,
            per_page=per_page,
            ruptures_count=ruptures_count,
        )

    async def delete(self, ing_id: int) -> None:
        """Soft-delete d'un ingrédient (is_active = False)."""
        deleted = await self._repo.soft_delete(ing_id)
        if not deleted:
            raise NotFound("IngredientRestaurant")

    async def list_epuises(self) -> list[IngredientResponse]:
        items = await self._repo.list_epuises()
        ing_ids = [i.id for i in items]
        entrees = await self._repo.get_dernieres_entrees_batch(ing_ids)
        return [_to_response(i, derniere_entree=entrees.get(i.id)) for i in items]
