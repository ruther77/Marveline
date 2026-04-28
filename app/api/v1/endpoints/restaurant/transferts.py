"""Endpoints — Demandes de transfert restaurant → épicerie (BACK-TRANSFER-RESTO-01).

3 endpoints MVP :
  POST   /restaurant/transferts/demander    (staff resto: create PENDING request)
  GET    /restaurant/transferts             (staff resto: list with pagination + filter status)
  POST   /restaurant/transferts/{id}/annuler (staff resto: cancel PENDING request)

Multi-tenant strict : current_user.tenant_id propagé à tous les appels service.
Le tenant restaurant ne peut JAMAIS lire/modifier les demandes d'un autre tenant.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.exceptions import NotFound
from app.core.permissions import Scope
from app.schemas.restaurant.transfer_request import (
    TransferRequestCancel,
    TransferRequestCreate,
    TransferRequestListResponse,
    TransferRequestRead,
)
from app.services.restaurant.transfer_request import TransferRequestService

router = APIRouter(prefix="/restaurant/transferts", tags=["Restaurant — Transferts"])


@router.post(
    "/demander",
    response_model=TransferRequestRead,
    status_code=status.HTTP_201_CREATED,
)
async def demander_transfert(
    payload: TransferRequestCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> TransferRequestRead:
    """Crée une demande de transfert vers l'épicerie cible (status=PENDING)."""
    service = TransferRequestService(db)
    try:
        return await service.create(
            tenant_id=current_user.tenant_id,
            created_by=current_user.id,
            payload=payload,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e


@router.get("", response_model=TransferRequestListResponse)
async def list_transferts(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_READ)),
) -> TransferRequestListResponse:
    """Liste paginée des demandes émises par le tenant restaurant courant."""
    service = TransferRequestService(db)
    items, total = await service.list_for_tenant(
        tenant_id=current_user.tenant_id,
        page=page,
        per_page=per_page,
        status=status_filter,
    )
    return TransferRequestListResponse(
        items=items, total=total, page=page, per_page=per_page,
    )


@router.post("/{request_id}/annuler", response_model=TransferRequestRead)
async def annuler_transfert(
    request_id: int,
    payload: Optional[TransferRequestCancel] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESTAURANT_WRITE)),
) -> TransferRequestRead:
    """Annule une demande PENDING. 404 si introuvable ou état non-annulable."""
    service = TransferRequestService(db)
    raison = payload.raison if payload else None
    try:
        return await service.cancel(
            request_id=request_id,
            tenant_id=current_user.tenant_id,
            raison=raison,
        )
    except NotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande introuvable ou non annulable",
        ) from e
