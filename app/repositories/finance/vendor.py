"""Repository FinanceVendor — CRUD fournisseurs référentiel global."""
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance.vendor import FinanceVendor


class AsyncFinanceVendorRepository:
    """Repository async pour FinanceVendor (référentiel global, sans tenant)."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, vendor_id: int) -> Optional[FinanceVendor]:
        result = await self._db.execute(
            select(FinanceVendor).where(FinanceVendor.id == vendor_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[FinanceVendor]:
        result = await self._db.execute(
            select(FinanceVendor).where(FinanceVendor.code == code)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[FinanceVendor]:
        result = await self._db.execute(
            select(FinanceVendor).order_by(FinanceVendor.name)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self._db.execute(select(func.count()).select_from(FinanceVendor))
        return result.scalar_one()

    async def create(
        self,
        name: str,
        code: Optional[str] = None,
        adresse: Optional[str] = None,
        telephone: Optional[str] = None,
        email: Optional[str] = None,
    ) -> FinanceVendor:
        vendor = FinanceVendor(
            name=name, code=code, adresse=adresse,
            telephone=telephone, email=email,
        )
        self._db.add(vendor)
        await self._db.flush()
        return vendor

    async def update(self, vendor: FinanceVendor, **kwargs) -> FinanceVendor:
        for key, value in kwargs.items():
            setattr(vendor, key, value)
        await self._db.flush()
        return vendor
