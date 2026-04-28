"""Endpoints CRUD pour les ventes directes."""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.vente import (
    VenteCreate,
    VenteUpdate,
    VenteResponse,
    VenteList,
    VentePaymentCreate,
    VentePaymentResponse,
)
from app.schemas.common import PaginatedResponse
import app.services.vente as svc
from app.services.vente_pdf import generate_vente_pdf
from app.services.invoice_pdf import load_brand_for_tenant

router = APIRouter(prefix="/ventes", tags=["ventes"])


@router.get("", response_model=PaginatedResponse[VenteList])
async def list_ventes(
    status: Optional[str] = Query(default=None),
    customer_id: Optional[int] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    search: Optional[str] = Query(default=None, min_length=1, max_length=120),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.VENTES_READ)),
):
    items, total = await svc.list_ventes(
        db,
        current_user.tenant_id,
        status=status,
        customer_id=customer_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        skip=skip,
        limit=limit,
    )
    # Enrichir customer_name
    result = []
    for v in items:
        d = VenteList.model_validate(v)
        if v.customer:
            d.customer_name = v.customer.display_name
        result.append(d)
    return PaginatedResponse(items=result, total=total, skip=skip, limit=limit)


@router.post("", response_model=VenteResponse, status_code=201)
async def create_vente(
    data: VenteCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.VENTES_WRITE)),
):
    vente = await svc.create_vente(db, current_user.tenant_id, data)
    return VenteResponse.model_validate(vente)


@router.get("/overdue", response_model=PaginatedResponse[VenteList])
async def list_overdue(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.VENTES_READ)),
):
    items, total = await svc.get_overdue(db, current_user.tenant_id, skip=skip, limit=limit)
    result = []
    for v in items:
        d = VenteList.model_validate(v)
        if v.customer:
            d.customer_name = v.customer.display_name
        result.append(d)
    return PaginatedResponse(items=result, total=total, skip=skip, limit=limit)


@router.get("/{vente_id}", response_model=VenteResponse)
async def get_vente(
    vente_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.VENTES_READ)),
):
    return VenteResponse.model_validate(await svc.get_vente(db, current_user.tenant_id, vente_id))


@router.patch("/{vente_id}", response_model=VenteResponse)
async def update_vente(
    vente_id: int,
    data: VenteUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.VENTES_WRITE)),
):
    return VenteResponse.model_validate(await svc.update_vente(db, current_user.tenant_id, vente_id, data))


@router.post("/{vente_id}/payments", response_model=VentePaymentResponse, status_code=201)
async def add_payment(
    vente_id: int,
    data: VentePaymentCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.VENTES_WRITE)),
):
    payment = await svc.add_payment(db, current_user.tenant_id, vente_id, data, current_user.id)
    return VentePaymentResponse.model_validate(payment)


@router.get("/{vente_id}/payments", response_model=list[VentePaymentResponse])
async def list_payments(
    vente_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.VENTES_READ)),
):
    payments = await svc.get_payments(db, current_user.tenant_id, vente_id)
    return [VentePaymentResponse.model_validate(p) for p in payments]


@router.post("/{vente_id}/refund", response_model=VenteResponse)
async def refund_vente(
    vente_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.VENTES_WRITE)),
):
    return VenteResponse.model_validate(await svc.refund_vente(db, current_user.tenant_id, vente_id))


@router.post("/{vente_id}/cancel", response_model=VenteResponse)
async def cancel_vente(
    vente_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.VENTES_WRITE)),
):
    return VenteResponse.model_validate(await svc.cancel_vente(db, current_user.tenant_id, vente_id))


@router.get("/{vente_id}/pdf")
async def get_vente_pdf(
    vente_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.VENTES_READ)),
):
    """Génère et retourne le PDF de la vente."""
    v = await svc.get_vente(db, current_user.tenant_id, vente_id)
    brand = await load_brand_for_tenant(db, current_user.tenant_id)
    pdf_bytes = generate_vente_pdf(v, brand_name=brand["name"])
    filename = f"vente-{v.reference}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
