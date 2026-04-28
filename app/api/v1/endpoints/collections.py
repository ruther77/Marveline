"""Endpoints collections de produits — regroupements thématiques."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from app.core.exceptions import NotFound
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.errors import ErrorMessages
from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.models.product_collection import ProductCollection
from app.models.product import Product
from app.schemas.collection import (
    CollectionCreate,
    CollectionUpdate,
    CollectionResponse,
    CollectionWithProducts,
    CollectionAddProducts,
)
from app.schemas.common import PaginatedResponse, PaginationParams

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get("", response_model=PaginatedResponse[CollectionResponse])
async def list_collections(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_READ)),
) -> PaginatedResponse[CollectionResponse]:
    """Liste toutes les collections du tenant."""
    total = (await db.execute(
        select(func.count(ProductCollection.id)).where(
            ProductCollection.tenant_id == current_user.tenant_id
        )
    )).scalar() or 0
    items = (await db.execute(
        select(ProductCollection)
        .where(ProductCollection.tenant_id == current_user.tenant_id)
        .order_by(ProductCollection.id)
        .offset(pagination.skip)
        .limit(pagination.limit)
    )).scalars().all()
    return PaginatedResponse[CollectionResponse](
        items=list(items),
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(
    data: CollectionCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> CollectionResponse:
    """Crée une nouvelle collection."""
    obj = ProductCollection(
        tenant_id=current_user.tenant_id,
        name=data.name,
        description=data.description,
        is_active=data.is_active,
    )
    db.add(obj)
    await db.flush()
    await db.commit()
    await db.refresh(obj)
    return obj


@router.get("/{collection_id}", response_model=CollectionWithProducts)
async def get_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_READ)),
) -> CollectionWithProducts:
    """Détail d'une collection avec ses produits."""
    obj = (await db.execute(
        select(ProductCollection).where(
            ProductCollection.id == collection_id,
            ProductCollection.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not obj:
        raise NotFound(ErrorMessages.COLLECTION_NOT_FOUND)
    return obj


@router.patch("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: int,
    data: CollectionUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> CollectionResponse:
    """Met à jour une collection."""
    obj = (await db.execute(
        select(ProductCollection).where(
            ProductCollection.id == collection_id,
            ProductCollection.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not obj:
        raise NotFound(ErrorMessages.COLLECTION_NOT_FOUND)
    if data.name is not None:
        obj.name = data.name
    if data.description is not None:
        obj.description = data.description
    if data.is_active is not None:
        obj.is_active = data.is_active
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> None:
    """Supprime une collection (ne supprime pas les produits)."""
    obj = (await db.execute(
        select(ProductCollection).where(
            ProductCollection.id == collection_id,
            ProductCollection.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not obj:
        raise NotFound(ErrorMessages.COLLECTION_NOT_FOUND)
    await db.delete(obj)
    await db.commit()


@router.post("/{collection_id}/products", response_model=CollectionWithProducts)
async def add_products_to_collection(
    collection_id: int,
    data: CollectionAddProducts,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> CollectionWithProducts:
    """Ajoute des produits à une collection."""
    obj = (await db.execute(
        select(ProductCollection).where(
            ProductCollection.id == collection_id,
            ProductCollection.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not obj:
        raise NotFound(ErrorMessages.COLLECTION_NOT_FOUND)
    existing_ids = {p.id for p in obj.products}
    for pid in data.product_ids:
        if pid not in existing_ids:
            product = (await db.execute(
                select(Product).where(
                    Product.id == pid,
                    Product.tenant_id == current_user.tenant_id,
                )
            )).scalar_one_or_none()
            if product:
                obj.products.append(product)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.delete("/{collection_id}/products/{product_id}", response_model=CollectionWithProducts)
async def remove_product_from_collection(
    collection_id: int,
    product_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> CollectionWithProducts:
    """Retire un produit d'une collection."""
    obj = (await db.execute(
        select(ProductCollection).where(
            ProductCollection.id == collection_id,
            ProductCollection.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not obj:
        raise NotFound(ErrorMessages.COLLECTION_NOT_FOUND)
    obj.products = [p for p in obj.products if p.id != product_id]
    await db.commit()
    await db.refresh(obj)
    return obj
