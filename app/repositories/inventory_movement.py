"""Repositories pour InventoryMovement et MovementItem."""
from __future__ import annotations

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

    def list(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[dict[str, Any]] = None,
        include_inactive: bool = False,
        order_by: Optional[str] = None
    ) -> tuple[list[InventoryMovement], int]:
        """Liste les mouvements avec items_count calculé en SQL (évite N+1).

        Override de BaseRepository.list() pour ajouter items_count via subquery.

        Args:
            tenant_id: ID du tenant (OBLIGATOIRE)
            skip: Nombre d'éléments à sauter (offset)
            limit: Nombre maximum d'éléments à retourner (max 1000)
            filters: Dictionnaire de filtres additionnels
            include_inactive: Inclure les entités soft-deleted
            order_by: Nom de la colonne pour tri (défaut: "id")

        Returns:
            Tuple (items, total) avec items_count déjà calculé pour chaque mouvement
        """
        # Subquery pour compter les items de chaque mouvement
        items_count_subq = (
            select(func.count(MovementItem.id))
            .where(MovementItem.movement_id == InventoryMovement.id)
            .correlate(InventoryMovement)
            .scalar_subquery()
            .label("items_count")
        )

        # Limite max sécurité
        limit = min(limit, 1000)

        # Compter le total d'abord (via méthode parent)
        total = self.count(tenant_id=tenant_id, filters=filters, include_inactive=include_inactive)

        # Construire query avec items_count
        query = select(InventoryMovement, items_count_subq)
        query = self._apply_tenant_filter(query, tenant_id)

        if not include_inactive:
            query = self._apply_active_filter(query)

        # Filtres additionnels
        if filters:
            for key, value in filters.items():
                if "__" in key:
                    field_name, operator = key.rsplit("__", 1)
                    if not hasattr(InventoryMovement, field_name):
                        continue
                    field = getattr(InventoryMovement, field_name)

                    if operator == "gt":
                        query = query.filter(field > value)
                    elif operator == "gte":
                        query = query.filter(field >= value)
                    elif operator == "lt":
                        query = query.filter(field < value)
                    elif operator == "lte":
                        query = query.filter(field <= value)
                    elif operator == "ne":
                        query = query.filter(field != value)
                    else:
                        continue
                elif hasattr(InventoryMovement, key):
                    query = query.filter(getattr(InventoryMovement, key) == value)

        # Tri
        if order_by and hasattr(InventoryMovement, order_by):
            query = query.order_by(getattr(InventoryMovement, order_by))
        else:
            query = query.order_by(InventoryMovement.id)

        # Pagination
        query = query.offset(skip).limit(limit)

        # Exécuter et attacher items_count à chaque mouvement
        result = self.db.execute(query).all()
        movements = []
        for movement, items_count in result:
            # Attacher items_count comme attribut temporaire (non persisté)
            movement.items_count = items_count
            movements.append(movement)

        return (movements, total)

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
