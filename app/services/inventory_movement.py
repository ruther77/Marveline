"""Service métier pour les mouvements de stock."""
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ItemCondition, MovementStatus, MovementType, ReservationStatus
from app.constants.errors import ErrorMessages
from app.constants.business import LATE_RETURN_PENALTY_RATE
from app.models.inventory_movement import InventoryMovement, MovementItem
from app.models.movement_item_unit import MovementItemUnit
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.repositories.inventory_movement import (
    AsyncMovementItemRepository,
    AsyncMovementRepository,
)
from app.repositories.product import AsyncProductRepository

logger = logging.getLogger(__name__)

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
    """Service async pour la gestion des mouvements de stock."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncMovementRepository(db)
        self.item_repo = AsyncMovementItemRepository(db)

    # ── Validation ──────────────────────────────────────────────────

    async def _validate_variant(
        self, product_id: int, variant_id: Optional[int], tenant_id: int
    ) -> None:
        from sqlalchemy import func, select

        count_result = await self.db.execute(
            select(func.count())
            .select_from(ProductVariant)
            .where(
                ProductVariant.product_id == product_id,
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.is_active.is_(True),
            )
        )
        active_variants_count = count_result.scalar() or 0

        if active_variants_count > 0 and variant_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Ce produit a des variantes couleur — veuillez spécifier variant_id "
                    f"(produit {product_id})"
                ),
            )

        if variant_id is not None:
            from sqlalchemy import select

            result = await self.db.execute(
                select(ProductVariant).where(
                    ProductVariant.id == variant_id,
                    ProductVariant.product_id == product_id,
                    ProductVariant.tenant_id == tenant_id,
                    ProductVariant.is_active.is_(True),
                )
            )
            if not result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ErrorMessages.VARIANT_NOT_FOUND,
                )

    # ── CRUD Movements ───────────────────────────────────────────────

    async def create_movement(
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
        skip_stock_check: bool = False,
    ) -> InventoryMovement:
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one item is required",
            )

        valid_types = {mt.value for mt in MovementType}
        if movement_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid movement_type: {movement_type}",
            )

        if not skip_stock_check and movement_type == MovementType.DEPARTURE.value:
            for item_data in items:
                product_id = item_data.get("product_id")
                variant_id = item_data.get("variant_id")
                qty_expected = item_data.get("quantity_expected", 0)
                if product_id and variant_id:
                    variant = await self.db.get(ProductVariant, variant_id)
                    if variant and variant.tenant_id == tenant_id:
                        if variant.available_quantity < qty_expected:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=(
                                    f"Stock insuffisant pour la variante {variant_id} : "
                                    f"disponible={variant.available_quantity}, demandé={qty_expected}"
                                ),
                            )
                elif product_id:
                    product = await self.db.get(Product, product_id)
                    if product and product.tenant_id == tenant_id:
                        if product.available_quantity < qty_expected:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=(
                                    f"Stock insuffisant pour le produit {product_id} : "
                                    f"disponible={product.available_quantity}, demandé={qty_expected}"
                                ),
                            )

        movement = await self.repo.create({
            "tenant_id": tenant_id,
            "event_id": event_id,
            "reservation_id": reservation_id,
            "movement_type": movement_type,
            "scheduled_date": scheduled_date,
            "status": MovementStatus.SCHEDULED.value,
            "delivery_method": delivery_method,
            "delivery_address": delivery_address,
            "delivery_notes": delivery_notes,
            "damage_fee_cents": 0,
        })

        for item_data in items:
            await self.item_repo.create({
                "tenant_id": tenant_id,
                "movement_id": movement.id,
                "event_item_id": item_data.get("event_item_id"),
                "product_id": item_data.get("product_id"),
                "variant_id": item_data.get("variant_id"),
                "quantity_expected": item_data["quantity_expected"],
                "condition": item_data.get("condition"),
                "condition_notes": item_data.get("condition_notes"),
            })

        await self.db.refresh(movement)
        return movement

    async def get_movement(
        self,
        movement_id: int,
        tenant_id: int,
    ) -> InventoryMovement:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await self.db.execute(
            select(InventoryMovement)
            .options(
                selectinload(InventoryMovement.items).selectinload(MovementItem.units),
                selectinload(InventoryMovement.items).selectinload(MovementItem.product),
                selectinload(InventoryMovement.items).selectinload(MovementItem.variant),
            )
            .where(
                InventoryMovement.id == movement_id,
                InventoryMovement.tenant_id == tenant_id,
                InventoryMovement.is_active.is_(True),
            )
        )
        movement = result.scalar_one_or_none()
        if not movement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movement not found",
            )

        # Résoudre les noms de bundles pour items sans product_id
        await self._resolve_bundle_names(movement)

        return movement

    async def _resolve_bundle_names(
        self,
        movement: InventoryMovement,
    ) -> None:
        """Injecte _bundle_name sur les items sans product_id via event_item_id → ReservationLine → Bundle."""
        from sqlalchemy import select

        orphan_ids = [
            item.event_item_id
            for item in movement.items
            if not item.product_id and item.event_item_id
        ]
        if not orphan_ids:
            return

        from app.models.reservation import ReservationLine
        from app.models.bundle import ProductBundle

        stmt = (
            select(ReservationLine.id, ProductBundle.name)
            .join(ProductBundle, ReservationLine.bundle_id == ProductBundle.id)
            .where(ReservationLine.id.in_(orphan_ids))
        )
        rows = (await self.db.execute(stmt)).all()
        name_map = {row[0]: row[1] for row in rows}

        for item in movement.items:
            if not item.product_id and item.event_item_id:
                bundle_name = name_map.get(item.event_item_id)
                if bundle_name:
                    object.__setattr__(item, "_bundle_name", bundle_name)

    async def list_movements(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 20,
        movement_type: Optional[str] = None,
        movement_status: Optional[str] = None,
        event_id: Optional[int] = None,
        reservation_id: Optional[int] = None,
        product_id: Optional[int] = None,
    ) -> tuple[list[InventoryMovement], int]:
        filters: dict[str, Any] = {}
        if movement_type:
            filters["movement_type"] = movement_type
        if movement_status:
            filters["status"] = movement_status
        if event_id is not None:
            filters["event_id"] = event_id
        if reservation_id is not None:
            filters["reservation_id"] = reservation_id

        return await self.repo.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters=filters if filters else None,
            order_by="scheduled_date",
            product_id=product_id,
        )

    async def update_movement(
        self,
        movement_id: int,
        tenant_id: int,
        **kwargs: Any,
    ) -> InventoryMovement:
        movement = await self.get_movement(movement_id, tenant_id)

        new_status = kwargs.get("status")
        if new_status and new_status != movement.status:
            if new_status == MovementStatus.COMPLETED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Cannot set status to 'completed' via update_movement. "
                        "Use complete_movement() or the Operations flow (validate_departure/validate_return)."
                    ),
                )
            allowed = VALID_TRANSITIONS.get(movement.status, set())
            if new_status not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Invalid status transition: {movement.status} → {new_status}. "
                        f"Allowed: {', '.join(sorted(allowed)) or 'none'}"
                    ),
                )

        updatable_fields = {
            "scheduled_date", "actual_date", "status",
            "delivery_method", "delivery_address", "delivery_notes",
            "handled_by_user_id", "inspection_status", "inspection_notes", "damage_fee_cents",
        }
        data = {k: v for k, v in kwargs.items() if k in updatable_fields and v is not None}
        return await self.repo.update(movement, data)

    async def delete_movement(self, movement_id: int, tenant_id: int) -> bool:
        movement = await self.get_movement(movement_id, tenant_id)

        if movement.status == MovementStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete a completed movement",
            )

        await self.repo.update(movement, {"is_active": False})
        return True

    # ── Status Actions ───────────────────────────────────────────────

    async def complete_movement(
        self,
        movement_id: int,
        tenant_id: int,
        *,
        _internal: bool = False,
    ) -> InventoryMovement:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await self.db.execute(
            select(InventoryMovement)
            .options(
                selectinload(InventoryMovement.items).selectinload(MovementItem.units),
                selectinload(InventoryMovement.items).selectinload(MovementItem.product),
                selectinload(InventoryMovement.items).selectinload(MovementItem.variant),
            )
            .where(
                InventoryMovement.id == movement_id,
                InventoryMovement.tenant_id == tenant_id,
                InventoryMovement.is_active.is_(True),
            )
        )
        movement = result.scalar_one_or_none()
        if not movement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movement not found",
            )

        # Idempotence: compléter un mouvement déjà completed renvoie l'état courant.
        if movement.status == MovementStatus.COMPLETED.value:
            return movement

        # Enforce VALID_TRANSITIONS
        allowed = VALID_TRANSITIONS.get(movement.status, set())
        if MovementStatus.COMPLETED.value not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot complete movement in status '{movement.status}'. "
                       f"Allowed transitions: {sorted(allowed) or 'none'}",
            )

        # Mouvements liés à une réservation → passage obligatoire par Operations
        if not _internal and movement.reservation_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This movement is linked to a reservation. "
                       "Use the Operations flow (departure/return) to complete it.",
            )

        update_data: dict[str, Any] = {
            "status": MovementStatus.COMPLETED.value,
            "actual_date": datetime.now(timezone.utc),
        }

        if movement.movement_type == MovementType.RETURN.value and movement.damage_fee_cents == 0:
            auto_fee = await self._calculate_damage_fee_from_items(movement)
            if auto_fee > 0:
                update_data["damage_fee_cents"] = auto_fee

        await self.repo.update(movement, update_data)

        # Recharger avec relations eager pour _update_stock_on_complete (évite MissingGreenlet)
        result = await self.db.execute(
            select(InventoryMovement)
            .options(
                selectinload(InventoryMovement.items).selectinload(MovementItem.units),
                selectinload(InventoryMovement.items).selectinload(MovementItem.product),
                selectinload(InventoryMovement.items).selectinload(MovementItem.variant),
            )
            .where(
                InventoryMovement.id == movement_id,
                InventoryMovement.tenant_id == tenant_id,
            )
        )
        movement = result.scalar_one()

        await self._update_stock_on_complete(movement)
        await self._update_reservation_on_complete(movement)
        return movement

    async def _update_reservation_on_complete(self, movement: InventoryMovement) -> None:
        """Met à jour le statut réservation quand un mouvement lié est complété."""
        if not movement.reservation_id:
            return

        from sqlalchemy import select
        from app.models.reservation import Reservation

        result = await self.db.execute(
            select(Reservation).where(
                Reservation.id == movement.reservation_id,
                Reservation.tenant_id == movement.tenant_id,
            )
        )
        reservation = result.scalar_one_or_none()
        if not reservation:
            logger.warning(
                "Reservation %d not found for movement %d",
                movement.reservation_id,
                movement.id,
            )
            return

        # Note: la transition DEPARTURE → DELIVERED est gérée par Operations
        # (validate_departure). Seul le RETURN est géré ici en fallback.
        if movement.movement_type == MovementType.RETURN.value:
            if reservation.status == ReservationStatus.DELIVERED:
                reservation.status = ReservationStatus.RETURNED
                await self.db.flush()
                logger.info(
                    "Reservation %s -> returned (return movement %d completed)",
                    reservation.reference,
                    movement.id,
                )

    # ── Phase 4C — Calcul damage_fee_cents ────────────────────────────

    async def _calculate_damage_fee_from_items(self, movement: InventoryMovement) -> int:
        total_fee = 0
        for item in movement.items:
            if item.condition not in (ItemCondition.DAMAGED.value, ItemCondition.MISSING.value):
                continue
            if not item.product_id:
                continue

            price = 0
            if item.variant_id:
                variant = await self.db.get(ProductVariant, item.variant_id)
                if variant and variant.price_per_day_cents is not None:
                    price = variant.price_per_day_cents
            if price == 0:
                product = await self.db.get(Product, item.product_id)
                if product:
                    price = product.price_per_day_cents
            if price == 0:
                continue

            qty_actual = item.quantity_actual if item.quantity_actual is not None else item.quantity_expected

            if item.condition == ItemCondition.MISSING.value:
                qty_issue = item.quantity_expected - qty_actual
            else:
                qty_issue = qty_actual

            total_fee += price * max(0, qty_issue)

        return total_fee

    # ── D6 — Synchronisation stock_items ────────────────────────────

    async def _update_stock_on_complete(self, movement: InventoryMovement) -> None:
        from app.repositories.stock_item import AsyncStockItemRepository

        repo = AsyncStockItemRepository(self.db)
        if not movement.items:
            return

        if movement.movement_type == MovementType.DEPARTURE.value:
            for item in movement.items:
                if not item.product_id:
                    continue
                qty = item.quantity_expected
                if qty <= 0:
                    continue
                try:
                    transitioned = await repo.transition_n(
                        item.product_id, qty, "reserved", "on_location", movement.tenant_id,
                        variant_id=getattr(item, "variant_id", None),
                    )
                    for stock_item in transitioned:
                        unit = MovementItemUnit(
                            tenant_id=movement.tenant_id,
                            movement_item_id=item.id,
                            stock_item_id=stock_item.id,
                            status_before="reserved",
                            status_after="on_location",
                        )
                        self.db.add(unit)
                    await self.db.flush()
                except ValueError:
                    logger.warning(
                        "StockItem: transition reserved→on_location partielle (product_id=%d, qty=%d)",
                        item.product_id, qty,
                    )

        elif movement.movement_type == MovementType.RETURN.value:
            products_to_sync: set[int] = set()
            for item in movement.items:
                if not item.product_id:
                    continue
                if item.units:
                    for unit in item.units:
                        condition = unit.condition or item.condition
                        if condition in (ItemCondition.DAMAGED.value, ItemCondition.MISSING.value):
                            new_status = "damaged"
                        else:
                            new_status = "available"
                        try:
                            await repo.transition_status(
                                unit.stock_item_id, new_status, movement.tenant_id
                            )
                            unit.status_before = "on_location"
                            unit.status_after = new_status
                            products_to_sync.add(item.product_id)
                        except (ValueError, Exception):
                            logger.warning(
                                "StockItem: transition individuelle échouée (stock_item_id=%d → %s)",
                                unit.stock_item_id, new_status,
                            )
                else:
                    qty_actual = (
                        item.quantity_actual
                        if item.quantity_actual is not None
                        else item.quantity_expected
                    )
                    if item.condition == ItemCondition.DAMAGED.value:
                        qty_damaged_bulk = qty_actual
                        qty_ok_bulk = 0
                    elif item.condition == ItemCondition.MISSING.value:
                        qty_damaged_bulk = item.quantity_expected - qty_actual
                        qty_ok_bulk = qty_actual
                    else:
                        qty_damaged_bulk = 0
                        qty_ok_bulk = qty_actual

                    if qty_ok_bulk > 0:
                        try:
                            await repo.transition_n(
                                item.product_id, qty_ok_bulk, "on_location", "available", movement.tenant_id
                            )
                            products_to_sync.add(item.product_id)
                        except ValueError:
                            logger.warning(
                                "StockItem: bulk on_location→available partielle (product_id=%d, qty=%d)",
                                item.product_id, qty_ok_bulk,
                            )
                    if qty_damaged_bulk > 0:
                        try:
                            await repo.transition_n(
                                item.product_id, qty_damaged_bulk, "on_location", "damaged", movement.tenant_id
                            )
                            products_to_sync.add(item.product_id)
                        except ValueError:
                            logger.warning(
                                "StockItem: bulk on_location→damaged partielle (product_id=%d, qty=%d)",
                                item.product_id, qty_damaged_bulk,
                            )

            product_repo = AsyncProductRepository(self.db)
            for product_id in products_to_sync:
                await product_repo.sync_available_from_variants(product_id, movement.tenant_id)

    # ── Phase 4D — Calcul pénalité retard ───────────────────────────

    async def calculate_late_penalty(self, movement: InventoryMovement) -> int:
        if movement.movement_type != MovementType.RETURN.value:
            return 0
        if not movement.reservation_id:
            return 0

        actual = movement.actual_date or datetime.now(timezone.utc)
        scheduled = movement.scheduled_date

        actual_d = actual.date() if hasattr(actual, "date") else actual
        scheduled_d = scheduled.date() if hasattr(scheduled, "date") else scheduled

        days_late = max(0, (actual_d - scheduled_d).days)
        if days_late == 0:
            return 0

        from app.repositories.reservation import AsyncReservationRepository

        reservation = await AsyncReservationRepository(self.db).get_by_id(
            movement.reservation_id, movement.tenant_id
        )
        if not reservation:
            return 0

        return int(reservation.total_amount_cents * LATE_RETURN_PENALTY_RATE * days_late)

    # ── Special Queries ──────────────────────────────────────────────

    async def get_late_movements(
        self, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> tuple[list[InventoryMovement], int]:
        return await self.repo.list_late(tenant_id, skip, limit)

    async def get_pending_inspections(
        self, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> tuple[list[InventoryMovement], int]:
        return await self.repo.list_pending_inspections(tenant_id, skip, limit)

    async def get_statistics(
        self,
        tenant_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        return await self.repo.get_statistics(tenant_id, start_date=start_date, end_date=end_date)

    async def get_agenda(
        self,
        tenant_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        from datetime import timedelta

        from sqlalchemy import or_, select
        from sqlalchemy.orm import selectinload

        from app.models.customer import Customer
        from app.models.reservation import Reservation

        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = start_date + timedelta(days=30)

        result = await self.db.execute(
            select(Reservation)
            .options(
                selectinload(Reservation.movements).selectinload(InventoryMovement.items),
                selectinload(Reservation.customer),
            )
            .where(
                Reservation.tenant_id == tenant_id,
                or_(
                    (Reservation.delivery_date >= start_date) & (Reservation.delivery_date <= end_date),
                    (Reservation.return_date >= start_date) & (Reservation.return_date <= end_date),
                ),
            )
            .join(Customer, Reservation.customer_id == Customer.id)
        )
        reservations = list(result.scalars().all())

        events = []
        total_departures = 0
        total_returns = 0

        for reservation in reservations:
            departure_movement = None
            return_movement = None

            for movement in reservation.movements:
                if not movement.is_active:
                    continue
                if movement.scheduled_date.date() < start_date or movement.scheduled_date.date() > end_date:
                    continue

                if movement.movement_type == MovementType.DEPARTURE.value:
                    departure_movement = movement
                    total_departures += 1
                elif movement.movement_type == MovementType.RETURN.value:
                    return_movement = movement
                    total_returns += 1

            event_item: dict[str, Any] = {
                "event_id": None,
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
                    "items_count": len(departure_movement.items) if hasattr(departure_movement, "items") else 0,
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
                    "items_count": len(return_movement.items) if hasattr(return_movement, "items") else 0,
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

    async def add_item(
        self,
        movement_id: int,
        tenant_id: int,
        event_item_id: Optional[int] = None,
        product_id: Optional[int] = None,
        variant_id: Optional[int] = None,
        quantity_expected: int = 1,
        condition: Optional[str] = None,
        condition_notes: Optional[str] = None,
    ) -> MovementItem:
        movement = await self.get_movement(movement_id, tenant_id)

        if movement.status in (
            MovementStatus.COMPLETED.value,
            MovementStatus.CANCELLED.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add items to a completed or cancelled movement",
            )

        if product_id is not None:
            await self._validate_variant(product_id, variant_id, tenant_id)

        return await self.item_repo.create({
            "tenant_id": tenant_id,
            "movement_id": movement_id,
            "event_item_id": event_item_id,
            "product_id": product_id,
            "variant_id": variant_id,
            "quantity_expected": quantity_expected,
            "condition": condition,
            "condition_notes": condition_notes,
        })

    async def update_item(
        self,
        item_id: int,
        tenant_id: int,
        quantity_actual: Optional[int] = None,
        condition: Optional[str] = None,
        condition_notes: Optional[str] = None,
    ) -> MovementItem:
        from sqlalchemy import select

        result = await self.db.execute(
            select(MovementItem).where(
                MovementItem.id == item_id,
                MovementItem.tenant_id == tenant_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movement item not found",
            )

        data: dict[str, Any] = {}
        if quantity_actual is not None:
            data["quantity_actual"] = quantity_actual
        if condition is not None:
            data["condition"] = condition
        if condition_notes is not None:
            data["condition_notes"] = condition_notes

        return await self.item_repo.update(item, data)

    async def remove_item(self, item_id: int, tenant_id: int) -> bool:
        from sqlalchemy import select

        result = await self.db.execute(
            select(MovementItem).where(
                MovementItem.id == item_id,
                MovementItem.tenant_id == tenant_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movement item not found",
            )

        movement = await self.repo.get_by_id(item.movement_id, tenant_id)
        if movement and movement.status in (
            MovementStatus.COMPLETED.value,
            MovementStatus.CANCELLED.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove items from a completed or cancelled movement",
            )

        await self.item_repo.soft_delete(item)
        return True


# Backward-compat alias
AsyncMovementService = MovementService
