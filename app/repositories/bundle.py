"""Repositories pour ProductBundle et BundleItem."""
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload
from app.models.bundle import ProductBundle, BundleItem
from app.repositories.base import BaseRepository


class BundleRepository(BaseRepository[ProductBundle]):
    """Repository pour les bundles avec methodes specialisees."""

    def __init__(self, db: Session):
        super().__init__(db, ProductBundle)

    def get_by_slug(
        self,
        slug: str,
        tenant_id: int,
        include_inactive: bool = False
    ) -> Optional[ProductBundle]:
        """Recupere un bundle par son slug (unique par tenant)."""
        query = select(ProductBundle).filter(ProductBundle.slug == slug)
        query = self._apply_tenant_filter(query, tenant_id)
        if not include_inactive:
            query = self._apply_active_filter(query)
        return self.db.execute(query).scalar_one_or_none()

    def slug_exists(
        self,
        slug: str,
        tenant_id: int,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Verifie si un slug existe deja pour ce tenant."""
        query = select(ProductBundle).filter(ProductBundle.slug == slug)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if exclude_id:
            query = query.filter(ProductBundle.id != exclude_id)
        return self.db.execute(query).scalar_one_or_none() is not None

    def name_exists(
        self,
        name: str,
        tenant_id: int,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Verifie si un nom existe deja pour ce tenant."""
        query = select(ProductBundle).filter(ProductBundle.name == name)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if exclude_id:
            query = query.filter(ProductBundle.id != exclude_id)
        return self.db.execute(query).scalar_one_or_none() is not None

    def get_with_items(
        self,
        bundle_id: int,
        tenant_id: int,
        include_inactive: bool = False
    ) -> Optional[ProductBundle]:
        """Recupere un bundle avec ses items et produits (eager loading)."""
        query = (
            select(ProductBundle)
            .options(
                joinedload(ProductBundle.items).joinedload(BundleItem.product)
            )
            .filter(ProductBundle.id == bundle_id)
        )
        query = self._apply_tenant_filter(query, tenant_id)
        if not include_inactive:
            query = self._apply_active_filter(query)
        return self.db.execute(query).unique().scalar_one_or_none()

    def list_featured(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[list[ProductBundle], int]:
        """Liste les bundles mis en avant."""
        return self.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters={"featured": True},
            order_by="display_order",
        )


class BundleItemRepository(BaseRepository[BundleItem]):
    """Repository pour les items de bundle."""

    def __init__(self, db: Session):
        super().__init__(db, BundleItem)

    def get_by_bundle_and_product(
        self,
        bundle_id: int,
        product_id: int,
        tenant_id: int
    ) -> Optional[BundleItem]:
        """Recupere un item par bundle_id et product_id."""
        query = select(BundleItem).filter(
            BundleItem.bundle_id == bundle_id,
            BundleItem.product_id == product_id,
        )
        query = self._apply_tenant_filter(query, tenant_id)
        return self.db.execute(query).scalar_one_or_none()

    def list_by_bundle(
        self,
        bundle_id: int,
        tenant_id: int
    ) -> list[BundleItem]:
        """Liste les items d'un bundle."""
        query = select(BundleItem).filter(
            BundleItem.bundle_id == bundle_id,
        )
        query = self._apply_tenant_filter(query, tenant_id)
        query = query.order_by(BundleItem.display_order, BundleItem.id)
        return list(self.db.execute(query).scalars().all())

    def delete_by_bundle(
        self,
        bundle_id: int,
        tenant_id: int
    ) -> int:
        """Supprime tous les items d'un bundle. Retourne le nombre supprime."""
        items = self.list_by_bundle(bundle_id, tenant_id)
        count = len(items)
        for item in items:
            self.db.delete(item)
        self.db.flush()
        return count

class AsyncBundleRepository:
    """Version async de BundleRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get_by_slug(self, slug: str, tenant_id: int, include_inactive: bool = False) -> Optional[ProductBundle]:
        from sqlalchemy import select
        q = select(ProductBundle).filter(ProductBundle.slug == slug, ProductBundle.tenant_id == tenant_id)
        if not include_inactive:
            q = q.filter(ProductBundle.is_active == True)  # noqa: E712
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str, tenant_id: int, exclude_id: Optional[int] = None) -> bool:
        from sqlalchemy import select
        q = select(ProductBundle).filter(ProductBundle.slug == slug, ProductBundle.tenant_id == tenant_id, ProductBundle.is_active == True)  # noqa: E712
        if exclude_id:
            q = q.filter(ProductBundle.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def name_exists(self, name: str, tenant_id: int, exclude_id: Optional[int] = None) -> bool:
        from sqlalchemy import select
        q = select(ProductBundle).filter(ProductBundle.name == name, ProductBundle.tenant_id == tenant_id, ProductBundle.is_active == True)  # noqa: E712
        if exclude_id:
            q = q.filter(ProductBundle.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def get_with_items(self, bundle_id: int, tenant_id: int, include_inactive: bool = False) -> Optional[ProductBundle]:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        q = (
            select(ProductBundle)
            .options(joinedload(ProductBundle.items).joinedload(BundleItem.product))
            .filter(ProductBundle.id == bundle_id, ProductBundle.tenant_id == tenant_id)
        )
        if not include_inactive:
            q = q.filter(ProductBundle.is_active == True)  # noqa: E712
        result = await self.db.execute(q)
        return result.unique().scalar_one_or_none()

    async def list_featured(self, tenant_id: int, skip: int = 0, limit: int = 100) -> tuple[list[ProductBundle], int]:
        from sqlalchemy import select, func
        q = select(ProductBundle).filter(ProductBundle.tenant_id == tenant_id, ProductBundle.is_active == True, ProductBundle.featured == True)  # noqa: E712
        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar() or 0
        items_result = await self.db.execute(q.order_by(ProductBundle.display_order).offset(skip).limit(min(limit, 1000)))
        return list(items_result.scalars().all()), total

    async def list(self, tenant_id: int, skip: int = 0, limit: int = 100, filters: Optional[dict] = None) -> tuple[list[ProductBundle], int]:
        from sqlalchemy import select, func
        q = select(ProductBundle).filter(ProductBundle.tenant_id == tenant_id, ProductBundle.is_active == True)  # noqa: E712
        if filters:
            for key, value in filters.items():
                if hasattr(ProductBundle, key):
                    q = q.filter(getattr(ProductBundle, key) == value)
        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar() or 0
        items_result = await self.db.execute(q.offset(skip).limit(min(limit, 1000)))
        return list(items_result.scalars().all()), total

    async def get_by_id(self, bundle_id: int, tenant_id: int) -> Optional[ProductBundle]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(ProductBundle).filter(ProductBundle.id == bundle_id, ProductBundle.tenant_id == tenant_id, ProductBundle.is_active == True)  # noqa: E712
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> ProductBundle:
        obj = ProductBundle(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: ProductBundle, data: dict) -> ProductBundle:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def soft_delete(self, obj: ProductBundle) -> ProductBundle:
        obj.is_active = False
        await self.db.flush()
        return obj


class AsyncBundleItemRepository:
    """Version async de BundleItemRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get_by_bundle_and_product(self, bundle_id: int, product_id: int, tenant_id: int) -> Optional[BundleItem]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(BundleItem).filter(BundleItem.bundle_id == bundle_id, BundleItem.product_id == product_id, BundleItem.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def list_by_bundle(self, bundle_id: int, tenant_id: int) -> list[BundleItem]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(BundleItem).filter(BundleItem.bundle_id == bundle_id, BundleItem.tenant_id == tenant_id)
            .order_by(BundleItem.display_order, BundleItem.id)
        )
        return list(result.scalars().all())

    async def delete_by_bundle(self, bundle_id: int, tenant_id: int) -> int:
        items = await self.list_by_bundle(bundle_id, tenant_id)
        for item in items:
            await self.db.delete(item)
        await self.db.flush()
        return len(items)

    async def create(self, data: dict) -> BundleItem:
        obj = BundleItem(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj
