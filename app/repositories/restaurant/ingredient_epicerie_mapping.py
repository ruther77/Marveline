"""Repository — IngredientEpicerieMapping.

Multi-tenant strict (A1) : toutes les méthodes filtrent par tenant_id du
restaurant propriétaire du mapping. L'isolation cross-tenant vers le produit
épicerie est vérifiée par le service appelant (vérif tenant jumelé).
"""
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.ingredient_epicerie_mapping import IngredientEpicerieMapping


class AsyncIngredientEpicerieMappingRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_by_ingredient(
        self, ingredient_id: int, tenant_id: int,
    ) -> list[IngredientEpicerieMapping]:
        """Retourne les mappings triés par ordre croissant (préférés en tête)."""
        stmt = (
            select(IngredientEpicerieMapping)
            .where(
                IngredientEpicerieMapping.ingredient_id == ingredient_id,
                IngredientEpicerieMapping.tenant_id == tenant_id,
            )
            .order_by(
                IngredientEpicerieMapping.ordre.asc(),
                IngredientEpicerieMapping.id.asc(),
            )
        )
        return list((await self._db.execute(stmt)).scalars())

    async def get(
        self, ingredient_id: int, produit_id: int, tenant_id: int,
    ) -> Optional[IngredientEpicerieMapping]:
        stmt = select(IngredientEpicerieMapping).where(
            IngredientEpicerieMapping.ingredient_id == ingredient_id,
            IngredientEpicerieMapping.produit_id == produit_id,
            IngredientEpicerieMapping.tenant_id == tenant_id,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def create(
        self,
        tenant_id: int,
        ingredient_id: int,
        produit_id: int,
        ordre: int,
        facteur_conv: Decimal,
        notes: Optional[str] = None,
    ) -> IngredientEpicerieMapping:
        mapping = IngredientEpicerieMapping(
            tenant_id=tenant_id,
            ingredient_id=ingredient_id,
            produit_id=produit_id,
            ordre=ordre,
            facteur_conv=facteur_conv,
            notes=notes,
        )
        self._db.add(mapping)
        await self._db.flush()
        await self._db.refresh(mapping)
        return mapping

    async def update(
        self,
        mapping: IngredientEpicerieMapping,
        ordre: Optional[int] = None,
        facteur_conv: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> IngredientEpicerieMapping:
        if ordre is not None:
            mapping.ordre = ordre
        if facteur_conv is not None:
            mapping.facteur_conv = facteur_conv
        if notes is not None:
            mapping.notes = notes
        await self._db.flush()
        await self._db.refresh(mapping)
        return mapping

    async def delete(self, mapping: IngredientEpicerieMapping) -> None:
        await self._db.delete(mapping)
        await self._db.flush()
