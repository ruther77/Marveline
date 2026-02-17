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

        # Callback : mettre à jour la réservation liée via workflow (évite circular dependency)
        from app.services.reservation_workflow import ReservationWorkflowService
        workflow = ReservationWorkflowService(self.db)
        workflow.update_reservation_on_movement_complete(movement)

        # Notifications best-effort après mise à jour
        if movement.reservation_id:
            from app.services.reservation import ReservationService
            reservation_service = ReservationService(self.db)
            reservation = reservation_service.repo.get_by_id(
                movement.reservation_id, movement.tenant_id
            )
            if reservation:
                if movement.movement_type == MovementType.DEPARTURE.value:
                    self._notify_delivery_completed(reservation, movement)
                elif movement.movement_type == MovementType.RETURN.value:
                    self._notify_return_completed(reservation, movement)

        return movement

    # ── Notification Hooks (best-effort) ────────────────────────────

    def _notify_delivery_completed(self, reservation, movement: InventoryMovement) -> None:
        """Best-effort : notification livraison au client (async via Celery)."""
        try:
            from app.services.reservation import ReservationService
            from app.tasks.notifications import send_delivery_completed_email

            full_res = ReservationService(self.db).repo.get_by_id_with_relations(
                reservation.id, reservation.tenant_id
            )
            if not full_res or not full_res.customer or not full_res.customer.email:
                return
            send_delivery_completed_email.delay(
                email=full_res.customer.email,
                customer_name=full_res.customer.display_name,
                reservation_reference=reservation.reference,
                delivery_address=movement.delivery_address or reservation.event_location or "",
                delivery_date_iso=str(movement.actual_date),
            )
        except Exception:
            logger.exception("Notification failed for delivery movement %d", movement.id)

    def _notify_return_completed(self, reservation, movement: InventoryMovement) -> None:
        """Best-effort : notification retour au client (async via Celery)."""
        try:
            from app.services.reservation import ReservationService
            from app.tasks.notifications import send_return_completed_email

            full_res = ReservationService(self.db).repo.get_by_id_with_relations(
                reservation.id, reservation.tenant_id
            )
            if not full_res or not full_res.customer or not full_res.customer.email:
                return
            send_return_completed_email.delay(
                email=full_res.customer.email,
                customer_name=full_res.customer.display_name,
                reservation_reference=reservation.reference,
                return_date_iso=str(movement.actual_date),
            )
        except Exception:
            logger.exception("Notification failed for return movement %d", movement.id)

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

    def get_agenda(
        self,
        tenant_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Retourne la vue agenda avec événements/réservations et leurs mouvements.

        Args:
            tenant_id: ID du tenant
            start_date: Date début plage (filtre sur scheduled_date des mouvements)
            end_date: Date fin plage (filtre sur scheduled_date des mouvements)

        Returns:
            Dict contenant date_start, date_end, events[], total_departures, total_returns
        """
        from app.repositories.reservation import ReservationRepository
        from app.models.customer import Customer

        reservation_repo = ReservationRepository(self.db)

        # Déterminer dates
        if not start_date:
            start_date = date.today()
        if not end_date:
            from datetime import timedelta
            end_date = start_date + timedelta(days=30)

        # Récupérer toutes les réservations avec leurs mouvements dans la plage
        # Filtre sur delivery_date/return_date pour inclure réservations pertinentes
        reservations = (
            self.db.query(reservation_repo.model_class)
            .filter(
                reservation_repo.model_class.tenant_id == tenant_id,
                # Réservation dont delivery_date ou return_date dans la plage
                (
                    (reservation_repo.model_class.delivery_date >= start_date) &
                    (reservation_repo.model_class.delivery_date <= end_date)
                ) | (
                    (reservation_repo.model_class.return_date >= start_date) &
                    (reservation_repo.model_class.return_date <= end_date)
                )
            )
            .join(Customer, reservation_repo.model_class.customer_id == Customer.id)
            .all()
        )

        # Construire events avec mouvements
        events = []
        total_departures = 0
        total_returns = 0

        for reservation in reservations:
            # Trouver mouvements departure et return pour cette réservation
            departure_movement = None
            return_movement = None

            for movement in reservation.movements:
                if not movement.is_active:
                    continue

                # Vérifier si dans la plage de dates
                if movement.scheduled_date.date() < start_date or movement.scheduled_date.date() > end_date:
                    continue

                if movement.movement_type == MovementType.DEPARTURE.value:
                    departure_movement = movement
                    total_departures += 1
                elif movement.movement_type == MovementType.RETURN.value:
                    return_movement = movement
                    total_returns += 1

            # Construire AgendaItem
            event_item = {
                "event_id": None,  # Legacy, pas de table events
                "reservation_id": reservation.id,
                "customer_name": f"{reservation.customer.first_name} {reservation.customer.last_name}".strip(),
                "event_type": reservation.event_location or "",
                "event_date": reservation.event_date.isoformat(),
                "rental_start_date": reservation.delivery_date.isoformat(),
                "rental_end_date": reservation.return_date.isoformat(),
                "status": reservation.status,
                "departure": None,
                "return_movement": None,
            }

            # Ajouter mouvements si existants
            if departure_movement:
                event_item["departure"] = {
                    "id": departure_movement.id,
                    "tenant_id": departure_movement.tenant_id,
                    "event_id": departure_movement.event_id,
                    "reservation_id": departure_movement.reservation_id,
                    "movement_type": departure_movement.movement_type,
                    "scheduled_date": departure_movement.scheduled_date.isoformat(),
                    "actual_date": departure_movement.actual_date.isoformat() if departure_movement.actual_date else None,
                    "status": departure_movement.status,
                    "delivery_method": departure_movement.delivery_method,
                    "items_count": len(departure_movement.items) if hasattr(departure_movement, 'items') else 0,
                    "created_at": departure_movement.created_at.isoformat(),
                    "updated_at": departure_movement.updated_at.isoformat(),
                }

            if return_movement:
                event_item["return_movement"] = {
                    "id": return_movement.id,
                    "tenant_id": return_movement.tenant_id,
                    "event_id": return_movement.event_id,
                    "reservation_id": return_movement.reservation_id,
                    "movement_type": return_movement.movement_type,
                    "scheduled_date": return_movement.scheduled_date.isoformat(),
                    "actual_date": return_movement.actual_date.isoformat() if return_movement.actual_date else None,
                    "status": return_movement.status,
                    "delivery_method": return_movement.delivery_method,
                    "items_count": len(return_movement.items) if hasattr(return_movement, 'items') else 0,
                    "created_at": return_movement.created_at.isoformat(),
                    "updated_at": return_movement.updated_at.isoformat(),
                }

            events.append(event_item)

        return {
            "date_start": start_date.isoformat(),
            "date_end": end_date.isoformat(),
            "events": events,
            "total_departures": total_departures,
            "total_returns": total_returns,
        }

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
