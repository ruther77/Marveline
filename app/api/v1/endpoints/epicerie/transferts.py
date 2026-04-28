"""Endpoints Transferts internes epicerie -> restaurant.

5 routes :
  GET  /epicerie/transferts              — liste paginee
  GET  /epicerie/transferts/{id}         — detail
  POST /epicerie/transferts              — creer (PENDING)
  POST /epicerie/transferts/{id}/valider — valider (stock + invoice)
  POST /epicerie/transferts/{id}/annuler — annuler (CANCELLED)

tenant_id = current_user.tenant_id sur toutes les routes.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope
from app.core.permissions import Scope
from app.repositories.epicerie.internal_transfer import AsyncInternalTransferRepository
from app.repositories.finance.invoice import AsyncFinanceInvoiceRepository
from app.schemas.epicerie.transfert import (
    AnnulationPayload,
    InternalTransferCreate,
    InternalTransferLineRead,
    InternalTransferListResponse,
    InternalTransferRead,
)
from app.services.epicerie.transfert import (
    annuler_transfert,
    creer_transfert,
    valider_transfert,
)

router = APIRouter(prefix="/epicerie/transferts", tags=["Epicerie — Transferts"])


async def _build_transfer_read(
    transfer,
    repo: AsyncInternalTransferRepository,
    db: AsyncSession,
) -> InternalTransferRead:
    """Construit le schema de lecture avec lignes chargees."""
    lignes = await repo.list_lines(transfer.id)
    invoice_numero = None
    invoice_statut = None
    if transfer.invoice_id is not None:
        invoice_repo = AsyncFinanceInvoiceRepository(db)
        invoice = await invoice_repo.get_by_id(transfer.invoice_id, transfer.tenant_id)
        if invoice is not None:
            invoice_numero = invoice.numero
            invoice_statut = invoice.statut

    return InternalTransferRead(
        id=transfer.id,
        tenant_id=transfer.tenant_id,
        dest_tenant_id=transfer.dest_tenant_id,
        reference=transfer.reference,
        status=transfer.status,
        notes=transfer.notes,
        montant_ht=transfer.montant_ht or 0,
        montant_ttc=transfer.montant_ttc or 0,
        invoice_id=transfer.invoice_id,
        invoice_numero=invoice_numero,
        invoice_statut=invoice_statut,
        created_by=transfer.created_by,
        validated_at=transfer.validated_at,
        validated_by=transfer.validated_by,
        cancelled_at=transfer.cancelled_at,
        raison_annulation=transfer.raison_annulation,
        created_at=transfer.created_at,
        lignes=[InternalTransferLineRead.model_validate(l) for l in lignes],
    )


@router.get("", response_model=InternalTransferListResponse)
async def list_transferts(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Liste paginee des transferts internes."""
    repo = AsyncInternalTransferRepository(db)
    items, total = await repo.list_paginated(
        tenant_id=current_user.tenant_id,
        page=page,
        per_page=per_page,
        status=status,
    )
    transfers_read = []
    for transfer in items:
        transfers_read.append(await _build_transfer_read(transfer, repo, db))
    return InternalTransferListResponse(
        items=transfers_read, total=total, page=page, per_page=per_page,
    )


@router.get("/{transfer_id}", response_model=InternalTransferRead)
async def get_transfert(
    transfer_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """Detail d'un transfert interne."""
    repo = AsyncInternalTransferRepository(db)
    transfer = await repo.get_by_id(transfer_id, current_user.tenant_id)
    if transfer is None:
        raise HTTPException(status_code=404, detail="Transfert introuvable")
    return await _build_transfer_read(transfer, repo, db)


@router.post("", response_model=InternalTransferRead, status_code=201)
async def create_transfert(
    payload: InternalTransferCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Cree un transfert interne (PENDING)."""
    repo = AsyncInternalTransferRepository(db)
    transfer = await creer_transfert(
        db, current_user.tenant_id, payload, current_user.id,
    )
    return await _build_transfer_read(transfer, repo, db)


@router.post("/{transfer_id}/valider", response_model=InternalTransferRead)
async def valider(
    transfer_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Validation atomique du transfert (stock + mouvements + facture)."""
    repo = AsyncInternalTransferRepository(db)
    transfer = await valider_transfert(
        db, current_user.tenant_id, transfer_id, current_user.id,
    )
    return await _build_transfer_read(transfer, repo, db)


@router.post("/{transfer_id}/annuler", response_model=InternalTransferRead)
async def annuler(
    transfer_id: int,
    payload: Optional[AnnulationPayload] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_WRITE)),
):
    """Annule un transfert PENDING."""
    raison = payload.raison if payload else None
    repo = AsyncInternalTransferRepository(db)
    transfer = await annuler_transfert(
        db, current_user.tenant_id, transfer_id, raison,
    )
    return await _build_transfer_read(transfer, repo, db)
