"""Repository pour l'entite Category."""
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.category import Category
from app.models.product import Product
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    """Repository pour les categories avec methodes specialisees."""

    def __init__(self, db: Session):
        super().__init__(db, Category)

    def get_by_slug(
        self,
        slug: str,
        tenant_id: int,
        include_inactive: bool = False
    ) -> Optional[Category]:
        """Recupere une categorie par son slug (unique par tenant)."""
        query = select(Category).filter(Category.slug == slug)
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
        query = select(Category).filter(Category.slug == slug)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if exclude_id:
            query = query.filter(Category.id != exclude_id)
        return self.db.execute(query).scalar_one_or_none() is not None

    def name_exists(
        self,
        name: str,
        tenant_id: int,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Verifie si un nom existe deja pour ce tenant."""
        query = select(Category).filter(Category.name == name)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        if exclude_id:
            query = query.filter(Category.id != exclude_id)
        return self.db.execute(query).scalar_one_or_none() is not None

    def list_by_parent(
        self,
        parent_id: Optional[int],
        tenant_id: int
    ) -> list[Category]:
        """Liste les categories enfants d'un parent."""
        query = select(Category)
        if parent_id is None:
            query = query.filter(Category.parent_id.is_(None))
        else:
            query = query.filter(Category.parent_id == parent_id)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        query = query.order_by(Category.display_order, Category.name)
        return list(self.db.execute(query).scalars().all())

    def list_all_active(self, tenant_id: int) -> list[Category]:
        """Liste toutes les categories actives d'un tenant (pour tree building)."""
        query = select(Category)
        query = self._apply_tenant_filter(query, tenant_id)
        query = self._apply_active_filter(query)
        query = query.order_by(Category.display_order, Category.name)
        return list(self.db.execute(query).scalars().all())

    def has_active_children(self, category_id: int, tenant_id: int) -> bool:
        """Verifie si une categorie a des enfants actifs."""
        query = select(func.count()).select_from(Category).filter(
            Category.parent_id == category_id,
            Category.is_active == True,  # noqa: E712
        )
        query = self._apply_tenant_filter(query, tenant_id)
        count = self.db.execute(query).scalar() or 0
        return count > 0

    def count_products(self, slug: str, tenant_id: int) -> int:
        """Compte les produits dans une categorie via slug match."""
        query = select(func.count()).select_from(Product).filter(
            Product.category == slug,
            Product.is_active == True,  # noqa: E712
        )
        query = query.filter(Product.tenant_id == tenant_id)
        return self.db.execute(query).scalar() or 0

class AsyncCategoryRepository:
    """Version async de CategoryRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get_by_slug(self, slug: str, tenant_id: int, include_inactive: bool = False) -> Optional[Category]:
        from sqlalchemy import select
        q = select(Category).filter(Category.slug == slug, Category.tenant_id == tenant_id)
        if not include_inactive:
            q = q.filter(Category.is_active == True)  # noqa: E712
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str, tenant_id: int, exclude_id: Optional[int] = None) -> bool:
        from sqlalchemy import select
        q = select(Category).filter(Category.slug == slug, Category.tenant_id == tenant_id, Category.is_active == True)  # noqa: E712
        if exclude_id:
            q = q.filter(Category.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def name_exists(self, name: str, tenant_id: int, exclude_id: Optional[int] = None) -> bool:
        from sqlalchemy import select
        q = select(Category).filter(Category.name == name, Category.tenant_id == tenant_id, Category.is_active == True)  # noqa: E712
        if exclude_id:
            q = q.filter(Category.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def list_by_parent(self, parent_id: Optional[int], tenant_id: int) -> list[Category]:
        from sqlalchemy import select
        q = select(Category).filter(Category.tenant_id == tenant_id, Category.is_active == True)  # noqa: E712
        if parent_id is None:
            q = q.filter(Category.parent_id.is_(None))
        else:
            q = q.filter(Category.parent_id == parent_id)
        result = await self.db.execute(q.order_by(Category.display_order, Category.name))
        return list(result.scalars().all())

    async def list_all_active(self, tenant_id: int) -> list[Category]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(Category).filter(Category.tenant_id == tenant_id, Category.is_active == True)  # noqa: E712
            .order_by(Category.display_order, Category.name)
        )
        return list(result.scalars().all())

    async def has_active_children(self, category_id: int, tenant_id: int) -> bool:
        from sqlalchemy import select, func
        result = await self.db.execute(
            select(func.count()).select_from(Category).filter(
                Category.parent_id == category_id, Category.tenant_id == tenant_id,
                Category.is_active == True,  # noqa: E712
            )
        )
        return (result.scalar() or 0) > 0

    async def count_products(self, slug: str, tenant_id: int) -> int:
        from sqlalchemy import select, func
        result = await self.db.execute(
            select(func.count()).select_from(Product).filter(
                Product.category == slug, Product.tenant_id == tenant_id,
                Product.is_active == True,  # noqa: E712
            )
        )
        return result.scalar() or 0

    async def get_by_id(self, category_id: int, tenant_id: int) -> Optional[Category]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(Category).filter(Category.id == category_id, Category.tenant_id == tenant_id, Category.is_active == True)  # noqa: E712
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Category:
        obj = Category(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: Category, data: dict) -> Category:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def soft_delete(self, obj: Category) -> Category:
        obj.is_active = False
        await self.db.flush()
        return obj
