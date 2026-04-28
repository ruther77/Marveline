"""Service — MouvementStockRestaurant.

Règle de signe (quantite body toujours positive) :
  - entree, transfert_entrant : delta = +quantite
  - consommation, perte       : delta = -quantite
  - inventaire                : quantite = nouveau stock cible, delta calculé

ADR-14 : SELECT FOR UPDATE sur ingredient avant tout UPDATE stock.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.repositories.restaurant.alerte_stock import AsyncAlerteStockRepo
from app.repositories.restaurant.ingredient import AsyncIngredientRepo
from app.repositories.restaurant.mouvement_stock import AsyncMouvementStockRepo
from app.schemas.restaurant.mouvement_stock import (
    MouvementStockCreate,
    MouvementStockCreateSimple,
    MouvementStockListResponse,
    MouvementStockResponse,
)

_ZERO = Decimal("0")

_SIGNES_POSITIFS = frozenset({"entree", "transfert_entrant"})
_SIGNES_NEGATIFS = frozenset({"consommation", "perte"})


def _appliquer_signe(type_mouvement: str, quantite: Decimal, stock_actuel: Decimal) -> Decimal:
    """Retourne le delta signé à appliquer sur stock_actuel."""
    if type_mouvement in _SIGNES_POSITIFS:
        return quantite
    if type_mouvement in _SIGNES_NEGATIFS:
        return -quantite
    # inventaire : quantite = stock cible, delta = cible - actuel
    return quantite - stock_actuel


class MouvementStockService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AsyncMouvementStockRepo(db)
        self._ing_repo = AsyncIngredientRepo(db)
        self._alerte_repo = AsyncAlerteStockRepo(db)

    async def create(
        self,
        payload: MouvementStockCreate,
        created_by_id: Optional[int] = None,
    ) -> Optional[MouvementStockResponse]:
        # SELECT FOR UPDATE — atomicité ADR-14
        ing = await self._ing_repo.get_by_id_lock(payload.ingredient_id)
        if ing is None:
            raise NotFound("IngredientRestaurant")

        stock_actuel = Decimal(str(ing.stock_actuel))
        delta = _appliquer_signe(payload.type_mouvement, payload.quantite, stock_actuel)
        # inventaire : stock cible == stock actuel → aucun mouvement à enregistrer
        if payload.type_mouvement == "inventaire" and delta == _ZERO:
            return None
        nouveau_stock = stock_actuel + delta

        ing.stock_actuel = nouveau_stock
        mouv = await self._repo.create(
            ingredient_id=payload.ingredient_id,
            type_mouvement=payload.type_mouvement,
            quantite=delta,
            stock_apres=nouveau_stock,
            date_mouvement=payload.date_mouvement,
            notes=payload.notes,
            created_by_id=created_by_id,
        )

        await self._gerer_alertes(ing.id, nouveau_stock, Decimal(str(ing.stock_alerte)))
        # Enrichir la réponse avec ingredient_nom + created_by_name
        enriched = await self._repo.get_enriched(mouv.id)
        if enriched is not None:
            return MouvementStockResponse(**enriched)
        return MouvementStockResponse.model_validate(mouv)

    async def _gerer_alertes(
        self,
        ing_id: int,
        nouveau_stock: Decimal,
        stock_alerte: Decimal,
    ) -> None:
        """Crée ou résout une alerte stock selon le nouveau niveau (ADR-14)."""
        if nouveau_stock <= _ZERO:
            alerte = await self._alerte_repo.get_active_by_entite("ingredient", ing_id)
            if alerte is None:
                await self._alerte_repo.create("ingredient", ing_id, "zero")
        elif stock_alerte > _ZERO and nouveau_stock <= stock_alerte:
            alerte = await self._alerte_repo.get_active_by_entite("ingredient", ing_id)
            if alerte is None:
                await self._alerte_repo.create("ingredient", ing_id, "bas")
        else:
            await self._alerte_repo.resoudre_by_entite("ingredient", ing_id)

    async def create_for_ingredient(
        self,
        ingredient_id: int,
        payload: MouvementStockCreateSimple,
        created_by_id: Optional[int] = None,
    ) -> Optional[MouvementStockResponse]:
        """Crée un mouvement simplifié (date_mouvement=now, ingredient_id du path)."""
        full = MouvementStockCreate(
            ingredient_id=ingredient_id,
            type_mouvement=payload.type_mouvement,
            quantite=payload.quantite,
            date_mouvement=datetime.now(timezone.utc),
            notes=payload.notes,
        )
        return await self.create(full, created_by_id=created_by_id)

    async def list_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        ingredient_id: Optional[int] = None,
        type_mouvement: Optional[str] = None,
        date_debut: Optional[datetime] = None,
        date_fin: Optional[datetime] = None,
    ) -> MouvementStockListResponse:
        items, total = await self._repo.list_paginated(
            page, per_page, ingredient_id, type_mouvement, date_debut, date_fin
        )
        return MouvementStockListResponse(
            items=[MouvementStockResponse(**d) for d in items],
            total=total,
            page=page,
            per_page=per_page,
        )
