"""Repository pour ProductVariant."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product_variant import ProductVariant
from app.repositories.base import BaseRepository


class ProductVariantRepository(BaseRepository[ProductVariant]):
    """Repository variantes produit avec isolation multi-tenant."""

    def __init__(self, db: Session):
        super().__init__(db, ProductVariant)

    def list_by_product(
        self, product_id: int, tenant_id: int
    ) -> list[ProductVariant]:
        """Liste toutes les variantes actives d'un produit, triées par label."""
        query = (
            select(ProductVariant)
            .filter(
                ProductVariant.product_id == product_id,
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.is_active == True,  # noqa: E712
            )
            .order_by(ProductVariant.label)
        )
        return list(self.db.execute(query).scalars().all())

    def get_by_product_and_label(
        self, product_id: int, label: str, tenant_id: int
    ) -> Optional[ProductVariant]:
        """Récupère une variante par produit + label."""
        query = select(ProductVariant).filter(
            ProductVariant.product_id == product_id,
            ProductVariant.label == label,
            ProductVariant.tenant_id == tenant_id,
            ProductVariant.is_active == True,  # noqa: E712
        )
        return self.db.execute(query).scalar_one_or_none()

    def label_exists_for_product(
        self,
        product_id: int,
        label: str,
        tenant_id: int,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """Vérifie si un label existe déjà pour ce produit."""
        query = select(ProductVariant).filter(
            ProductVariant.product_id == product_id,
            ProductVariant.label == label,
            ProductVariant.tenant_id == tenant_id,
            ProductVariant.is_active == True,  # noqa: E712
        )
        if exclude_id:
            query = query.filter(ProductVariant.id != exclude_id)
        return self.db.execute(query).scalar_one_or_none() is not None

    def sku_exists(
        self, sku: str, tenant_id: int, exclude_id: Optional[int] = None
    ) -> bool:
        """Vérifie si un SKU existe déjà pour ce tenant."""
        query = select(ProductVariant).filter(
            ProductVariant.sku == sku,
            ProductVariant.tenant_id == tenant_id,
            ProductVariant.is_active == True,  # noqa: E712
        )
        if exclude_id:
            query = query.filter(ProductVariant.id != exclude_id)
        return self.db.execute(query).scalar_one_or_none() is not None


class AsyncProductVariantRepository:
    """Version async de ProductVariantRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get_by_id(self, variant_id: int, tenant_id: int):
        from sqlalchemy import select
        from app.models.product_variant import ProductVariant
        result = await self.db.execute(
            select(ProductVariant).filter(
                ProductVariant.id == variant_id,
                ProductVariant.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_product(self, product_id: int, tenant_id: int) -> list:
        from sqlalchemy import select
        from app.models.product_variant import ProductVariant
        result = await self.db.execute(
            select(ProductVariant)
            .filter(
                ProductVariant.product_id == product_id,
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.is_active == True,  # noqa: E712
            )
            .order_by(ProductVariant.label)
        )
        return list(result.scalars().all())

    async def get_by_product_and_label(
        self, product_id: int, label: str, tenant_id: int
    ):
        from sqlalchemy import select
        from app.models.product_variant import ProductVariant
        result = await self.db.execute(
            select(ProductVariant).filter(
                ProductVariant.product_id == product_id,
                ProductVariant.label == label,
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def label_exists_for_product(
        self,
        product_id: int,
        label: str,
        tenant_id: int,
        exclude_id=None,
    ) -> bool:
        from sqlalchemy import select
        from app.models.product_variant import ProductVariant
        q = select(ProductVariant).filter(
            ProductVariant.product_id == product_id,
            ProductVariant.label == label,
            ProductVariant.tenant_id == tenant_id,
            ProductVariant.is_active == True,  # noqa: E712
        )
        if exclude_id:
            q = q.filter(ProductVariant.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def sku_exists(self, sku: str, tenant_id: int, exclude_id=None) -> bool:
        from sqlalchemy import select
        from app.models.product_variant import ProductVariant
        q = select(ProductVariant).filter(
            ProductVariant.sku == sku,
            ProductVariant.tenant_id == tenant_id,
            ProductVariant.is_active == True,  # noqa: E712
        )
        if exclude_id:
            q = q.filter(ProductVariant.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def create(self, data: dict):
        from app.models.product_variant import ProductVariant
        obj = ProductVariant(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj, data: dict):
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def soft_delete(self, obj) -> None:
        obj.is_active = False
        await self.db.flush()

    async def _get_for_update(
        self, variant_id: int, tenant_id: int
    ) -> "ProductVariant | None":
        """SELECT FOR UPDATE — verrouille la variante pour opération stock."""
        result = await self.db.execute(
            select(ProductVariant).where(
                ProductVariant.id == variant_id,
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.is_active == True,  # noqa: E712
            ).with_for_update()
        )
        return result.scalar_one_or_none()

    async def check_availability(
        self, variant_id: int, quantity: int, tenant_id: int
    ) -> bool:
        """Vérifie si le stock disponible de la variante est suffisant."""
        variant = await self.get_by_id(variant_id, tenant_id)
        if not variant:
            return False
        return variant.available_quantity >= quantity

    async def reserve_stock(
        self, variant_id: int, quantity: int, tenant_id: int
    ) -> bool:
        """Réserve du stock (available_quantity -= quantity).

        Utilise SELECT FOR UPDATE pour éviter les race conditions.
        Ne commit pas — la transaction est gérée par le service appelant.
        """
        variant = await self._get_for_update(variant_id, tenant_id)
        if not variant or variant.available_quantity < quantity:
            return False
        variant.available_quantity -= quantity
        await self.db.flush()
        return True

    async def release_stock(
        self, variant_id: int, quantity: int, tenant_id: int
    ) -> bool:
        """Libère du stock (available_quantity += quantity, cap at stock_quantity).

        Utilise SELECT FOR UPDATE pour éviter les race conditions.
        Ne commit pas — la transaction est gérée par le service appelant.
        """
        variant = await self._get_for_update(variant_id, tenant_id)
        if not variant:
            return False
        new_available = variant.available_quantity + quantity
        if new_available > variant.stock_quantity:
            new_available = variant.stock_quantity
        variant.available_quantity = new_available
        await self.db.flush()
        return True
