"""Service SupplierOrder — logique métier cycle commande fournisseur."""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock_management import StockAdjustment
from app.models.supplier_order import SupplierOrder, SupplierOrderLine, SupplierOrderReceipt, SupplierOrderReceiptLine
from app.repositories.supplier_order import AsyncSupplierOrderRepository
from app.schemas.supplier_order import (
    SupplierOrderCreate,
    SupplierOrderListItem,
    SupplierOrderReceiptCreate,
    SupplierOrderUpdate,
)
from app.constants.errors import ErrorMessages
from app.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)

# Transitions d'état autorisées
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"ordered", "cancelled"},
    "ordered": {"partially_received", "fully_received", "cancelled"},
    "partially_received": {"partially_received", "fully_received", "cancelled"},
    "fully_received": set(),
    "cancelled": set(),
}


class SupplierOrderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AsyncSupplierOrderRepository(db)

    # -----------------------------------------------------------------------
    # Lecture
    # -----------------------------------------------------------------------

    async def list_orders(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        supplier_id: Optional[int] = None,
    ) -> PaginatedResponse[SupplierOrderListItem]:
        items, total = await self.repo.list_paginated(
            tenant_id, skip=skip, limit=limit, status=status, supplier_id=supplier_id,
        )
        return PaginatedResponse[SupplierOrderListItem](
            items=items,  # type: ignore[arg-type]
            total=total,
            skip=skip,
            limit=limit,
        )

    async def get_order(self, order_id: int, tenant_id: int) -> SupplierOrder:
        order = await self.repo.get_by_id(order_id, tenant_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.SUPPLIER_ORDER_NOT_FOUND,
            )
        return order

    # -----------------------------------------------------------------------
    # Création
    # -----------------------------------------------------------------------

    async def create_order(
        self, data: SupplierOrderCreate, tenant_id: int
    ) -> SupplierOrder:
        if not data.lines:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La commande doit contenir au moins une ligne",
            )

        order = SupplierOrder(
            tenant_id=tenant_id,
            supplier_id=data.supplier_id,
            reference=data.reference,
            order_date=data.order_date,
            expected_date=data.expected_date,
            notes=data.notes,
            status="draft",
        )
        self.db.add(order)
        await self.db.flush()

        for line_data in data.lines:
            line = SupplierOrderLine(
                tenant_id=tenant_id,
                order_id=order.id,
                product_id=line_data.product_id,
                qty_ordered=line_data.qty_ordered,
                unit_cost_cents=line_data.unit_cost_cents,
                qty_received=0,
            )
            self.db.add(line)

        # Auto-save prix d'achat de reference
        await self._upsert_supplier_prices(
            tenant_id, data.supplier_id, data.lines,
        )

        await self.db.commit()
        return await self.repo.get_by_id(order.id, tenant_id)  # type: ignore[return-value]

    async def _upsert_supplier_prices(
        self, tenant_id: int, supplier_id: int, lines: list,
    ) -> None:
        """Met a jour le referentiel prix d'achat par fournisseur."""
        from sqlalchemy import select
        from app.models.supplier_product_price import SupplierProductPrice

        now = datetime.now(timezone.utc)
        for line_data in lines:
            if not line_data.unit_cost_cents or line_data.unit_cost_cents <= 0:
                continue
            result = await self.db.execute(
                select(SupplierProductPrice).where(
                    SupplierProductPrice.tenant_id == tenant_id,
                    SupplierProductPrice.supplier_id == supplier_id,
                    SupplierProductPrice.product_id == line_data.product_id,
                    SupplierProductPrice.variant_id.is_(None),
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.cost_price_cents = line_data.unit_cost_cents
                existing.last_order_date = now
            else:
                self.db.add(SupplierProductPrice(
                    tenant_id=tenant_id,
                    supplier_id=supplier_id,
                    product_id=line_data.product_id,
                    cost_price_cents=line_data.unit_cost_cents,
                    last_order_date=now,
                ))

    async def get_supplier_prices(
        self, supplier_id: int, tenant_id: int,
    ) -> list[dict]:
        """Retourne les prix d'achat de reference pour un fournisseur."""
        from sqlalchemy import select
        from app.models.supplier_product_price import SupplierProductPrice

        result = await self.db.execute(
            select(SupplierProductPrice).where(
                SupplierProductPrice.tenant_id == tenant_id,
                SupplierProductPrice.supplier_id == supplier_id,
            )
        )
        rows = result.scalars().all()
        return [
            {
                "product_id": r.product_id,
                "variant_id": r.variant_id,
                "cost_price_cents": r.cost_price_cents,
                "last_order_date": r.last_order_date.isoformat() if r.last_order_date else None,
            }
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # Mise a jour
    # -----------------------------------------------------------------------

    async def update_order(
        self, order_id: int, data: SupplierOrderUpdate, tenant_id: int
    ) -> SupplierOrder:
        order = await self.get_order(order_id, tenant_id)
        if order.status in ("fully_received", "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorMessages.SUPPLIER_ORDER_INVALID_STATUS,
            )

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(order, field, value)

        await self.db.commit()
        return await self.repo.get_by_id(order.id, tenant_id)  # type: ignore[return-value]

    # -----------------------------------------------------------------------
    # Confirmation (draft → ordered)
    # -----------------------------------------------------------------------

    async def confirm_order(self, order_id: int, tenant_id: int) -> SupplierOrder:
        order = await self.get_order(order_id, tenant_id)
        self._transition(order, "ordered")
        await self.db.commit()

        # Notifier le fournisseur par email
        self._notify_supplier(order, tenant_id)

        return await self.repo.get_by_id(order.id, tenant_id)  # type: ignore[return-value]

    def _notify_supplier(self, order: SupplierOrder, tenant_id: int) -> None:
        """Enqueue l'envoi d'email au fournisseur (async via Celery)."""
        try:
            from app.tasks.notifications import send_supplier_order_email
            send_supplier_order_email.delay(
                order.id,
                order.supplier_id,
                order.reference,
                tenant_id,
            )
            logger.info(
                "Queued supplier notification for order %s (supplier=%d, tenant=%d)",
                order.reference, order.supplier_id, tenant_id,
            )
        except Exception:
            logger.warning(
                "Failed to queue supplier notification for order %s",
                order.reference,
                exc_info=True,
            )

    # -----------------------------------------------------------------------
    # Réception (partielle ou totale)
    # -----------------------------------------------------------------------

    async def receive(
        self,
        order_id: int,
        data: SupplierOrderReceiptCreate,
        tenant_id: int,
        user_id: int,
    ) -> SupplierOrder:
        order = await self.get_order(order_id, tenant_id)

        if order.status not in ("ordered", "partially_received"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorMessages.SUPPLIER_ORDER_INVALID_STATUS,
            )

        if not data.lines:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No receipt lines provided",
            )

        lines_by_id = {line.id: line for line in order.lines}
        lines_snapshot: dict[str, int] = {}
        now = datetime.now(tz=timezone.utc)

        for recv_line in data.lines:
            line = lines_by_id.get(recv_line.line_id)
            if not line:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ErrorMessages.SUPPLIER_ORDER_LINE_NOT_FOUND,
                )

            # Contrôle : ne pas dépasser le reliquat
            max_receivable = line.qty_ordered - line.qty_received
            if recv_line.qty_received > max_receivable:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Line {recv_line.line_id}: received qty ({recv_line.qty_received}) exceeds remaining ({max_receivable})",
                )

            # Mettre à jour qty_received cumulée
            line.qty_received += recv_line.qty_received
            lines_snapshot[str(recv_line.line_id)] = recv_line.qty_received

            # Créer StockAdjustment pour traçabilité stock
            adjustment = StockAdjustment(
                tenant_id=tenant_id,
                product_id=line.product_id,
                delta=recv_line.qty_received,
                reason=f"Réception commande {order.reference} (ligne {recv_line.line_id})",
                created_at=now,
                created_by=user_id,
            )
            self.db.add(adjustment)

        # Créer le bon de réception
        receipt = SupplierOrderReceipt(
            tenant_id=tenant_id,
            order_id=order.id,
            received_at=now,
            received_by=user_id,
            notes=data.notes,
            lines_json=lines_snapshot,
        )
        self.db.add(receipt)
        await self.db.flush()  # Obtenir receipt.id pour les lignes granulaires

        # Créer les lignes granulaires Option B
        for recv_line in data.lines:
            line = lines_by_id[recv_line.line_id]
            receipt_line = SupplierOrderReceiptLine(
                tenant_id=tenant_id,
                receipt_id=receipt.id,
                order_line_id=recv_line.line_id,
                product_id=line.product_id,
                qty_received=recv_line.qty_received,
                qty_damaged=recv_line.qty_damaged,
                qty_missing=recv_line.qty_missing,
                damage_type_id=recv_line.damage_type_id,
                notes=recv_line.notes,
            )
            self.db.add(receipt_line)

        # Recalculer le statut de la commande
        await self.db.flush()
        all_received = all(
            line.qty_received >= line.qty_ordered for line in order.lines
        )
        order.status = "fully_received" if all_received else "partially_received"

        await self.db.commit()
        return await self.repo.get_by_id(order.id, tenant_id)  # type: ignore[return-value]

    # -----------------------------------------------------------------------
    # Annulation
    # -----------------------------------------------------------------------

    async def cancel_order(self, order_id: int, tenant_id: int) -> SupplierOrder:
        order = await self.get_order(order_id, tenant_id)
        self._transition(order, "cancelled")
        await self.db.commit()
        return await self.repo.get_by_id(order.id, tenant_id)  # type: ignore[return-value]

    # -----------------------------------------------------------------------
    # Soft delete
    # -----------------------------------------------------------------------

    async def delete_order(self, order_id: int, tenant_id: int) -> None:
        deleted = await self.repo.soft_delete(order_id, tenant_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.SUPPLIER_ORDER_NOT_FOUND,
            )
        await self.db.commit()

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _transition(self, order: SupplierOrder, new_status: str) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(order.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Transition '{order.status}' → '{new_status}' non autorisée"
                ),
            )
        order.status = new_status
