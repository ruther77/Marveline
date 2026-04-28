"""Repository — TransferRequest (BACK-TRANSFER-RESTO-01).

Multi-tenant strict (A1) : toutes les méthodes filtrent par tenant_id du
restaurant émetteur. Aucune lecture/écriture cross-tenant possible.
"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.transfer_request import TransferRequest, TransferRequestLine


class AsyncTransferRequestRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(
        self, request_id: int, tenant_id: int
    ) -> Optional[TransferRequest]:
        """Retourne la demande si elle appartient au tenant, sinon None."""
        stmt = select(TransferRequest).where(
            TransferRequest.id == request_id,
            TransferRequest.tenant_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        tenant_id: int,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
        active_only: bool = True,
    ) -> tuple[list[TransferRequest], int]:
        base_filters = [TransferRequest.tenant_id == tenant_id]
        if active_only:
            base_filters.append(TransferRequest.is_active.is_(True))
        if status:
            base_filters.append(TransferRequest.status == status)

        count_stmt = select(func.count()).select_from(TransferRequest).where(*base_filters)
        total = (await self._db.execute(count_stmt)).scalar_one()

        stmt = (
            select(TransferRequest)
            .where(*base_filters)
            .order_by(TransferRequest.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        items = list((await self._db.execute(stmt)).scalars())
        return items, total

    async def create(
        self,
        tenant_id: int,
        target_tenant_id: int,
        created_by: int,
        notes: Optional[str],
        lignes_data: list[dict],
    ) -> TransferRequest:
        request = TransferRequest(
            tenant_id=tenant_id,
            target_tenant_id=target_tenant_id,
            status="PENDING",
            notes=notes,
            created_by=created_by,
        )
        self._db.add(request)
        await self._db.flush()
        for ld in lignes_data:
            ligne = TransferRequestLine(
                request_id=request.id,
                designation=ld["designation"],
                quantity=ld["quantity"],
                unit=ld.get("unit", "kg"),
                ingredient_restaurant_id=ld.get("ingredient_restaurant_id"),
                notes=ld.get("notes"),
            )
            self._db.add(ligne)
        await self._db.flush()
        await self._db.refresh(request, attribute_names=["lignes"])
        return request

    async def cancel(
        self, request_id: int, tenant_id: int, raison: Optional[str]
    ) -> Optional[TransferRequest]:
        """Annule une demande PENDING. Retourne None si non trouvée ou état invalide."""
        request = await self.get(request_id, tenant_id)
        if request is None or request.status != "PENDING":
            return None
        request.status = "CANCELLED"
        request.rejection_reason = raison
        await self._db.flush()
        await self._db.refresh(request, attribute_names=["lignes"])
        return request

    # ── Vue côté épicerie (cible) ────────────────────────────────────────────

    async def get_for_target(
        self, request_id: int, target_tenant_id: int
    ) -> Optional[TransferRequest]:
        """Retourne la demande si elle cible le tenant épicerie courant."""
        stmt = select(TransferRequest).where(
            TransferRequest.id == request_id,
            TransferRequest.target_tenant_id == target_tenant_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_inbound(
        self,
        target_tenant_id: int,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[TransferRequest], int]:
        """Liste paginée des demandes ENTRANTES (target = épicerie courante)."""
        base_filters = [
            TransferRequest.target_tenant_id == target_tenant_id,
            TransferRequest.is_active.is_(True),
        ]
        if status:
            base_filters.append(TransferRequest.status == status)

        count_stmt = select(func.count()).select_from(TransferRequest).where(*base_filters)
        total = (await self._db.execute(count_stmt)).scalar_one()

        stmt = (
            select(TransferRequest)
            .where(*base_filters)
            .order_by(TransferRequest.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        items = list((await self._db.execute(stmt)).scalars())
        return items, total

    async def approve(
        self,
        request_id: int,
        target_tenant_id: int,
        fulfilled_transfer_id: Optional[int] = None,
    ) -> Optional[TransferRequest]:
        """Approuve une demande PENDING (côté épicerie)."""
        request = await self.get_for_target(request_id, target_tenant_id)
        if request is None or request.status != "PENDING":
            return None
        request.status = "APPROVED" if fulfilled_transfer_id is None else "FULFILLED"
        if fulfilled_transfer_id is not None:
            request.fulfilled_transfer_id = fulfilled_transfer_id
        await self._db.flush()
        await self._db.refresh(request, attribute_names=["lignes"])
        return request

    async def reject(
        self, request_id: int, target_tenant_id: int, raison: Optional[str]
    ) -> Optional[TransferRequest]:
        """Rejette une demande PENDING (côté épicerie)."""
        request = await self.get_for_target(request_id, target_tenant_id)
        if request is None or request.status != "PENDING":
            return None
        request.status = "REJECTED"
        request.rejection_reason = raison
        await self._db.flush()
        await self._db.refresh(request, attribute_names=["lignes"])
        return request
