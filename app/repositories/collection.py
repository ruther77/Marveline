"""Repository ProductCollection."""
from __future__ import annotations
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.product_collection import ProductCollection
from app.models.product import Product


class CollectionRepository:
    def __init__(self, db: Session, tenant_id: int) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def _base_query(self):
        return self.db.query(ProductCollection).filter(
            ProductCollection.tenant_id == self.tenant_id
        )

    def list(self, skip: int = 0, limit: int = 100) -> tuple[list[ProductCollection], int]:
        q = self._base_query()
        total = q.count()
        items = q.order_by(ProductCollection.id).offset(skip).limit(limit).all()
        return items, total

    def get_by_id(self, collection_id: int) -> Optional[ProductCollection]:
        return self._base_query().filter(ProductCollection.id == collection_id).first()

    def create(self, name: str, description: Optional[str], is_active: bool) -> ProductCollection:
        obj = ProductCollection(
            tenant_id=self.tenant_id,
            name=name,
            description=description,
            is_active=is_active,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def update(
        self,
        collection: ProductCollection,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> ProductCollection:
        if name is not None:
            collection.name = name
        if description is not None:
            collection.description = description
        if is_active is not None:
            collection.is_active = is_active
        self.db.flush()
        return collection

    def delete(self, collection: ProductCollection) -> None:
        self.db.delete(collection)
        self.db.flush()

    def add_products(self, collection: ProductCollection, product_ids: List[int]) -> ProductCollection:
        existing_ids = {p.id for p in collection.products}
        for pid in product_ids:
            if pid not in existing_ids:
                product = (
                    self.db.query(Product)
                    .filter(Product.id == pid, Product.tenant_id == self.tenant_id)
                    .first()
                )
                if product:
                    collection.products.append(product)
        self.db.flush()
        return collection

    def remove_product(self, collection: ProductCollection, product_id: int) -> ProductCollection:
        collection.products = [p for p in collection.products if p.id != product_id]
        self.db.flush()
        return collection
