"""Service — TransferRequest (BACK-TRANSFER-RESTO-01).

Workflow MVP : create / list / cancel.
Approbation et conversion en InternalTransfer = future phase.
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.repositories.restaurant.transfer_request import AsyncTransferRequestRepo
from app.schemas.restaurant.transfer_request import (
    TransferRequestCreate,
    TransferRequestRead,
)


class TransferRequestService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AsyncTransferRequestRepo(db)

    async def create(
        self,
        tenant_id: int,
        created_by: int,
        payload: TransferRequestCreate,
    ) -> TransferRequestRead:
        # Validation : self-target déjà bloqué par CHECK SQL, mais pre-check
        # pour erreur métier propre (422 vs 500).
        if payload.target_tenant_id == tenant_id:
            raise ValueError("target_tenant_id doit être différent du tenant émetteur")

        lignes_data = [
            {
                "designation": ligne.designation.strip(),
                "quantity": ligne.quantity,
                "unit": ligne.unit,
                "ingredient_restaurant_id": ligne.ingredient_restaurant_id,
                "notes": ligne.notes,
            }
            for ligne in payload.lignes
        ]
        request = await self._repo.create(
            tenant_id=tenant_id,
            target_tenant_id=payload.target_tenant_id,
            created_by=created_by,
            notes=payload.notes,
            lignes_data=lignes_data,
        )
        # Refresh pour charger les server-defaults (created_at, updated_at)
        await self._db.refresh(
            request, attribute_names=["created_at", "updated_at", "lignes"]
        )
        result = TransferRequestRead.model_validate(request)
        await self._db.commit()
        return result

    async def list_for_tenant(
        self,
        tenant_id: int,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[TransferRequestRead], int]:
        items, total = await self._repo.list_paginated(
            tenant_id=tenant_id,
            page=page,
            per_page=per_page,
            status=status,
        )
        return [TransferRequestRead.model_validate(i) for i in items], total

    async def cancel(
        self,
        request_id: int,
        tenant_id: int,
        raison: Optional[str],
    ) -> TransferRequestRead:
        cancelled = await self._repo.cancel(request_id, tenant_id, raison)
        if cancelled is None:
            raise NotFound("TransferRequest")
        # Refresh explicite pour charger updated_at calculé côté DB
        # (onupdate=func.now() — valeur non connue avant SELECT post-flush).
        await self._db.refresh(cancelled, attribute_names=["updated_at", "lignes"])
        result = TransferRequestRead.model_validate(cancelled)
        await self._db.commit()
        return result
