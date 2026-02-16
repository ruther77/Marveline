"""Repositories pour InventoryMovement et MovementItem."""
from datetime import date
from typing import Any, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.constants import MovementStatus, InspectionStatus
from app.models.inventory_movement import InventoryMovement, MovementItem
from app.repositories.base import BaseRepository


class MovementRepository(BaseRepository[InventoryMovement]):
    """Repository pour les mouvements de stock."""

    def __init__(self, db: Session):
        super().__init__(db, InventoryMovement)

    def list_by_status(
        self,
        tenant_id: int,
        status: str,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[InventoryMovement], int]:
        """Liste les mouvements filtrés par statut."""
        return self.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters={"status": status},
            order_by="scheduled_date",
        )

    def list_late(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[InventoryMovement], int]:
        """Liste les mouvements en retard."""
        return self.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters={"status": MovementStatus.LATE.value},
            order_by="scheduled_date",
        )

    def list_pending_inspections(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[InventoryMovement], int]:
        """Liste les mouvements avec inspection en attente."""
        return self.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters={"inspection_status": InspectionStatus.PENDING.value},
        )

    def get_statistics(
        self,
        tenant_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Calcule les statistiques des mouvements pour un tenant.

        Returns:
            Dict avec total_movements, scheduled, in_transit, completed, late,
            cancelled, total_damage_fees
        """
        conditions = [
            InventoryMovement.tenant_id == tenant_id,
            InventoryMovement.is_active == True,  # noqa: E712
        ]
        if start_date is not None:
            conditions.append(InventoryMovement.scheduled_date >= start_date)
        if end_date is not None:
            conditions.append(InventoryMovement.scheduled_date <= end_date)

        base_filter = and_(*conditions)

        # Compter par statut
        status_counts = self.db.execute(
            select(
                InventoryMovement.status,
                func.count().label("cnt"),
            )
            .where(base_filter)
            .group_by(InventoryMovement.status)
        ).all()

        stats: dict[str, Any] = {
            "total_movements": 0,
            "scheduled": 0,
            "in_transit": 0,
            "completed": 0,
            "late": 0,
            "cancelled": 0,
        }
        for status, cnt in status_counts:
            stats[status] = cnt
            stats["total_movements"] += cnt

        # Total damage fees
        total_fees = self.db.execute(
            select(func.coalesce(func.sum(InventoryMovement.damage_fee), 0))
            .where(base_filter)
        ).scalar()
        stats["total_damage_fees"] = total_fees or 0

        return stats

    def list_by_event(
        self,
        tenant_id: int,
        event_id: int,
    ) -> list[InventoryMovement]:
        """Liste les mouvements pour un événement donné."""
        query = (
            select(InventoryMovement)
            .where(
                and_(
                    InventoryMovement.tenant_id == tenant_id,
                    InventoryMovement.event_id == event_id,
                    InventoryMovement.is_active == True,  # noqa: E712
                )
            )
            .order_by(InventoryMovement.scheduled_date)
        )
        result = self.db.execute(query).scalars().all()
        return list(result)


class MovementItemRepository(BaseRepository[MovementItem]):
    """Repository pour les articles de mouvement."""

    def __init__(self, db: Session):
        super().__init__(db, MovementItem)

    def list_by_movement(
        self,
        tenant_id: int,
        movement_id: int,
    ) -> list[MovementItem]:
        """Liste les articles d'un mouvement."""
        query = (
            select(MovementItem)
            .where(
                and_(
                    MovementItem.tenant_id == tenant_id,
                    MovementItem.movement_id == movement_id,
                )
            )
            .order_by(MovementItem.id)
        )
        result = self.db.execute(query).scalars().all()
        return list(result)

    def get_by_id_and_movement(
        self,
        item_id: int,
        movement_id: int,
        tenant_id: int,
    ) -> Optional[MovementItem]:
        """Récupère un article par ID avec vérification du mouvement parent."""
        query = (
            select(MovementItem)
            .where(
                and_(
                    MovementItem.id == item_id,
                    MovementItem.movement_id == movement_id,
                    MovementItem.tenant_id == tenant_id,
                )
            )
        )
        return self.db.execute(query).scalar_one_or_none()

    def count_by_movement(
        self,
        tenant_id: int,
        movement_id: int,
    ) -> int:
        """Compte les articles d'un mouvement."""
        result = self.db.execute(
            select(func.count())
            .select_from(MovementItem)
            .where(
                and_(
                    MovementItem.tenant_id == tenant_id,
                    MovementItem.movement_id == movement_id,
                )
            )
        ).scalar()
        return result or 0
