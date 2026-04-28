"""Schémas Pydantic pour le module ProductCollection."""
from typing import Optional
from app.schemas.base import BaseSchema
from app.schemas.product import ProductList


class CollectionBase(BaseSchema):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class CollectionCreate(CollectionBase):
    pass


class CollectionUpdate(BaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CollectionResponse(CollectionBase):
    id: int
    tenant_id: int


class CollectionWithProducts(CollectionResponse):
    products: list[ProductList] = []


class CollectionAddProducts(BaseSchema):
    product_ids: list[int]


class CollectionList(BaseSchema):
    items: list[CollectionResponse]
    total: int
