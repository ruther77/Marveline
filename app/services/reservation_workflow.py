"""Service orchestrateur pour workflows Réservation + Inventory.

Résout la dépendance circulaire reservation.py ↔ inventory_movement.py
en centralisant les opérations cross-domain.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.constants import MovementType, ReservationStatus
from app.models.reservation import Reservation
from app.models.inventory_movement import InventoryMovement

logger = logging.getLogger(__name__)


class ReservationWorkflowService:
    """Orchestre les workflows entre Réservations et Mouvements d'inventaire."""

    def __init__(self, db: Session):
        self.db = db

    def auto_generate_departure_movement(
        self,
        reservation: Reservation,
        tenant_id: int
    ) -> None:
        """Auto-crée un mouvement DEPARTURE lors de la confirmation d'une réservation.

        Idempotent : si un mouvement DEPARTURE existe déjà pour cette réservation,
        l'opération est ignorée silencieusement (log warning).

        Args:
            reservation: Réservation confirmée (avec lines chargées)
            tenant_id: ID du tenant
        """
        from app.services.inventory_movement import MovementService

        movement_service = MovementService(self.db)

        # Idempotence : vérifier qu'aucun DEPARTURE n'existe déjà
        existing, count = movement_service.list_movements(
            tenant_id=tenant_id,
            reservation_id=reservation.id,
            movement_type=MovementType.DEPARTURE.value,
        )
        if count > 0:
            logger.warning(
                "Departure movement already exists for reservation %s",
                reservation.reference,
            )
            return

        # Construire les items depuis les lignes de réservation
        items = [
            {"product_id": line.product_id, "quantity_expected": line.quantity}
            for line in reservation.lines
        ]

        scheduled_dt = datetime.combine(
            reservation.delivery_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )

        movement_service.create_movement(
            tenant_id=tenant_id,
            movement_type=MovementType.DEPARTURE.value,
            scheduled_date=scheduled_dt,
            items=items,
            reservation_id=reservation.id,
            delivery_address=reservation.event_location,
        )
        logger.info(
            "Auto-generated departure movement for reservation %s (tenant=%d)",
            reservation.reference,
            tenant_id,
        )

    def update_reservation_on_movement_complete(
        self,
        movement: InventoryMovement
    ) -> None:
        """Met à jour le statut réservation quand un mouvement lié est complété.

        Args:
            movement: Mouvement complété (avec reservation_id)
        """
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
