"""Endpoints CRUD pour les variantes couleur de produits."""
import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.product_variant import (
    ProductVariantCreate,
    ProductVariantResponse,
    ProductVariantUpdate,
)
from app.services.product_variant import ProductVariantService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/products/{product_id}/variants",
    tags=["Product Variants"],
)


@router.get("", response_model=PaginatedResponse[ProductVariantResponse])
async def list_product_variants(
    product_id: int,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
) -> PaginatedResponse[ProductVariantResponse]:
    """Liste les variantes actives d'un produit."""
    service = ProductVariantService(db)
    all_items = await service.list_variants(product_id, current_user.tenant_id)
    total = len(all_items)
    page = all_items[pagination.skip : pagination.skip + pagination.limit]
    return PaginatedResponse[ProductVariantResponse](
        items=[ProductVariantResponse.model_validate(v) for v in page],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{variant_id}", response_model=ProductVariantResponse)
async def get_product_variant(
    product_id: int,
    variant_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
) -> ProductVariantResponse:
    """Récupère les détails d'une variante."""
    service = ProductVariantService(db)
    variant = await service.get_variant(product_id, variant_id, current_user.tenant_id)
    return ProductVariantResponse.model_validate(variant)


@router.post(
    "", response_model=ProductVariantResponse, status_code=status.HTTP_201_CREATED
)
async def create_product_variant(
    product_id: int,
    data: ProductVariantCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> ProductVariantResponse:
    """Crée une variante couleur pour un produit (products:write).

    La combinaison produit + couleur doit être unique par tenant.
    Le SKU doit être unique dans le tenant.
    """
    service = ProductVariantService(db)
    variant = await service.create_variant(product_id, data, current_user.tenant_id)
    await db.commit()
    await db.refresh(variant)
    return ProductVariantResponse.model_validate(variant)


@router.patch("/{variant_id}", response_model=ProductVariantResponse)
async def update_product_variant(
    product_id: int,
    variant_id: int,
    data: ProductVariantUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> ProductVariantResponse:
    """Met à jour une variante (products:write, PATCH partiel)."""
    service = ProductVariantService(db)
    variant = await service.update_variant(
        product_id, variant_id, data, current_user.tenant_id
    )
    await db.commit()
    await db.refresh(variant)
    return ProductVariantResponse.model_validate(variant)


@router.delete("/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_variant(
    product_id: int,
    variant_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> None:
    """Supprime (soft delete) une variante (products:write)."""
    service = ProductVariantService(db)
    await service.delete_variant(product_id, variant_id, current_user.tenant_id)
    await db.commit()
