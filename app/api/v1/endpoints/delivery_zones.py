"""Endpoints CRUD pour les zones de livraison."""
import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.delivery_zone import (
    DeliveryZoneCreate,
    DeliveryZoneResponse,
    DeliveryZoneUpdate,
)
from app.services.delivery_zone import DeliveryZoneService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/delivery-zones", tags=["Delivery Zones"])


@router.get("", response_model=PaginatedResponse[DeliveryZoneResponse])
async def list_delivery_zones(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
) -> PaginatedResponse[DeliveryZoneResponse]:
    """Liste les zones de livraison actives du tenant."""
    service = DeliveryZoneService(db)
    items, total = await service.list_zones(
        current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse[DeliveryZoneResponse](
        items=[DeliveryZoneResponse.model_validate(z) for z in items],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{zone_id}", response_model=DeliveryZoneResponse)
async def get_delivery_zone(
    zone_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
) -> DeliveryZoneResponse:
    """Récupère les détails d'une zone de livraison."""
    service = DeliveryZoneService(db)
    zone = await service.get_zone(zone_id, current_user.tenant_id)
    return DeliveryZoneResponse.model_validate(zone)


@router.post("", response_model=DeliveryZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_delivery_zone(
    data: DeliveryZoneCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> DeliveryZoneResponse:
    """Crée une zone de livraison (products:write).

    Le code département doit être unique par tenant.
    """
    service = DeliveryZoneService(db)
    zone = await service.create_zone(data, current_user.tenant_id)
    await db.commit()
    await db.refresh(zone)
    return DeliveryZoneResponse.model_validate(zone)


@router.patch("/{zone_id}", response_model=DeliveryZoneResponse)
async def update_delivery_zone(
    zone_id: int,
    data: DeliveryZoneUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> DeliveryZoneResponse:
    """Met à jour une zone de livraison (products:write, PATCH partiel)."""
    service = DeliveryZoneService(db)
    zone = await service.update_zone(zone_id, data, current_user.tenant_id)
    await db.commit()
    await db.refresh(zone)
    return DeliveryZoneResponse.model_validate(zone)


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_delivery_zone(
    zone_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.PRODUCTS_WRITE)),
) -> None:
    """Supprime (soft delete) une zone de livraison (products:write)."""
    service = DeliveryZoneService(db)
    await service.delete_zone(zone_id, current_user.tenant_id)
    await db.commit()
