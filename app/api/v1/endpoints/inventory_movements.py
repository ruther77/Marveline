"""Endpoints CRUD pour les mouvements de stock (départs/retours)."""
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.services.inventory_movement import AsyncMovementService
from app.schemas.inventory_movement import (
    MovementCreate,
    MovementUpdate,
    MovementResponse,
    MovementListItem,
    MovementStatistics,
    MovementItemCreate,
    MovementItemUpdate,
    MovementItemResponse,
    AgendaView,
)
from app.schemas.common import PaginatedResponse, PaginationParams


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory-movements", tags=["Inventory Movements"])


# ── List / Query endpoints ────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[MovementListItem])
async def list_movements(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    movement_type: Optional[str] = Query(None, description="Filtrer par type (departure/return)"),
    movement_status: Optional[str] = Query(None, alias="status", description="Filtrer par statut"),
    event_id: Optional[int] = Query(None, description="Filtrer par événement"),
    reservation_id: Optional[int] = Query(None, description="Filtrer par réservation"),
    product_id: Optional[int] = Query(None, description="Filtrer par produit"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> PaginatedResponse[MovementListItem]:
    """Liste les mouvements avec pagination et filtres."""
    service = AsyncMovementService(db)
    movements, total = await service.list_movements(
        tenant_id=current_user.tenant_id,
        skip=skip,
        limit=limit,
        movement_type=movement_type,
        movement_status=movement_status,
        event_id=event_id,
        reservation_id=reservation_id,
        product_id=product_id,
    )

    # items_count est déjà calculé en SQL par le repository (évite N+1)
    items = [MovementListItem.model_validate(m) for m in movements]

    return PaginatedResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/late", response_model=PaginatedResponse[MovementListItem])
async def list_late_movements(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> PaginatedResponse[MovementListItem]:
    """Liste les mouvements en retard."""
    service = AsyncMovementService(db)
    movements, total = await service.get_late_movements(
        current_user.tenant_id, skip=pagination.skip, limit=pagination.limit,
    )
    return PaginatedResponse(
        items=[MovementListItem.model_validate(m) for m in movements],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/pending-inspections", response_model=PaginatedResponse[MovementListItem])
async def list_pending_inspections(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> PaginatedResponse[MovementListItem]:
    """Liste les mouvements avec inspection en attente."""
    service = AsyncMovementService(db)
    movements, total = await service.get_pending_inspections(
        current_user.tenant_id, skip=pagination.skip, limit=pagination.limit,
    )
    return PaginatedResponse(
        items=[MovementListItem.model_validate(m) for m in movements],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/statistics", response_model=MovementStatistics)
async def get_statistics(
    start_date: date | None = Query(None, description="Date de début (filtre scheduled_date)"),
    end_date: date | None = Query(None, description="Date de fin (filtre scheduled_date)"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> MovementStatistics:
    """Retourne les statistiques des mouvements."""
    service = AsyncMovementService(db)
    stats = await service.get_statistics(
        current_user.tenant_id,
        start_date=start_date,
        end_date=end_date,
    )
    return MovementStatistics(**stats)


@router.get("/today", status_code=410, deprecated=True)
async def get_today_movements_gone() -> dict:
    """RETIRED — Use GET /planning/today instead."""
    raise HTTPException(status_code=410, detail="Gone. Use GET /planning/today")


@router.get("/agenda", status_code=410, deprecated=True)
async def get_agenda_gone() -> dict:
    """RETIRED — Use GET /planning/timeline instead."""
    raise HTTPException(status_code=410, detail="Gone. Use GET /planning/timeline")


# ── Single movement CRUD ──────────────────────────────────────────────


@router.get("/{movement_id}", response_model=MovementResponse)
async def get_movement(
    movement_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> MovementResponse:
    """Récupère les détails d'un mouvement."""
    service = AsyncMovementService(db)
    movement = await service.get_movement(movement_id, current_user.tenant_id)
    return MovementResponse.model_validate(movement)


@router.post("", response_model=MovementResponse, status_code=status.HTTP_201_CREATED)
async def create_movement(
    data: MovementCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> MovementResponse:
    """Crée un nouveau mouvement avec ses articles (inventory:write)."""
    service = AsyncMovementService(db)

    try:
        movement = await service.create_movement(
            tenant_id=current_user.tenant_id,
            movement_type=data.movement_type.value,
            scheduled_date=data.scheduled_date,
            items=[item.model_dump() for item in data.items],
            event_id=data.event_id,
            reservation_id=data.reservation_id,
            delivery_method=data.delivery_method.value if data.delivery_method else None,
            delivery_address=data.delivery_address,
            delivery_notes=data.delivery_notes,
        )
        await db.commit()
        # Recharger avec relations eager-loaded (évite MissingGreenlet sur items.units)
        movement = await service.get_movement(movement.id, current_user.tenant_id)
        return MovementResponse.model_validate(movement)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in create_movement")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating movement: {str(e)}",
        )


@router.patch("/{movement_id}", response_model=MovementResponse)
async def update_movement(
    movement_id: int,
    data: MovementUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> MovementResponse:
    """Met à jour un mouvement existant (inventory:write, PATCH partiel)."""
    service = AsyncMovementService(db)

    try:
        update_data = data.model_dump(exclude_unset=True)

        # Convert enums to values
        if "status" in update_data and update_data["status"] is not None:
            update_data["status"] = update_data["status"].value if hasattr(update_data["status"], "value") else update_data["status"]
        if "delivery_method" in update_data and update_data["delivery_method"] is not None:
            update_data["delivery_method"] = update_data["delivery_method"].value if hasattr(update_data["delivery_method"], "value") else update_data["delivery_method"]
        if "inspection_status" in update_data and update_data["inspection_status"] is not None:
            update_data["inspection_status"] = update_data["inspection_status"].value if hasattr(update_data["inspection_status"], "value") else update_data["inspection_status"]

        movement = await service.update_movement(
            movement_id,
            current_user.tenant_id,
            **update_data,
        )
        await db.commit()
        # Recharger avec relations eager-loaded (évite MissingGreenlet sur items.units)
        movement = await service.get_movement(movement_id, current_user.tenant_id)
        return MovementResponse.model_validate(movement)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in update_movement")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating movement: {str(e)}",
        )


@router.delete("/{movement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movement(
    movement_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> None:
    """Supprime un mouvement (soft delete, inventory:write)."""
    service = AsyncMovementService(db)

    try:
        await service.delete_movement(movement_id, current_user.tenant_id)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in delete_movement")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting movement: {str(e)}",
        )


# ── Status actions ────────────────────────────────────────────────────


@router.patch("/{movement_id}/complete", response_model=MovementResponse)
async def complete_movement(
    movement_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> MovementResponse:
    """Marque un mouvement comme complété (inventory:write)."""
    service = AsyncMovementService(db)

    try:
        movement = await service.complete_movement(movement_id, current_user.tenant_id)
        await db.commit()
        # Recharger avec relations eager-loaded (évite MissingGreenlet sur items.units)
        movement = await service.get_movement(movement_id, current_user.tenant_id)
        return MovementResponse.model_validate(movement)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in complete_movement")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error completing movement: {str(e)}",
        )


# ── Items management ──────────────────────────────────────────────────


@router.get("/{movement_id}/items", response_model=list[MovementItemResponse])
async def list_items(
    movement_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> list[MovementItemResponse]:
    """Liste les articles d'un mouvement."""
    service = AsyncMovementService(db)
    movement = await service.get_movement(movement_id, current_user.tenant_id)
    return [MovementItemResponse.model_validate(item) for item in movement.items]


@router.post("/{movement_id}/items", response_model=MovementItemResponse, status_code=status.HTTP_201_CREATED)
async def add_item(
    movement_id: int,
    data: MovementItemCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> MovementItemResponse:
    """Ajoute un article à un mouvement (inventory:write)."""
    service = AsyncMovementService(db)

    try:
        item = await service.add_item(
            movement_id=movement_id,
            tenant_id=current_user.tenant_id,
            event_item_id=data.event_item_id,
            product_id=data.product_id,
            variant_id=data.variant_id,
            quantity_expected=data.quantity_expected,
            condition=data.condition.value if data.condition else None,
            condition_notes=data.condition_notes,
        )
        item_id_created = item.id
        await db.commit()
        # Recharger le movement avec relations eager-loaded puis extraire l'item
        movement = await service.get_movement(movement_id, current_user.tenant_id)
        item = next(i for i in movement.items if i.id == item_id_created)
        return MovementItemResponse.model_validate(item)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in add_item")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding item: {str(e)}",
        )


@router.patch("/{movement_id}/items/{item_id}", response_model=MovementItemResponse)
async def update_item(
    movement_id: int,
    item_id: int,
    data: MovementItemUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> MovementItemResponse:
    """Met à jour un article de mouvement (inventory:write)."""
    service = AsyncMovementService(db)

    try:
        item = await service.update_item(
            item_id=item_id,
            tenant_id=current_user.tenant_id,
            quantity_actual=data.quantity_actual,
            condition=data.condition.value if data.condition else None,
            condition_notes=data.condition_notes,
        )
        # Validation cohérence: vérifier que l'item appartient bien au movement
        if item.movement_id != movement_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found in this movement",
            )
        await db.commit()
        # Recharger le movement avec relations eager-loaded puis extraire l'item
        movement = await service.get_movement(movement_id, current_user.tenant_id)
        item = next(i for i in movement.items if i.id == item_id)
        return MovementItemResponse.model_validate(item)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in update_item")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating item: {str(e)}",
        )


@router.delete("/{movement_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(
    movement_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> None:
    """Supprime un article d'un mouvement (inventory:write)."""
    service = AsyncMovementService(db)

    try:
        # Récupérer l'item et valider la cohérence movement
        item = await service.item_repo.get_by_id_and_movement(
            item_id, movement_id, current_user.tenant_id
        )
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movement item not found in this movement",
            )
        # Vérifier que le mouvement n'est pas dans un état terminal
        movement = await service.get_movement(movement_id, current_user.tenant_id)
        if movement.status in ("completed", "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot remove items from a {movement.status} movement",
            )
        await service.item_repo.soft_delete(item)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in remove_item")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing item: {str(e)}",
        )
