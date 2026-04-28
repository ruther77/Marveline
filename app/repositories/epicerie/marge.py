"""Repository marges par catégorie épicerie."""
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.epicerie.marge import EpicerieMargeCategorie


class AsyncEpicerieMargeRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_all(self, tenant_id: int) -> list[EpicerieMargeCategorie]:
        result = await self._db.execute(
            select(EpicerieMargeCategorie)
            .where(EpicerieMargeCategorie.tenant_id == tenant_id)
            .order_by(EpicerieMargeCategorie.categorie)
        )
        return list(result.scalars().all())

    async def get_by_categorie(self, tenant_id: int, categorie: str) -> Optional[EpicerieMargeCategorie]:
        result = await self._db.execute(
            select(EpicerieMargeCategorie).where(
                EpicerieMargeCategorie.tenant_id == tenant_id,
                EpicerieMargeCategorie.categorie == categorie,
            )
        )
        return result.scalar_one_or_none()

    async def get_marges_dict(self, tenant_id: int) -> dict[str, int]:
        """Retourne {categorie: taux_marge_centieme} pour un tenant."""
        rows = await self.get_all(tenant_id)
        return {r.categorie: r.taux_marge_centieme for r in rows}

    async def upsert(self, tenant_id: int, categorie: str, taux: int) -> EpicerieMargeCategorie:
        existing = await self.get_by_categorie(tenant_id, categorie)
        if existing:
            existing.taux_marge_centieme = taux
            await self._db.flush()
            return existing
        obj = EpicerieMargeCategorie(
            tenant_id=tenant_id,
            categorie=categorie,
            taux_marge_centieme=taux,
        )
        self._db.add(obj)
        await self._db.flush()
        return obj

    async def upsert_batch(self, tenant_id: int, marges: dict[str, int]) -> int:
        """Upsert un dict {categorie: taux}. Retourne le nombre modifié."""
        count = 0
        for cat, taux in marges.items():
            await self.upsert(tenant_id, cat, taux)
            count += 1
        return count

    async def remove(self, tenant_id: int, categorie: str) -> bool:
        result = await self._db.execute(
            delete(EpicerieMargeCategorie).where(
                EpicerieMargeCategorie.tenant_id == tenant_id,
                EpicerieMargeCategorie.categorie == categorie,
            )
        )
        return result.rowcount > 0
