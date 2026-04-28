"""Endpoints CRUD pour les bundles (packs de produits)."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.services.bundle import BundleService
from app.schemas.bundle import (
    BundleCreate,
    BundleUpdate,
    BundleResponse,
    BundleWithItems,
    BundleItemCreate,
    BundleItemUpdate,
    BundleItemResponse,
    BundlePriceResponse,
)
from app.schemas.common import PaginationParams, PaginatedResponse
from app.constants import ErrorMessages
from app.models.bundle import BundleItem as BundleItemModel


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bundles", tags=["Bundles"])


@router.get("", response_model=PaginatedResponse[BundleResponse])
async def list_bundles(
    pagination: PaginationParams = Depends(),
    featured: bool = Query(None, description="Filtrer bundles mis en avant"),
    active_only: bool = Query(True, description="Filtrer bundles actifs uniquement"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.BUNDLES_READ)),
) -> PaginatedResponse[BundleResponse]:
    """Liste les bundles avec pagination."""
    service = BundleService(db)

    bundles, total = await service.list_bundles(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        featured=featured,
        include_inactive=not active_only,
    )

    return PaginatedResponse(
        items=[BundleResponse.model_validate(b) for b in bundles],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{bundle_id}", response_model=BundleWithItems)
async def get_bundle(
    bundle_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.BUNDLES_READ)),
) -> BundleWithItems:
    """Recupere les details d'un bundle avec ses items."""
    service = BundleService(db)
    bundle = await service.get_bundle(bundle_id, current_user.tenant_id)
    return BundleWithItems.model_validate(bundle)


@router.post("", response_model=BundleResponse, status_code=status.HTTP_201_CREATED)
async def create_bundle(
    data: BundleCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.BUNDLES_WRITE)),
) -> BundleResponse:
    """Cree un nouveau bundle (admin uniquement)."""
    service = BundleService(db)
    try:
        bundle = await service.create_bundle(data, current_user.tenant_id)
        await db.commit()
        await db.refresh(bundle)
        return BundleResponse.model_validate(bundle)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in create_bundle")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating bundle: {str(e)}",
        )


@router.patch("/{bundle_id}", response_model=BundleResponse)
async def update_bundle(
    bundle_id: int,
    data: BundleUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.BUNDLES_WRITE)),
) -> BundleResponse:
    """Met a jour un bundle (admin uniquement)."""
    service = BundleService(db)
    try:
        bundle = await service.update_bundle(bundle_id, data, current_user.tenant_id)
        await db.commit()
        await db.refresh(bundle)
        return BundleResponse.model_validate(bundle)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in update_bundle")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating bundle: {str(e)}",
        )


@router.delete("/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bundle(
    bundle_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.BUNDLES_DELETE)),
) -> None:
    """Soft delete un bundle (admin uniquement)."""
    service = BundleService(db)
    try:
        await service.delete_bundle(bundle_id, current_user.tenant_id)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in delete_bundle")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting bundle: {str(e)}",
        )


@router.post(
    "/{bundle_id}/items",
    response_model=BundleItemResponse,
    status_code=status.HTTP_201_CREATED
)
async def add_bundle_item(
    bundle_id: int,
    data: BundleItemCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.BUNDLES_WRITE)),
) -> BundleItemResponse:
    """Ajoute un produit au bundle (admin uniquement)."""
    service = BundleService(db)
    try:
        item = await service.add_item(bundle_id, data, current_user.tenant_id)
        await db.commit()
        await db.refresh(item)
        reloaded = await db.get(BundleItemModel, item.id, options=[joinedload(BundleItemModel.product)])
        return BundleItemResponse.model_validate(reloaded)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in add_bundle_item")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding item: {str(e)}",
        )


@router.patch("/{bundle_id}/items/{item_id}", response_model=BundleItemResponse)
async def update_bundle_item(
    bundle_id: int,
    item_id: int,
    data: BundleItemUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.BUNDLES_WRITE)),
) -> BundleItemResponse:
    """Met a jour un item du bundle (admin uniquement)."""
    service = BundleService(db)
    try:
        item = await service.update_item(bundle_id, item_id, data, current_user.tenant_id)
        await db.commit()
        await db.refresh(item)
        reloaded = await db.get(BundleItemModel, item.id, options=[joinedload(BundleItemModel.product)])
        return BundleItemResponse.model_validate(reloaded)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in update_bundle_item")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating item: {str(e)}",
        )


@router.delete("/{bundle_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_bundle_item(
    bundle_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.BUNDLES_DELETE)),
) -> None:
    """Supprime un item du bundle (admin uniquement)."""
    service = BundleService(db)
    try:
        await service.remove_item(bundle_id, item_id, current_user.tenant_id)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in remove_bundle_item")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing item: {str(e)}",
        )


@router.get("/{bundle_id}/calculate-price", response_model=BundlePriceResponse)
async def calculate_bundle_price(
    bundle_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.BUNDLES_READ)),
) -> BundlePriceResponse:
    """Calcule le prix individuel vs prix bundle."""
    service = BundleService(db)
    result = await service.calculate_price(bundle_id, current_user.tenant_id)
    return BundlePriceResponse(**result)
