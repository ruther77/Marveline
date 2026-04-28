"""Repository pour StockItem — tracking individuel des unités physiques."""
import logging
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import case, func, or_
from app.models.stock_item import StockItem
from app.models.movement_item_unit import MovementItemUnit
from app.models.inventory_movement import MovementItem, InventoryMovement

logger = logging.getLogger(__name__)


def _variant_filter(variant_id: Optional[int]):
    if variant_id is None:
        return None
    return or_(StockItem.variant_id == variant_id, StockItem.variant_id.is_(None))


def _variant_ordering(variant_id: Optional[int]):
    if variant_id is None:
        return (StockItem.id,)
    return (
        case((StockItem.variant_id == variant_id, 0), else_=1),
        StockItem.id,
    )


class StockItemRepository:
    """Repository pour les opérations sur stock_items.

    Toutes les opérations filtrent par tenant_id (isolation multi-tenant).
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, item_id: int, product_id: int, tenant_id: int) -> Optional[StockItem]:
        """Récupère un stock_item par id, product_id et tenant_id."""
        return (
            self.db.query(StockItem)
            .filter(
                StockItem.id == item_id,
                StockItem.product_id == product_id,
                StockItem.tenant_id == tenant_id,
            )
            .first()
        )

    def get_item_history(
        self, item_id: int, tenant_id: int
    ) -> list[MovementItemUnit]:
        """Retourne l'historique complet d'un stock_item : tous ses MovementItemUnit
        avec leurs MovementItem et InventoryMovement, triés par date planifiée.
        """
        return (
            self.db.query(MovementItemUnit)
            .join(MovementItem, MovementItemUnit.movement_item_id == MovementItem.id)
            .join(InventoryMovement, MovementItem.movement_id == InventoryMovement.id)
            .options(
                joinedload(MovementItemUnit.movement_item).joinedload(
                    MovementItem.movement
                )
            )
            .filter(
                MovementItemUnit.stock_item_id == item_id,
                MovementItemUnit.tenant_id == tenant_id,
            )
            .order_by(InventoryMovement.scheduled_date)
            .all()
        )

    def list_by_product(self, product_id: int, tenant_id: int) -> list[StockItem]:
        """Liste tous les stock_items d'un produit, toutes statuses."""
        return (
            self.db.query(StockItem)
            .filter(
                StockItem.product_id == product_id,
                StockItem.tenant_id == tenant_id,
            )
            .order_by(StockItem.id)
            .all()
        )

    def count_by_status(self, product_id: int, status: str, tenant_id: int) -> int:
        """Compte les stock_items d'un produit pour un status donné."""
        return (
            self.db.query(func.count(StockItem.id))
            .filter(
                StockItem.product_id == product_id,
                StockItem.tenant_id == tenant_id,
                StockItem.status == status,
            )
            .scalar()
            or 0
        )

    def count_by_statuses(self, product_id: int, tenant_id: int) -> dict[str, int]:
        """Retourne les compteurs par status pour un produit."""
        rows = (
            self.db.query(StockItem.status, func.count(StockItem.id))
            .filter(
                StockItem.product_id == product_id,
                StockItem.tenant_id == tenant_id,
            )
            .group_by(StockItem.status)
            .all()
        )
        return {status: count for status, count in rows}

    def reserve_n(
        self,
        product_id: int,
        n: int,
        tenant_id: int,
        reservation_id: Optional[int] = None,
        variant_id: Optional[int] = None,
    ) -> list[StockItem]:
        """Passe N items 'available' → 'reserved'.

        Prend les N premiers items disponibles (ORDER BY id).
        Si variant_id fourni, prend d'abord les items déjà affectés à cette
        variante puis complète avec les items non encore assignés (variant_id
        NULL), qui sont alors liés à la variante sélectionnée.

        Raises:
            ValueError: Si moins de N items disponibles.
        """
        q = (
            self.db.query(StockItem)
            .filter(
                StockItem.product_id == product_id,
                StockItem.tenant_id == tenant_id,
                StockItem.status == "available",
            )
        )
        variant_filter = _variant_filter(variant_id)
        if variant_filter is not None:
            q = q.filter(variant_filter)
        items = (
            q
            .order_by(*_variant_ordering(variant_id))
            .limit(n)
            .with_for_update()
            .all()
        )
        if len(items) < n:
            raise ValueError(
                f"Stock insuffisant : {len(items)} disponible(s), {n} requis "
                f"(product_id={product_id})"
            )
        for item in items:
            if variant_id is not None and item.variant_id is None:
                item.variant_id = variant_id
            item.status = "reserved"
            item.current_reservation_id = reservation_id
        self.db.flush()
        return items

    def release_n(
        self,
        product_id: int,
        n: int,
        tenant_id: int,
        variant_id: Optional[int] = None,
        reservation_id: Optional[int] = None,
    ) -> list[StockItem]:
        """Passe N items 'reserved' → 'available' (annulation réservation).

        Si ``reservation_id`` est fourni, ne libère que les items appartenant
        à cette réservation (``current_reservation_id`` match). Évite le bug
        de libération aveugle quand 2 résa concurrentes existent sur le même
        produit.

        Si variant_id fourni, prend les items de cette variante puis complète
        avec les items encore non assignés.

        Raises:
            ValueError: Si moins de N items réservés correspondants.
        """
        q = (
            self.db.query(StockItem)
            .filter(
                StockItem.product_id == product_id,
                StockItem.tenant_id == tenant_id,
                StockItem.status == "reserved",
            )
        )
        if reservation_id is not None:
            q = q.filter(StockItem.current_reservation_id == reservation_id)
        else:
            logger.warning(
                "release_n called without reservation_id (product_id=%s, tenant=%s) "
                "— may release items belonging to other reservations",
                product_id, tenant_id,
            )
        variant_filter = _variant_filter(variant_id)
        if variant_filter is not None:
            q = q.filter(variant_filter)
        items = (
            q
            .order_by(*_variant_ordering(variant_id))
            .limit(n)
            .with_for_update()
            .all()
        )
        if len(items) < n:
            raise ValueError(
                f"Impossible de libérer {n} items réservés (seulement {len(items)} réservés)"
            )
        for item in items:
            item.status = "available"
            item.current_reservation_id = None
        self.db.flush()
        return items

    def transition_n(
        self,
        product_id: int,
        n: int,
        from_status: str,
        to_status: str,
        tenant_id: int,
        variant_id: Optional[int] = None,
    ) -> list[StockItem]:
        """Transition générique : passe N items de from_status → to_status.

        Si variant_id fourni, prend les items de cette variante puis complète
        avec les items non encore assignés.

        Raises:
            ValueError: Si moins de N items dans from_status.
        """
        q = (
            self.db.query(StockItem)
            .filter(
                StockItem.product_id == product_id,
                StockItem.tenant_id == tenant_id,
                StockItem.status == from_status,
            )
        )
        variant_filter = _variant_filter(variant_id)
        if variant_filter is not None:
            q = q.filter(variant_filter)
        items = (
            q
            .order_by(*_variant_ordering(variant_id))
            .limit(n)
            .with_for_update()
            .all()
        )
        if len(items) < n:
            raise ValueError(
                f"Transition {from_status}→{to_status} : {len(items)} items dispo, {n} requis "
                f"(product_id={product_id})"
            )
        for item in items:
            if variant_id is not None and item.variant_id is None:
                item.variant_id = variant_id
            item.status = to_status
        self.db.flush()
        return items

    def transition_status(self, stock_item_id: int, new_status: str, tenant_id: int) -> StockItem:
        """Transition d'un item individuel vers new_status.

        Raises:
            ValueError: Si item introuvable ou mauvais tenant.
        """
        item = (
            self.db.query(StockItem)
            .filter(StockItem.id == stock_item_id, StockItem.tenant_id == tenant_id)
            .with_for_update()
            .first()
        )
        if not item:
            raise ValueError(f"StockItem {stock_item_id} introuvable (tenant={tenant_id})")
        item.status = new_status
        self.db.flush()
        return item

