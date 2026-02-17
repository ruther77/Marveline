"""Endpoints CRUD pour les mouvements de stock (départs/retours)."""
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.core.permissions import Permission
from app.models.user import User
from app.services.inventory_movement import MovementService
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
from app.schemas.common import PaginatedResponse


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory-movements", tags=["Inventory Movements"])


# ── List / Query endpoints ────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[MovementListItem])
def list_movements(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    movement_type: Optional[str] = Query(None, description="Filtrer par type (departure/return)"),
    movement_status: Optional[str] = Query(None, alias="status", description="Filtrer par statut"),
    event_id: Optional[int] = Query(None, description="Filtrer par événement"),
    reservation_id: Optional[int] = Query(None, description="Filtrer par réservation"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[MovementListItem]:
    """Liste les mouvements avec pagination et filtres."""
    service = MovementService(db)
    movements, total = service.list_movements(
        tenant_id=current_user.tenant_id,
        skip=skip,
        limit=limit,
        movement_type=movement_type,
        movement_status=movement_status,
        event_id=event_id,
        reservation_id=reservation_id,
    )

    # items_count est déjà calculé en SQL par le repository (évite N+1)
    items = [MovementListItem.model_validate(m) for m in movements]

    return PaginatedResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/late", response_model=list[MovementListItem])
def list_late_movements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MovementListItem]:
    """Liste les mouvements en retard."""
    service = MovementService(db)
    movements, _ = service.get_late_movements(current_user.tenant_id)

    # items_count est déjà calculé en SQL par le repository (évite N+1)
    return [MovementListItem.model_validate(m) for m in movements]


@router.get("/pending-inspections", response_model=list[MovementListItem])
def list_pending_inspections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MovementListItem]:
    """Liste les mouvements avec inspection en attente."""
    service = MovementService(db)
    movements, _ = service.get_pending_inspections(current_user.tenant_id)

    # items_count est déjà calculé en SQL par le repository (évite N+1)
    return [MovementListItem.model_validate(m) for m in movements]


@router.get("/statistics", response_model=MovementStatistics)
def get_statistics(
    start_date: date | None = Query(None, description="Date de début (filtre scheduled_date)"),
    end_date: date | None = Query(None, description="Date de fin (filtre scheduled_date)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MovementStatistics:
    """Retourne les statistiques des mouvements."""
    service = MovementService(db)
    stats = service.get_statistics(
        current_user.tenant_id,
        start_date=start_date,
        end_date=end_date,
    )
    return MovementStatistics(**stats)


@router.get("/agenda", response_model=AgendaView)
def get_agenda(
    start_date: date | None = Query(None, description="Date de début (filtre scheduled_date mouvements)"),
    end_date: date | None = Query(None, description="Date de fin (filtre scheduled_date mouvements)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgendaView:
    """Retourne la vue agenda avec événements/réservations et mouvements associés."""
    service = MovementService(db)
    agenda_data = service.get_agenda(
        current_user.tenant_id,
        start_date=start_date,
        end_date=end_date,
    )
    return AgendaView(**agenda_data)


# ── Single movement CRUD ──────────────────────────────────────────────


@router.get("/{movement_id}", response_model=MovementResponse)
def get_movement(
    movement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MovementResponse:
    """Récupère les détails d'un mouvement."""
    service = MovementService(db)
    movement = service.get_movement(movement_id, current_user.tenant_id)
    return MovementResponse.model_validate(movement)


@router.post("", response_model=MovementResponse, status_code=status.HTTP_201_CREATED)
def create_movement(
    data: MovementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> MovementResponse:
    """Crée un nouveau mouvement avec ses articles (inventory:write)."""
    service = MovementService(db)

    try:
        movement = service.create_movement(
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
        db.commit()
        db.refresh(movement)
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
def update_movement(
    movement_id: int,
    data: MovementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> MovementResponse:
    """Met à jour un mouvement existant (inventory:write, PATCH partiel)."""
    service = MovementService(db)

    try:
        update_data = data.model_dump(exclude_unset=True)

        # Convert enums to values
        if "status" in update_data and update_data["status"] is not None:
            update_data["status"] = update_data["status"].value if hasattr(update_data["status"], "value") else update_data["status"]
        if "delivery_method" in update_data and update_data["delivery_method"] is not None:
            update_data["delivery_method"] = update_data["delivery_method"].value if hasattr(update_data["delivery_method"], "value") else update_data["delivery_method"]
        if "inspection_status" in update_data and update_data["inspection_status"] is not None:
            update_data["inspection_status"] = update_data["inspection_status"].value if hasattr(update_data["inspection_status"], "value") else update_data["inspection_status"]

        movement = service.update_movement(
            movement_id,
            current_user.tenant_id,
            **update_data,
        )
        db.commit()
        db.refresh(movement)
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
def delete_movement(
    movement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> None:
    """Supprime un mouvement (soft delete, inventory:write)."""
    service = MovementService(db)

    try:
        service.delete_movement(movement_id, current_user.tenant_id)
        db.commit()
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
def complete_movement(
    movement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> MovementResponse:
    """Marque un mouvement comme complété (inventory:write)."""
    service = MovementService(db)

    try:
        movement = service.complete_movement(movement_id, current_user.tenant_id)
        db.commit()
        db.refresh(movement)
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


@router.post("/{movement_id}/items", response_model=MovementItemResponse, status_code=status.HTTP_201_CREATED)
def add_item(
    movement_id: int,
    data: MovementItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> MovementItemResponse:
    """Ajoute un article à un mouvement (inventory:write)."""
    service = MovementService(db)

    try:
        item = service.add_item(
            movement_id=movement_id,
            tenant_id=current_user.tenant_id,
            event_item_id=data.event_item_id,
            product_id=data.product_id,
            product_variation_id=data.product_variation_id,
            quantity_expected=data.quantity_expected,
            condition=data.condition.value if data.condition else None,
            condition_notes=data.condition_notes,
        )
        db.commit()
        db.refresh(item)
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
def update_item(
    movement_id: int,
    item_id: int,
    data: MovementItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> MovementItemResponse:
    """Met à jour un article de mouvement (inventory:write)."""
    service = MovementService(db)

    try:
        item = service.update_item(
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
        db.commit()
        db.refresh(item)
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
def remove_item(
    movement_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> None:
    """Supprime un article d'un mouvement (inventory:write)."""
    service = MovementService(db)

    try:
        # Récupérer l'item pour validation
        item_repo = service.item_repo
        item = item_repo.get_by_id(item_id, current_user.tenant_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movement item not found",
            )
        # Validation cohérence: vérifier que l'item appartient bien au movement
        if item.movement_id != movement_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found in this movement",
            )
        service.remove_item(item_id, current_user.tenant_id)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in remove_item")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing item: {str(e)}",
        )
