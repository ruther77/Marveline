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
