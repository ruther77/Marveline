"""Endpoints — Demandes de transfert ENTRANTES côté épicerie (BACK-TRANSFER-RESTO-01).

3 endpoints :
  GET    /epicerie/transfer-requests                  (liste demandes ciblant ce tenant)
  POST   /epicerie/transfer-requests/{id}/approuver   (status PENDING → APPROVED)
  POST   /epicerie/transfer-requests/{id}/rejeter     (status PENDING → REJECTED)

Multi-tenant strict : le repo filtre sur `target_tenant_id = current_user.tenant_id`.
Un tenant épicerie ne peut JAMAIS approuver/rejeter une demande qui ne le cible pas.

Hors scope MVP : conversion automatique en InternalTransfer (= phase suivante).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.exceptions import BadRequest, NotFound
from app.core.permissions import Scope
from app.schemas.restaurant.ingredient_epicerie_mapping import (
    ApproveWithTransferRequest,
    ApproveWithTransferResponse,
    PreviewResolutionResponse,
)
from app.schemas.restaurant.transfer_request import (
    TransferRequestListResponse,
    TransferRequestRead,
    TransferRequestReject,
)
from app.services.epicerie.transfer_request import EpicerieTransferRequestService

router = APIRouter(
    prefix="/epicerie/transfer-requests",
    tags=["Épicerie — Demandes de transfert"],
)


@router.get("", response_model=TransferRequestListResponse)
async def list_inbound(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.EPICERIE_READ)),
) -> TransferRequestListResponse:
    """Demandes de transfert reçues par le tenant épicerie courant."""
    service = EpicerieTransferRequestService(db)
    items, total = await service.list_inbound(
        target_tenant_id=current_user.tenant_id,
        page=page,
        per_page=per_page,
        status=status_filter,
    )
    return TransferRequestListResponse(
        items=items, total=total, page=page, per_page=per_page,
    )


@router.post("/{request_id}/approuver", response_model=TransferRequestRead)
async def approuver(
    request_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.EPICERIE_WRITE)),
) -> TransferRequestRead:
    """Approuve une demande PENDING (status → APPROVED).

    NB : la conversion en `InternalTransfer` (mouvement stock effectif) sera
    câblée dans une future phase. Pour l'instant, l'approbation est juste
    un signal métier.
    """
    service = EpicerieTransferRequestService(db)
    try:
        return await service.approve(
            request_id=request_id,
            target_tenant_id=current_user.tenant_id,
        )
    except NotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande introuvable, déjà traitée ou hors tenant",
        ) from e


@router.post(
    "/{request_id}/preview-resolution",
    response_model=PreviewResolutionResponse,
)
async def preview_resolution(
    request_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.EPICERIE_READ)),
) -> PreviewResolutionResponse:
    """Dry-run du résolveur cascade sur toutes les lignes d'une demande.

    Retourne, par ligne de demande, la proposition de prélèvement sur les
    produits épicerie (cascade mixte) + flag de déficit.
    Ne modifie rien en base.
    """
    service = EpicerieTransferRequestService(db)
    try:
        return await service.preview_resolution(
            request_id=request_id,
            target_tenant_id=current_user.tenant_id,
        )
    except NotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande introuvable ou hors tenant",
        ) from e


@router.post(
    "/{request_id}/approve-with-transfer",
    response_model=ApproveWithTransferResponse,
)
async def approve_with_transfer(
    request_id: int,
    payload: ApproveWithTransferRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.EPICERIE_WRITE)),
) -> ApproveWithTransferResponse:
    """Approuve la demande et crée un `InternalTransfer` PENDING.

    - Si `overrides` fourni : utilise ces lignes telles quelles.
    - Sinon : calcule automatiquement la résolution cascade depuis les
      mappings ingrédient ↔ produit épicerie.
    La demande passe à FULFILLED ; le transfert physique est validé
    séparément via l'endpoint de validation transferts.
    """
    service = EpicerieTransferRequestService(db)
    try:
        result = await service.approve_with_transfer(
            request_id=request_id,
            target_tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            payload=payload,
        )
        await db.commit()
        return result
    except NotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande introuvable, déjà traitée ou hors tenant",
        ) from e
    except BadRequest as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        ) from e


@router.post("/{request_id}/rejeter", response_model=TransferRequestRead)
async def rejeter(
    request_id: int,
    payload: Optional[TransferRequestReject] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.EPICERIE_WRITE)),
) -> TransferRequestRead:
    """Rejette une demande PENDING (status → REJECTED) avec raison optionnelle."""
    service = EpicerieTransferRequestService(db)
    raison = payload.raison if payload else None
    try:
        return await service.reject(
            request_id=request_id,
            target_tenant_id=current_user.tenant_id,
            raison=raison,
        )
    except NotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demande introuvable, déjà traitée ou hors tenant",
        ) from e
