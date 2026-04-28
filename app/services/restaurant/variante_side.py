"""Service — VarianteSide (gestion sides par plat avec supplément).

ISO-VARSIDE-01 : toutes les méthodes exigent désormais tenant_id.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.repositories.restaurant.variante_side import AsyncVarianteSideRepo
from app.schemas.restaurant.variante_side import (
    VarianteSideCreate,
    VarianteSideResponse,
    VarianteSideUpdate,
)


class VarianteSideService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = AsyncVarianteSideRepo(db)

    async def list_sides(
        self, variante_plat_id: int, tenant_id: int
    ) -> list[VarianteSideResponse]:
        rows = await self._repo.list_by_variante(variante_plat_id, tenant_id)
        return [VarianteSideResponse(**row) for row in rows]

    async def add_side(
        self, variante_plat_id: int, tenant_id: int, payload: VarianteSideCreate
    ) -> VarianteSideResponse:
        existing = await self._repo.get(variante_plat_id, payload.side_id, tenant_id)
        if existing:
            # Réactiver si désactivé
            existing.is_active = True
            existing.supplement_cts = payload.supplement_cts
            await self._repo._db.flush()
            rows = await self._repo.list_by_variante(variante_plat_id, tenant_id)
            match = next((r for r in rows if r["side_id"] == payload.side_id), None)
            if match:
                return VarianteSideResponse(**match)

        obj = await self._repo.create(
            tenant_id=tenant_id,
            variante_plat_id=variante_plat_id,
            side_id=payload.side_id,
            supplement_cts=payload.supplement_cts,
        )
        rows = await self._repo.list_by_variante(variante_plat_id, tenant_id)
        match = next((r for r in rows if r["side_id"] == obj.side_id), None)
        if match:
            return VarianteSideResponse(**match)
        return VarianteSideResponse(
            id=obj.id,
            side_id=obj.side_id,
            supplement_cts=obj.supplement_cts,
            is_active=obj.is_active,
        )

    async def update_side(
        self, variante_plat_id: int, side_id: int, tenant_id: int, payload: VarianteSideUpdate
    ) -> VarianteSideResponse:
        obj = await self._repo.get(variante_plat_id, side_id, tenant_id)
        if obj is None:
            raise NotFound("VarianteSide")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        await self._repo._db.flush()
        rows = await self._repo.list_by_variante(variante_plat_id, tenant_id)
        match = next((r for r in rows if r["side_id"] == side_id), None)
        if match:
            return VarianteSideResponse(**match)
        raise NotFound("VarianteSide")

    async def remove_side(
        self, variante_plat_id: int, side_id: int, tenant_id: int
    ) -> bool:
        return await self._repo.delete(variante_plat_id, side_id, tenant_id)
