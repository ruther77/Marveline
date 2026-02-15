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
