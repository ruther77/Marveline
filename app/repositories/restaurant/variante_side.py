"""Repository — VarianteSide (liaison plat ↔ side).

ISO-VARSIDE-01 : toutes les méthodes filtrent désormais par tenant_id.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.variante_side import VarianteSide
from app.models.restaurant.side_restaurant import SideRestaurant


class AsyncVarianteSideRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_by_variante(
        self, variante_plat_id: int, tenant_id: int
    ) -> list[dict]:
        """Retourne les sides liés à un plat avec nom + image du side."""
        stmt = (
            select(
                VarianteSide.id,
                VarianteSide.side_id,
                SideRestaurant.nom.label("side_nom"),
                SideRestaurant.image_url.label("side_image_url"),
                VarianteSide.supplement_cts,
                VarianteSide.is_active,
            )
            .join(SideRestaurant, SideRestaurant.id == VarianteSide.side_id)
            .where(
                VarianteSide.variante_plat_id == variante_plat_id,
                VarianteSide.tenant_id == tenant_id,
                VarianteSide.is_active.is_(True),
            )
            .order_by(VarianteSide.supplement_cts, SideRestaurant.nom)
        )
        result = await self._db.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def get(
        self, variante_plat_id: int, side_id: int, tenant_id: int
    ) -> Optional[VarianteSide]:
        stmt = select(VarianteSide).where(
            VarianteSide.variante_plat_id == variante_plat_id,
            VarianteSide.side_id == side_id,
            VarianteSide.tenant_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, tenant_id: int, **kwargs) -> VarianteSide:
        obj = VarianteSide(tenant_id=tenant_id, **kwargs)
        self._db.add(obj)
        await self._db.flush()
        await self._db.refresh(obj)
        return obj

    async def delete(
        self, variante_plat_id: int, side_id: int, tenant_id: int
    ) -> bool:
        obj = await self.get(variante_plat_id, side_id, tenant_id)
        if obj is None:
            return False
        await self._db.delete(obj)
        await self._db.flush()
        return True
