"""Repository pour SupplierOrder, SupplierOrderLine, SupplierOrderReceipt."""
import math
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.supplier_order import SupplierOrder, SupplierOrderLine, SupplierOrderReceipt


class SupplierOrderRepository:
    """Accès données commandes fournisseurs avec isolation multi-tenant."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -----------------------------------------------------------------------
    # SupplierOrder
    # -----------------------------------------------------------------------

    def list_paginated(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        supplier_id: Optional[int] = None,
    ) -> tuple[list[SupplierOrder], int]:
        """Retourne (items, total) pour la page demandée."""
        query = select(SupplierOrder).filter(
            SupplierOrder.tenant_id == tenant_id,
            SupplierOrder.is_active == True,  # noqa: E712
        )
        if status:
            query = query.filter(SupplierOrder.status == status)
        if supplier_id:
            query = query.filter(SupplierOrder.supplier_id == supplier_id)

        total = self.db.execute(
            select(func.count()).select_from(query.subquery())
        ).scalar_one()

        items = list(
            self.db.execute(
                query.order_by(SupplierOrder.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return items, total

    def get_by_id(self, order_id: int, tenant_id: int) -> Optional[SupplierOrder]:
        """Charge une commande avec ses lignes et bons de réception."""
        return self.db.execute(
            select(SupplierOrder)
            .options(
                selectinload(SupplierOrder.lines),
                selectinload(SupplierOrder.receipts),
            )
            .filter(
                SupplierOrder.id == order_id,
                SupplierOrder.tenant_id == tenant_id,
                SupplierOrder.is_active == True,  # noqa: E712
            )
        ).scalar_one_or_none()

    def create(self, order: SupplierOrder) -> SupplierOrder:
        self.db.add(order)
        self.db.flush()
        return order

    def soft_delete(self, order_id: int, tenant_id: int) -> bool:
        order = self.db.execute(
            select(SupplierOrder).filter(
                SupplierOrder.id == order_id,
                SupplierOrder.tenant_id == tenant_id,
                SupplierOrder.is_active == True,  # noqa: E712
            )
        ).scalar_one_or_none()
        if not order:
            return False
        order.is_active = False
        return True

    # -----------------------------------------------------------------------
    # SupplierOrderLine
    # -----------------------------------------------------------------------

    def get_line(
        self, line_id: int, order_id: int, tenant_id: int
    ) -> Optional[SupplierOrderLine]:
        return self.db.execute(
            select(SupplierOrderLine).filter(
                SupplierOrderLine.id == line_id,
                SupplierOrderLine.order_id == order_id,
                SupplierOrderLine.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

    # -----------------------------------------------------------------------
    # SupplierOrderReceipt
    # -----------------------------------------------------------------------

    def create_receipt(self, receipt: SupplierOrderReceipt) -> SupplierOrderReceipt:
        self.db.add(receipt)
        self.db.flush()
        return receipt

    # -----------------------------------------------------------------------
    # Helpers pagination
    # -----------------------------------------------------------------------

    @staticmethod
    def compute_total_pages(total: int, page_size: int) -> int:
        return max(1, math.ceil(total / page_size))


class AsyncSupplierOrderRepository:
    """Version async de SupplierOrderRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def list_paginated(
        self, tenant_id: int, skip: int = 0, limit: int = 20,
        status=None, supplier_id=None,
    ) -> tuple[list, int]:
        from sqlalchemy import select, func
        from app.models.supplier_order import SupplierOrder
        q = select(SupplierOrder).filter(
            SupplierOrder.tenant_id == tenant_id,
            SupplierOrder.is_active == True,  # noqa: E712
        )
        if status:
            q = q.filter(SupplierOrder.status == status)
        if supplier_id:
            q = q.filter(SupplierOrder.supplier_id == supplier_id)

        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar_one()

        items_result = await self.db.execute(
            q.order_by(SupplierOrder.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(items_result.scalars().all()), total

    async def get_by_id(self, order_id: int, tenant_id: int):
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.supplier_order import SupplierOrder
        result = await self.db.execute(
            select(SupplierOrder)
            .options(
                selectinload(SupplierOrder.lines),
                selectinload(SupplierOrder.receipts),
            )
            .filter(
                SupplierOrder.id == order_id,
                SupplierOrder.tenant_id == tenant_id,
                SupplierOrder.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def create(self, order):
        self.db.add(order)
        await self.db.flush()
        await self.db.refresh(order)
        return order

    async def soft_delete(self, order_id: int, tenant_id: int) -> bool:
        from sqlalchemy import select
        from app.models.supplier_order import SupplierOrder
        result = await self.db.execute(
            select(SupplierOrder).filter(
                SupplierOrder.id == order_id,
                SupplierOrder.tenant_id == tenant_id,
                SupplierOrder.is_active == True,  # noqa: E712
            )
        )
        order = result.scalar_one_or_none()
        if not order:
            return False
        order.is_active = False
        await self.db.flush()
        return True

    async def get_line(self, line_id: int, order_id: int, tenant_id: int):
        from sqlalchemy import select
        from app.models.supplier_order import SupplierOrderLine
        result = await self.db.execute(
            select(SupplierOrderLine).filter(
                SupplierOrderLine.id == line_id,
                SupplierOrderLine.order_id == order_id,
                SupplierOrderLine.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_receipt(self, receipt):
        self.db.add(receipt)
        await self.db.flush()
        await self.db.refresh(receipt)
        return receipt

    @staticmethod
    def compute_total_pages(total: int, page_size: int) -> int:
        import math
        return max(1, math.ceil(total / page_size))
