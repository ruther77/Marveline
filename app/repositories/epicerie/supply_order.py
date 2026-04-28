"""Repository SupplyOrder + SupplyOrderLine."""
from datetime import date
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.epicerie.supply_order import SupplyOrder, SupplyOrderLine


class AsyncSupplyOrderRepository:
    """Repository async pour SupplyOrder et SupplyOrderLine."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, order_id: int, tenant_id: int) -> Optional[SupplyOrder]:
        result = await self._db.execute(
            select(SupplyOrder).where(
                SupplyOrder.id == order_id,
                SupplyOrder.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        tenant_id: int,
        page: int = 1,
        per_page: int = 20,
        vendor_id: Optional[int] = None,
        statut: Optional[str] = None,
    ) -> tuple[list[SupplyOrder], int]:
        q = select(SupplyOrder).where(SupplyOrder.tenant_id == tenant_id)
        if vendor_id is not None:
            q = q.where(SupplyOrder.vendor_id == vendor_id)
        if statut:
            q = q.where(SupplyOrder.statut == statut)

        total_result = await self._db.execute(
            select(func.count()).select_from(q.subquery())
        )
        total = total_result.scalar_one()
        items_result = await self._db.execute(
            q.order_by(SupplyOrder.date_commande.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(items_result.scalars().all()), total

    async def count_by_vendor(self, vendor_id: int, tenant_id: int) -> int:
        result = await self._db.execute(
            select(func.count()).select_from(SupplyOrder).where(
                SupplyOrder.vendor_id == vendor_id,
                SupplyOrder.tenant_id == tenant_id,
            )
        )
        return result.scalar_one()

    async def count_livraisons_mois(self, vendor_id: int, tenant_id: int) -> int:
        """Commandes livrées (statut='livree') sur le mois calendaire courant."""
        today = date.today()
        debut_mois = today.replace(day=1)
        result = await self._db.execute(
            select(func.count()).select_from(SupplyOrder).where(
                SupplyOrder.vendor_id == vendor_id,
                SupplyOrder.tenant_id == tenant_id,
                SupplyOrder.statut == "livree",
                SupplyOrder.date_livraison_reelle >= debut_mois,
            )
        )
        return result.scalar_one()

    async def create(
        self,
        tenant_id: int,
        vendor_id: int,
        date_commande,
        reference: Optional[str] = None,
        date_livraison_prevue=None,
        notes: Optional[str] = None,
    ) -> SupplyOrder:
        order = SupplyOrder(
            tenant_id=tenant_id,
            vendor_id=vendor_id,
            reference=reference,
            date_commande=date_commande,
            date_livraison_prevue=date_livraison_prevue,
            statut="en_attente",
            notes=notes,
        )
        self._db.add(order)
        await self._db.flush()
        return order

    async def create_line(
        self,
        order_id: int,
        designation: str,
        quantity: float,
        prix_unitaire: int,
        taux_tva: int = 2000,
        produit_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> SupplyOrderLine:
        line = SupplyOrderLine(
            order_id=order_id,
            produit_id=produit_id,
            designation=designation,
            quantity=quantity,
            prix_unitaire=prix_unitaire,
            taux_tva=taux_tva,
            notes=notes,
        )
        self._db.add(line)
        await self._db.flush()
        return line

    async def list_lines(self, order_id: int) -> list[SupplyOrderLine]:
        result = await self._db.execute(
            select(SupplyOrderLine)
            .where(SupplyOrderLine.order_id == order_id)
            .order_by(SupplyOrderLine.id)
        )
        return list(result.scalars().all())

    async def update_statut(
        self,
        order: SupplyOrder,
        statut: str,
        invoice_id: Optional[int] = None,
        date_livraison_reelle=None,
    ) -> SupplyOrder:
        order.statut = statut
        if invoice_id is not None:
            order.invoice_id = invoice_id
        if date_livraison_reelle is not None:
            order.date_livraison_reelle = date_livraison_reelle
        await self._db.flush()
        return order

    async def update_totaux(
        self, order: SupplyOrder, montant_ht: int, montant_tva: int, montant_ttc: int
    ) -> SupplyOrder:
        order.montant_ht = montant_ht
        order.montant_tva = montant_tva
        order.montant_ttc = montant_ttc
        await self._db.flush()
        return order

    async def update_line_received(
        self, line: SupplyOrderLine, received_quantity: float
    ) -> SupplyOrderLine:
        line.received_quantity = received_quantity
        await self._db.flush()
        return line
