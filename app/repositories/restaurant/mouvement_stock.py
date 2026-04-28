"""Repository — MouvementStockRestaurant (tenant_id=3).

LEFT JOIN ingredient (nom) + account (created_by_name) pour réponse enrichie.
"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.account import Account
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.models.restaurant.mouvement_stock_restaurant import MouvementStockRestaurant

_TENANT_RESTAURANT = 3
_DEFAULT_PER_PAGE = 20
_MAX_PER_PAGE = 100


class AsyncMouvementStockRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs) -> MouvementStockRestaurant:
        obj = MouvementStockRestaurant(tenant_id=_TENANT_RESTAURANT, **kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    def _enriched_select(self):
        """SELECT avec LEFT JOIN ingredient_nom + created_by_name."""
        ing = aliased(IngredientRestaurant)
        acc = aliased(Account)
        return (
            select(
                MouvementStockRestaurant,
                ing.nom.label("ingredient_nom"),
                ing.unite_stock.label("ingredient_unite"),
                (acc.first_name + " " + acc.last_name).label("created_by_name"),
            )
            .outerjoin(ing, MouvementStockRestaurant.ingredient_id == ing.id)
            .outerjoin(acc, MouvementStockRestaurant.created_by_id == acc.id)
        )

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        """Convertit une row (ORM + labels) en dict pour MouvementStockResponse."""
        mouv = row[0]
        return {
            "id": mouv.id,
            "tenant_id": mouv.tenant_id,
            "ingredient_id": mouv.ingredient_id,
            "ingredient_nom": row.ingredient_nom or "",
            "ingredient_unite": row.ingredient_unite or "",
            "type_mouvement": mouv.type_mouvement,
            "quantite": mouv.quantite,
            "stock_apres": mouv.stock_apres,
            "date_mouvement": mouv.date_mouvement,
            "notes": mouv.notes,
            "created_by_name": row.created_by_name,
            "created_at": mouv.created_at,
        }

    async def list_paginated(
        self,
        page: int = 1,
        per_page: int = _DEFAULT_PER_PAGE,
        ingredient_id: Optional[int] = None,
        type_mouvement: Optional[str] = None,
        date_debut: Optional[datetime] = None,
        date_fin: Optional[datetime] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        effective_per_page = min(per_page, _MAX_PER_PAGE)
        base_where = [MouvementStockRestaurant.tenant_id == _TENANT_RESTAURANT]
        if ingredient_id is not None:
            base_where.append(MouvementStockRestaurant.ingredient_id == ingredient_id)
        if type_mouvement is not None:
            base_where.append(MouvementStockRestaurant.type_mouvement == type_mouvement)
        if date_debut is not None:
            base_where.append(MouvementStockRestaurant.date_mouvement >= date_debut)
        if date_fin is not None:
            base_where.append(MouvementStockRestaurant.date_mouvement <= date_fin)

        count_base = select(MouvementStockRestaurant).where(*base_where)
        count_stmt = select(func.count()).select_from(count_base.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        data_stmt = (
            self._enriched_select()
            .where(*base_where)
            .order_by(MouvementStockRestaurant.date_mouvement.desc())
            .offset((page - 1) * effective_per_page)
            .limit(effective_per_page)
        )
        rows = await self.db.execute(data_stmt)
        return [self._row_to_dict(r) for r in rows.all()], total

    async def get_enriched(self, mouv_id: int) -> Optional[dict[str, Any]]:
        """Récupère un mouvement avec ingredient_nom + created_by_name."""
        stmt = self._enriched_select().where(
            MouvementStockRestaurant.id == mouv_id,
            MouvementStockRestaurant.tenant_id == _TENANT_RESTAURANT,
        )
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None
        return self._row_to_dict(row)
