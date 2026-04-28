"""Repository InternalTransfer + InternalTransferLine.

Toutes les methodes de lecture filtrent par tenant_id (convention P0).
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.epicerie.internal_transfer import InternalTransfer, InternalTransferLine


class AsyncInternalTransferRepository:
    """Repository async pour InternalTransfer et InternalTransferLine."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Transfer ───────────────────────────────────────────────────────────

    async def get_by_id(
        self, transfer_id: int, tenant_id: int,
    ) -> Optional[InternalTransfer]:
        result = await self._db.execute(
            select(InternalTransfer).where(
                InternalTransfer.id == transfer_id,
                InternalTransfer.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        tenant_id: int,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[InternalTransfer], int]:
        q = select(InternalTransfer).where(
            InternalTransfer.tenant_id == tenant_id,
        )
        if status:
            q = q.where(InternalTransfer.status == status)

        total_result = await self._db.execute(
            select(func.count()).select_from(q.subquery())
        )
        total = total_result.scalar_one()
        items_result = await self._db.execute(
            q.order_by(InternalTransfer.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(items_result.scalars().all()), total

    async def next_sequence_today(
        self,
        tenant_id: int,
        day: Optional[date] = None,
    ) -> int:
        current_day = day or date.today()
        prefix = f"TRF-{current_day.strftime('%Y%m%d')}-"
        result = await self._db.execute(
            select(func.count()).select_from(InternalTransfer).where(
                InternalTransfer.tenant_id == tenant_id,
                InternalTransfer.reference.like(f"{prefix}%"),
            )
        )
        return (result.scalar_one() or 0) + 1

    async def generate_reference(
        self,
        tenant_id: int,
        day: Optional[date] = None,
    ) -> str:
        current_day = day or date.today()
        seq = await self.next_sequence_today(tenant_id, current_day)
        return f"TRF-{current_day.strftime('%Y%m%d')}-{seq:03d}"

    async def create(
        self,
        tenant_id: int,
        dest_tenant_id: int,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
        created_by: Optional[int] = None,
    ) -> InternalTransfer:
        effective_reference = (
            reference.strip()
            if reference is not None and reference.strip()
            else await self.generate_reference(tenant_id)
        )
        transfer = InternalTransfer(
            tenant_id=tenant_id,
            dest_tenant_id=dest_tenant_id,
            reference=effective_reference,
            status="PENDING",
            notes=notes,
            created_by=created_by,
        )
        self._db.add(transfer)
        await self._db.flush()
        return transfer

    async def validate(
        self,
        transfer: InternalTransfer,
        validated_by: int,
        invoice_id: Optional[int] = None,
        montant_ht: int = 0,
        montant_ttc: int = 0,
    ) -> InternalTransfer:
        transfer.status = "VALIDATED"
        transfer.validated_at = datetime.now(timezone.utc)
        transfer.validated_by = validated_by
        if invoice_id is not None:
            transfer.invoice_id = invoice_id
        transfer.montant_ht = montant_ht
        transfer.montant_ttc = montant_ttc
        await self._db.flush()
        return transfer

    async def cancel(
        self,
        transfer: InternalTransfer,
        raison: Optional[str] = None,
    ) -> InternalTransfer:
        transfer.status = "CANCELLED"
        transfer.cancelled_at = datetime.now(timezone.utc)
        transfer.raison_annulation = raison
        await self._db.flush()
        return transfer

    # ── Lines ──────────────────────────────────────────────────────────────

    async def create_line(
        self,
        transfer_id: int,
        produit_id: int,
        designation: str,
        quantite: float,
        prix_unitaire: int,
        montant_ht: int,
        montant_ttc: int,
        tva_pct: int = 2000,
        unite: str = "U",
        ingredient_id: Optional[int] = None,
    ) -> InternalTransferLine:
        line = InternalTransferLine(
            transfer_id=transfer_id,
            produit_id=produit_id,
            designation=designation,
            ingredient_id=ingredient_id,
            quantite=quantite,
            unite=unite,
            prix_unitaire=prix_unitaire,
            montant_ht=montant_ht,
            tva_pct=tva_pct,
            montant_ttc=montant_ttc,
        )
        self._db.add(line)
        await self._db.flush()
        return line

    async def list_lines(self, transfer_id: int) -> list[InternalTransferLine]:
        result = await self._db.execute(
            select(InternalTransferLine)
            .where(InternalTransferLine.transfer_id == transfer_id)
            .order_by(InternalTransferLine.id)
        )
        return list(result.scalars().all())

    async def update_line_mouvements(
        self,
        line: InternalTransferLine,
        mouvement_epicerie_id: Optional[int] = None,
        mouvement_restaurant_id: Optional[int] = None,
    ) -> InternalTransferLine:
        if mouvement_epicerie_id is not None:
            line.mouvement_epicerie_id = mouvement_epicerie_id
        if mouvement_restaurant_id is not None:
            line.mouvement_restaurant_id = mouvement_restaurant_id
        await self._db.flush()
        return line