class AsyncStockItemRepository:
    """Version async de StockItemRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get_by_id(self, item_id: int, product_id: int, tenant_id: int):
        from sqlalchemy import select
        from app.models.stock_item import StockItem
        result = await self.db.execute(
            select(StockItem).filter(
                StockItem.id == item_id,
                StockItem.product_id == product_id,
                StockItem.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_item_history(self, item_id: int, tenant_id: int) -> list:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        from app.models.movement_item_unit import MovementItemUnit
        from app.models.inventory_movement import MovementItem, InventoryMovement
        result = await self.db.execute(
            select(MovementItemUnit)
            .join(MovementItem, MovementItemUnit.movement_item_id == MovementItem.id)
            .join(InventoryMovement, MovementItem.movement_id == InventoryMovement.id)
            .options(
                joinedload(MovementItemUnit.movement_item).joinedload(MovementItem.movement)
            )
            .filter(
                MovementItemUnit.stock_item_id == item_id,
                MovementItemUnit.tenant_id == tenant_id,
            )
            .order_by(InventoryMovement.scheduled_date)
        )
        return list(result.unique().scalars().all())

    async def list_by_product(self, product_id: int, tenant_id: int) -> list:
        from sqlalchemy import select
        from app.models.stock_item import StockItem
        result = await self.db.execute(
            select(StockItem)
            .filter(StockItem.product_id == product_id, StockItem.tenant_id == tenant_id)
            .order_by(StockItem.id)
        )
        return list(result.scalars().all())

    async def list_by_products(self, product_ids: list[int], tenant_id: int) -> list:
        from sqlalchemy import select
        from app.models.stock_item import StockItem

        if not product_ids:
            return []

        result = await self.db.execute(
            select(StockItem)
            .filter(
                StockItem.product_id.in_(product_ids),
                StockItem.tenant_id == tenant_id,
            )
            .order_by(StockItem.product_id, StockItem.id)
        )
        return list(result.scalars().all())

    async def count_by_status(self, product_id: int, status: str, tenant_id: int) -> int:
        from sqlalchemy import select, func
        from app.models.stock_item import StockItem
        result = await self.db.execute(
            select(func.count(StockItem.id)).filter(
                StockItem.product_id == product_id,
                StockItem.tenant_id == tenant_id,
                StockItem.status == status,
            )
        )
        return result.scalar() or 0

    async def count_by_statuses(self, product_id: int, tenant_id: int) -> dict:
        from sqlalchemy import select, func
        from app.models.stock_item import StockItem
        result = await self.db.execute(
            select(StockItem.status, func.count(StockItem.id))
            .filter(StockItem.product_id == product_id, StockItem.tenant_id == tenant_id)
            .group_by(StockItem.status)
        )
        return {status: count for status, count in result.all()}

    async def reserve_n(
        self,
        product_id: int,
        n: int,
        tenant_id: int,
        reservation_id=None,
        variant_id: Optional[int] = None,
    ) -> list:
        from sqlalchemy import select
        from app.models.stock_item import StockItem
        q = (
            select(StockItem)
            .filter(
                StockItem.product_id == product_id,
                StockItem.tenant_id == tenant_id,
                StockItem.status == "available",
            )
        )
        variant_filter = _variant_filter(variant_id)
        if variant_filter is not None:
            q = q.filter(variant_filter)
        result = await self.db.execute(
            q.order_by(*_variant_ordering(variant_id)).limit(n).with_for_update()
        )
        items = list(result.scalars().all())
        if len(items) < n:
            raise ValueError(
                f"Stock insuffisant : {len(items)} disponible(s), {n} requis "
                f"(product_id={product_id})"
            )
        for item in items:
            if variant_id is not None and item.variant_id is None:
                item.variant_id = variant_id
            item.status = "reserved"
            item.current_reservation_id = reservation_id
        await self.db.flush()
        return items

    async def release_n(
        self,
        product_id: int,
        n: int,
        tenant_id: int,
        variant_id: Optional[int] = None,
        reservation_id: Optional[int] = None,
    ) -> list:
        """Libère N items reserved → available.

        Si ``reservation_id`` est fourni, filtre uniquement les items dont
        ``current_reservation_id`` correspond. C'est le comportement attendu
        pour annuler une réservation sans toucher aux items d'une autre résa
        ouverte sur le même produit.

        Si ``reservation_id`` est None, comportement legacy (libère N items
        reserved au hasard) — déconseillé sauf cleanup admin explicite.
        """
        from sqlalchemy import select
        from app.models.stock_item import StockItem
        q = (
            select(StockItem)
            .filter(
                StockItem.product_id == product_id,
                StockItem.tenant_id == tenant_id,
                StockItem.status == "reserved",
            )
        )
        if reservation_id is not None:
            q = q.filter(StockItem.current_reservation_id == reservation_id)
        else:
            logger.warning(
                "release_n called without reservation_id (product_id=%s, tenant=%s) "
                "— may release items belonging to other reservations",
                product_id, tenant_id,
            )
        variant_filter = _variant_filter(variant_id)
        if variant_filter is not None:
            q = q.filter(variant_filter)
        result = await self.db.execute(
            q.order_by(*_variant_ordering(variant_id)).limit(n).with_for_update()
        )
        items = list(result.scalars().all())
        if len(items) < n:
            raise ValueError(
                f"Impossible de libérer {n} items réservés (seulement {len(items)} réservés)"
            )
        for item in items:
            item.status = "available"
            item.current_reservation_id = None
        await self.db.flush()
        return items

    async def transition_n(
        self,
        product_id: int,
        n: int,
        from_status: str,
        to_status: str,
        tenant_id: int,
        variant_id: Optional[int] = None,
    ) -> list:
        from sqlalchemy import select
        from app.models.stock_item import StockItem
        q = (
            select(StockItem)
            .filter(
                StockItem.product_id == product_id,
                StockItem.tenant_id == tenant_id,
                StockItem.status == from_status,
            )
        )
        variant_filter = _variant_filter(variant_id)
        if variant_filter is not None:
            q = q.filter(variant_filter)
        result = await self.db.execute(
            q.order_by(*_variant_ordering(variant_id)).limit(n).with_for_update()
        )
        items = list(result.scalars().all())
        if len(items) < n:
            raise ValueError(
                f"Transition {from_status}→{to_status} : {len(items)} items dispo, {n} requis "
                f"(product_id={product_id})"
            )
        for item in items:
            if variant_id is not None and item.variant_id is None:
                item.variant_id = variant_id
            item.status = to_status
        await self.db.flush()
        return items

    async def transition_status(self, stock_item_id: int, new_status: str, tenant_id: int):
        from sqlalchemy import select
        from app.models.stock_item import StockItem
        result = await self.db.execute(
            select(StockItem)
            .filter(StockItem.id == stock_item_id, StockItem.tenant_id == tenant_id)
            .with_for_update()
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError(f"StockItem {stock_item_id} introuvable (tenant={tenant_id})")
        item.status = new_status
        await self.db.flush()
        return item
