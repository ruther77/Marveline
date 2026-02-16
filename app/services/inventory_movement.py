"""Service métier pour les mouvements de stock."""
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants import MovementStatus, MovementType, ReservationStatus

logger = logging.getLogger(__name__)
from app.models.inventory_movement import InventoryMovement, MovementItem
from app.repositories.inventory_movement import (
    MovementItemRepository,
    MovementRepository,
)


# Transitions de statut autorisées
VALID_TRANSITIONS: dict[str, set[str]] = {
    MovementStatus.SCHEDULED.value: {
        MovementStatus.IN_TRANSIT.value,
        MovementStatus.CANCELLED.value,
    },
    MovementStatus.IN_TRANSIT.value: {
        MovementStatus.COMPLETED.value,
        MovementStatus.LATE.value,
        MovementStatus.CANCELLED.value,
    },
    MovementStatus.LATE.value: {
        MovementStatus.COMPLETED.value,
        MovementStatus.CANCELLED.value,
    },
    MovementStatus.COMPLETED.value: set(),
    MovementStatus.CANCELLED.value: set(),
}


class MovementService:
    """Service métier pour gestion des mouvements de stock.

    Responsibilities:
        - CRUD mouvements avec validation
        - Gestion des items de mouvement
        - Transitions de statut (workflow)
        - Statistiques et requêtes spécialisées

    Transactions:
        - Pas de commit automatique
        - Rollback automatique en cas d'exception
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = MovementRepository(db)
        self.item_repo = MovementItemRepository(db)

    # ── CRUD Movements ───────────────────────────────────────────────

    def create_movement(
        self,
        tenant_id: int,
        movement_type: str,
        scheduled_date: datetime,
        items: list[dict[str, Any]],
        event_id: Optional[int] = None,
        reservation_id: Optional[int] = None,
        delivery_method: Optional[str] = None,
        delivery_address: Optional[str] = None,
        delivery_notes: Optional[str] = None,
    ) -> InventoryMovement:
        """Crée un mouvement avec ses items.

        Raises:
            HTTPException 400: Si données invalides ou aucun item
        """
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one item is required",
            )

        # Valider movement_type
        valid_types = {mt.value for mt in MovementType}
        if movement_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid movement_type: {movement_type}",
            )

        movement = InventoryMovement(
            tenant_id=tenant_id,
            event_id=event_id,
            reservation_id=reservation_id,
            movement_type=movement_type,
            scheduled_date=scheduled_date,
            status=MovementStatus.SCHEDULED.value,
            delivery_method=delivery_method,
            delivery_address=delivery_address,
            delivery_notes=delivery_notes,
            damage_fee=0,
        )
        movement = self.repo.create(movement)

        # Créer les items
        for item_data in items:
            item = MovementItem(
                tenant_id=tenant_id,
                movement_id=movement.id,
                event_item_id=item_data.get("event_item_id"),
                product_id=item_data.get("product_id"),
                product_variation_id=item_data.get("product_variation_id"),
                quantity_expected=item_data["quantity_expected"],
                condition=item_data.get("condition"),
                condition_notes=item_data.get("condition_notes"),
            )
            self.item_repo.create(item)

        # Refresh pour charger les items via relationship
        self.db.refresh(movement)
        return movement

    def get_movement(
        self,
        movement_id: int,
        tenant_id: int,
    ) -> InventoryMovement:
        """Récupère un mouvement par ID.

        Raises:
            HTTPException 404: Si mouvement non trouvé
        """
        movement = self.repo.get_by_id(movement_id, tenant_id)
        if not movement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movement not found",
            )
        return movement

    def list_movements(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 20,
        movement_type: Optional[str] = None,
        movement_status: Optional[str] = None,
        event_id: Optional[int] = None,
        reservation_id: Optional[int] = None,
    ) -> tuple[list[InventoryMovement], int]:
        """Liste les mouvements avec filtres et pagination."""
        filters: dict[str, Any] = {}
        if movement_type:
            filters["movement_type"] = movement_type
        if movement_status:
            filters["status"] = movement_status
        if event_id is not None:
            filters["event_id"] = event_id
        if reservation_id is not None:
            filters["reservation_id"] = reservation_id

        return self.repo.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters=filters if filters else None,
            order_by="scheduled_date",
        )

    def update_movement(
        self,
        movement_id: int,
        tenant_id: int,
        **kwargs: Any,
    ) -> InventoryMovement:
        """Met à jour un mouvement (PATCH partiel).

        Raises:
            HTTPException 404: Si mouvement non trouvé
            HTTPException 400: Si transition de statut invalide
        """
        movement = self.get_movement(movement_id, tenant_id)

        # Valider transition de statut si demandée
        new_status = kwargs.get("status")
        if new_status and new_status != movement.status:
            allowed = VALID_TRANSITIONS.get(movement.status, set())
            if new_status not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Invalid status transition: {movement.status} → {new_status}. "
                        f"Allowed: {', '.join(sorted(allowed)) or 'none'}"
                    ),
                )

        # Appliquer les champs modifiables
        updatable_fields = {
            "scheduled_date",
            "actual_date",
            "status",
            "delivery_method",
            "delivery_address",
            "delivery_notes",
            "handled_by_user_id",
            "inspection_status",
            "inspection_notes",
            "damage_fee",
        }

        for field, value in kwargs.items():
            if field in updatable_fields and value is not None:
                setattr(movement, field, value)

        return self.repo.update(movement)

    def delete_movement(
        self,
        movement_id: int,
        tenant_id: int,
    ) -> bool:
        """Supprime un mouvement (soft delete).

        Raises:
            HTTPException 404: Si mouvement non trouvé
            HTTPException 400: Si mouvement déjà complété
        """
        movement = self.get_movement(movement_id, tenant_id)

        if movement.status == MovementStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete a completed movement",
            )

        success = self.repo.soft_delete(movement_id, tenant_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movement not found",
            )
        return True

    # ── Status Actions ───────────────────────────────────────────────

    def complete_movement(
        self,
        movement_id: int,
        tenant_id: int,
    ) -> InventoryMovement:
        """Marque un mouvement comme complété.

        Sets actual_date to now and status to completed.
        If movement is linked to a reservation, updates reservation status.

        Raises:
            HTTPException 404: Si mouvement non trouvé
            HTTPException 400: Si transition de statut invalide
        """
        movement = self.update_movement(
            movement_id,
            tenant_id,
            status=MovementStatus.COMPLETED.value,
            actual_date=datetime.now(timezone.utc),
        )

        # Callback : mettre à jour la réservation liée si applicable
        self._update_reservation_on_complete(movement)

        return movement

    def _update_reservation_on_complete(self, movement: InventoryMovement) -> None:
        """Met à jour le statut réservation quand un mouvement lié est complété."""
        if not movement.reservation_id:
            return

        from app.services.reservation import ReservationService

        reservation_service = ReservationService(self.db)
        reservation = reservation_service.repo.get_by_id(
            movement.reservation_id, movement.tenant_id
        )
        if not reservation:
            logger.warning(
                "Reservation %d not found for movement %d",
                movement.reservation_id,
                movement.id,
            )
            return

        if movement.movement_type == MovementType.DEPARTURE.value:
            if reservation.status == ReservationStatus.CONFIRMED:
                reservation.status = ReservationStatus.DELIVERED
                reservation_service.repo.update(reservation)
                logger.info(
                    "Reservation %s -> delivered (departure movement %d completed)",
                    reservation.reference,
                    movement.id,
                )

        elif movement.movement_type == MovementType.RETURN.value:
            if reservation.status == ReservationStatus.DELIVERED:
                reservation.status = ReservationStatus.RETURNED
                reservation_service.repo.update(reservation)
                logger.info(
                    "Reservation %s -> returned (return movement %d completed)",
                    reservation.reference,
                    movement.id,
                )

    # ── Special Queries ──────────────────────────────────────────────

    def get_late_movements(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[InventoryMovement], int]:
        """Liste les mouvements en retard."""
        return self.repo.list_late(tenant_id, skip, limit)

    def get_pending_inspections(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[InventoryMovement], int]:
        """Liste les mouvements avec inspection en attente."""
        return self.repo.list_pending_inspections(tenant_id, skip, limit)

    def get_statistics(
        self,
        tenant_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Retourne les statistiques des mouvements."""
        return self.repo.get_statistics(tenant_id, start_date=start_date, end_date=end_date)

    # ── Items Management ─────────────────────────────────────────────

    def add_item(
        self,
        movement_id: int,
        tenant_id: int,
        event_item_id: Optional[int] = None,
        product_id: Optional[int] = None,
        product_variation_id: Optional[int] = None,
        quantity_expected: int = 1,
        condition: Optional[str] = None,
        condition_notes: Optional[str] = None,
    ) -> MovementItem:
        """Ajoute un article à un mouvement.

        Raises:
            HTTPException 404: Si mouvement non trouvé
            HTTPException 400: Si mouvement complété/annulé
        """
        movement = self.get_movement(movement_id, tenant_id)

        if movement.status in (
            MovementStatus.COMPLETED.value,
            MovementStatus.CANCELLED.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add items to a completed or cancelled movement",
            )

        item = MovementItem(
            tenant_id=tenant_id,
            movement_id=movement_id,
            event_item_id=event_item_id,
            product_id=product_id,
            product_variation_id=product_variation_id,
            quantity_expected=quantity_expected,
            condition=condition,
            condition_notes=condition_notes,
        )
        return self.item_repo.create(item)

    def update_item(
        self,
        item_id: int,
        tenant_id: int,
        quantity_actual: Optional[int] = None,
        condition: Optional[str] = None,
        condition_notes: Optional[str] = None,
    ) -> MovementItem:
        """Met à jour un article de mouvement.

        Raises:
            HTTPException 404: Si article non trouvé
        """
        item = self.item_repo.get_by_id(item_id, tenant_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movement item not found",
            )

        if quantity_actual is not None:
            item.quantity_actual = quantity_actual
        if condition is not None:
            item.condition = condition
        if condition_notes is not None:
            item.condition_notes = condition_notes

        return self.item_repo.update(item)

    def remove_item(
        self,
        item_id: int,
        tenant_id: int,
    ) -> bool:
        """Supprime un article d'un mouvement.

        Raises:
            HTTPException 404: Si article non trouvé
            HTTPException 400: Si mouvement complété
        """
        item = self.item_repo.get_by_id(item_id, tenant_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movement item not found",
            )

        # Vérifier que le mouvement parent n'est pas complété
        movement = self.repo.get_by_id(item.movement_id, tenant_id)
        if movement and movement.status in (
            MovementStatus.COMPLETED.value,
            MovementStatus.CANCELLED.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove items from a completed or cancelled movement",
            )

        success = self.item_repo.hard_delete(item_id, tenant_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movement item not found",
            )
        return True
