"""Repository — IngredientRestaurant (tenant_id=3).

ADR-14 : `stock_actuel` lu directement DB — get_by_id_lock utilise SELECT FOR UPDATE.
Filtre `statut` : ok | bas | rupture — calculé via SQL CASE pour filtrage côté DB.
`get_dernieres_entrees_batch` : anti-N+1 — batch dernière entrée par ingrédient.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.models.restaurant.mouvement_stock_restaurant import MouvementStockRestaurant

_TENANT_RESTAURANT = 3
_DEFAULT_PER_PAGE = 20
_MAX_PER_PAGE = 100


class AsyncIngredientRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs) -> IngredientRestaurant:
        obj = IngredientRestaurant(tenant_id=_TENANT_RESTAURANT, **kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, ing_id: int) -> Optional[IngredientRestaurant]:
        stmt = select(IngredientRestaurant).where(
            IngredientRestaurant.id == ing_id,
            IngredientRestaurant.tenant_id == _TENANT_RESTAURANT,
            IngredientRestaurant.is_active.is_(True),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete(self, ing_id: int) -> bool:
        """Désactive l'ingrédient (soft delete via SoftDeleteMixin)."""
        obj = await self.get_by_id(ing_id)
        if obj is None:
            return False
        obj.is_active = False
        await self.db.flush()
        return True

    async def get_by_id_lock(self, ing_id: int) -> Optional[IngredientRestaurant]:
        """SELECT FOR UPDATE — pour modifications stock atomiques (ADR-14)."""
        stmt = (
            select(IngredientRestaurant)
            .where(
                IngredientRestaurant.id == ing_id,
                IngredientRestaurant.tenant_id == _TENANT_RESTAURANT,
                IngredientRestaurant.is_active.is_(True),
            )
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        page: int = 1,
        per_page: int = _DEFAULT_PER_PAGE,
        search: Optional[str] = None,
        categorie_id: Optional[int] = None,
        statut: Optional[str] = None,
    ) -> tuple[list[IngredientRestaurant], int]:
        effective_per_page = min(per_page, _MAX_PER_PAGE)
        base = select(IngredientRestaurant).where(
            IngredientRestaurant.tenant_id == _TENANT_RESTAURANT,
            IngredientRestaurant.is_active.is_(True),
        )
        if search:
            base = base.where(IngredientRestaurant.nom.ilike(f"%{search}%"))
        if categorie_id is not None:
            base = base.where(IngredientRestaurant.categorie_id == categorie_id)
        if statut is not None:
            base = self._apply_statut_filter(base, statut)
        count_stmt = select(func.count()).select_from(base.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0
        # B3 : ORDER BY categorie_id pour regroupement frontend, puis nom
        data_stmt = (
            base.order_by(
                IngredientRestaurant.categorie_id.asc().nulls_last(),
                IngredientRestaurant.nom,
            )
            .offset((page - 1) * effective_per_page)
            .limit(effective_per_page)
        )
        rows = await self.db.execute(data_stmt)
        return list(rows.scalars().all()), total

    async def count_ruptures(self) -> int:
        """Nombre d'ingrédients actifs en rupture (stock_actuel ≤ 0)."""
        stmt = select(func.count()).select_from(
            select(IngredientRestaurant.id).where(
                IngredientRestaurant.tenant_id == _TENANT_RESTAURANT,
                IngredientRestaurant.is_active.is_(True),
                IngredientRestaurant.stock_actuel <= Decimal("0"),
            ).subquery()
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    def _apply_statut_filter(stmt, statut: str):
        """Filtre SQL par statut calculé : rupture | bas | ok."""
        zero = Decimal("0")
        if statut == "rupture":
            return stmt.where(IngredientRestaurant.stock_actuel <= zero)
        if statut == "bas":
            return stmt.where(
                IngredientRestaurant.stock_actuel > zero,
                IngredientRestaurant.stock_actuel <= IngredientRestaurant.stock_alerte,
                IngredientRestaurant.stock_alerte > zero,
            )
        # statut == "ok"
        return stmt.where(
            (IngredientRestaurant.stock_actuel > IngredientRestaurant.stock_alerte)
            | (IngredientRestaurant.stock_alerte <= zero)
        )

    async def list_epuises(self) -> list[IngredientRestaurant]:
        """Ingrédients avec stock_actuel ≤ 0 (ruptures dashboard)."""
        stmt = select(IngredientRestaurant).where(
            IngredientRestaurant.tenant_id == _TENANT_RESTAURANT,
            IngredientRestaurant.is_active.is_(True),
            IngredientRestaurant.stock_actuel <= Decimal("0"),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_dernieres_entrees_batch(
        self, ingredient_ids: list[int],
    ) -> dict[int, datetime]:
        """Anti-N+1 : date du dernier mouvement 'entree' par ingrédient."""
        if not ingredient_ids:
            return {}
        stmt = (
            select(
                MouvementStockRestaurant.ingredient_id,
                func.max(MouvementStockRestaurant.date_mouvement).label("derniere"),
            )
            .where(
                MouvementStockRestaurant.tenant_id == _TENANT_RESTAURANT,
                MouvementStockRestaurant.ingredient_id.in_(ingredient_ids),
                MouvementStockRestaurant.type_mouvement == "entree",
            )
            .group_by(MouvementStockRestaurant.ingredient_id)
        )
        rows = await self.db.execute(stmt)
        return {r.ingredient_id: r.derniere for r in rows.all()}
