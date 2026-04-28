"""Service — TypePreparation + stock requis (restaurant).

`stock_requis` : calcule si le stock disponible est suffisant pour lancer
un batch complet (ADR-14 — lecture directe DB).
"""
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.repositories.restaurant.ingredient import AsyncIngredientRepo
from app.repositories.restaurant.type_preparation import (
    AsyncRecetteTypePreparationRepo,
    AsyncTypePreparationRepo,
)
from app.schemas.restaurant.type_preparation import (
    IngredientRequisResponse,
    RecetteLigneCreate,
    RecetteLigneResponse,
    StockRequisResponse,
    TypePreparationCreate,
    TypePreparationResponse,
    TypePreparationUpdate,
)


class TypePreparationService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = AsyncTypePreparationRepo(db)
        self._recette_repo = AsyncRecetteTypePreparationRepo(db)
        self._ing_repo = AsyncIngredientRepo(db)

    async def create(self, payload: TypePreparationCreate) -> TypePreparationResponse:
        obj = await self._repo.create(
            nom=payload.nom,
            portions_par_batch=payload.portions_par_batch,
            notes=payload.notes,
        )
        return TypePreparationResponse.model_validate(obj)

    async def get_by_id(self, tp_id: int) -> TypePreparationResponse:
        obj = await self._repo.get_by_id(tp_id)
        if obj is None:
            raise NotFound("TypePreparation")
        return TypePreparationResponse.model_validate(obj)

    async def list_actives(
        self, page: int = 1, per_page: int = 20
    ) -> tuple[list[TypePreparationResponse], int]:
        items, total = await self._repo.list_actives(page, per_page)
        return [TypePreparationResponse.model_validate(i) for i in items], total

    async def update(self, tp_id: int, payload: TypePreparationUpdate) -> TypePreparationResponse:
        obj = await self._repo.get_by_id(tp_id)
        if obj is None:
            raise NotFound("TypePreparation")
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(obj, key, value)
        await self._repo.db.flush()
        await self._repo.db.refresh(obj)
        return TypePreparationResponse.model_validate(obj)

    async def soft_delete(self, tp_id: int) -> None:
        obj = await self._repo.get_by_id(tp_id)
        if obj is None:
            raise NotFound("TypePreparation")
        obj.is_active = False
        await self._repo.db.flush()

    async def add_recette_ligne(
        self, tp_id: int, payload: RecetteLigneCreate,
    ) -> RecetteLigneResponse:
        tp = await self._repo.get_by_id(tp_id)
        if tp is None:
            raise NotFound("TypePreparation")
        ing = await self._ing_repo.get_by_id(payload.ingredient_id)
        if ing is None:
            raise NotFound("Ingredient")
        rec = await self._recette_repo.create(
            type_preparation_id=tp_id,
            ingredient_id=payload.ingredient_id,
            quantite_par_batch=payload.quantite_par_batch,
            notes=payload.notes,
        )
        return RecetteLigneResponse(
            id=rec.id,
            ingredient_id=rec.ingredient_id,
            nom=ing.nom,
            quantite_par_batch=rec.quantite_par_batch,
            unite=ing.unite_stock,
            notes=rec.notes,
        )

    async def remove_recette_ligne(self, tp_id: int, ligne_id: int) -> None:
        rec = await self._recette_repo.get_by_id(ligne_id)
        if rec is None or rec.type_preparation_id != tp_id:
            raise NotFound("RecetteLigne")
        await self._recette_repo.delete(ligne_id)

    async def list_recette(self, tp_id: int) -> list[RecetteLigneResponse]:
        tp = await self._repo.get_by_id(tp_id)
        if tp is None:
            raise NotFound("TypePreparation")
        recettes = await self._recette_repo.list_by_type_preparation(tp_id)
        result: list[RecetteLigneResponse] = []
        for rec in recettes:
            ing = await self._ing_repo.get_by_id(rec.ingredient_id)
            if ing is None:
                continue
            result.append(RecetteLigneResponse(
                id=rec.id,
                ingredient_id=rec.ingredient_id,
                nom=ing.nom,
                quantite_par_batch=rec.quantite_par_batch,
                unite=ing.unite_stock,
                notes=rec.notes,
            ))
        return result

    async def get_stock_requis(self, tp_id: int) -> StockRequisResponse:
        """Calcule l'état du stock pour chaque ingrédient requis par un batch (ADR-14)."""
        tp = await self._repo.get_by_id(tp_id)
        if tp is None:
            raise NotFound("TypePreparation")
        recettes = await self._recette_repo.list_by_type_preparation(tp_id)
        ingredients_requis: list[IngredientRequisResponse] = []
        for rec in recettes:
            ing = await self._ing_repo.get_by_id(rec.ingredient_id)
            if ing is None:
                continue
            stock_actuel = Decimal(str(ing.stock_actuel))
            quantite_par_batch = Decimal(str(rec.quantite_par_batch))
            suffisant = stock_actuel >= quantite_par_batch
            ingredients_requis.append(
                IngredientRequisResponse(
                    ingredient_id=ing.id,
                    nom=ing.nom,
                    quantite_par_batch=quantite_par_batch,
                    unite=ing.unite_stock,
                    stock_actuel=stock_actuel,
                    suffisant=suffisant,
                )
            )
        return StockRequisResponse(
            type_preparation_id=tp.id,
            nom=tp.nom,
            portions_par_batch=tp.portions_par_batch,
            ingredients_requis=ingredients_requis,
        )
