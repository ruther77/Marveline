"""Endpoints CRUD pour les ventes directes."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
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
from app.core.exceptions import NotFound, BadRequest

router = APIRouter(prefix="/ventes", tags=["ventes"])


def _not_found(e: NotFound):
    raise HTTPException(status_code=404, detail=str(e))


def _bad_request(e: BadRequest):
    raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=PaginatedResponse[VenteList])
def list_ventes(
    status: Optional[str] = Query(default=None),
    customer_id: Optional[int] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = svc.list_ventes(
        db, current_user.tenant_id, status=status, customer_id=customer_id, skip=skip, limit=limit
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
def create_vente(
    data: VenteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        vente = svc.create_vente(db, current_user.tenant_id, data)
    except (NotFound, BadRequest) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return VenteResponse.model_validate(vente)


@router.get("/overdue", response_model=PaginatedResponse[VenteList])
def list_overdue(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = svc.get_overdue(db, current_user.tenant_id, skip=skip, limit=limit)
    result = []
    for v in items:
        d = VenteList.model_validate(v)
        if v.customer:
            d.customer_name = v.customer.display_name
        result.append(d)
    return PaginatedResponse(items=result, total=total, skip=skip, limit=limit)


@router.get("/{vente_id}", response_model=VenteResponse)
def get_vente(
    vente_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return VenteResponse.model_validate(svc.get_vente(db, current_user.tenant_id, vente_id))
    except NotFound as e:
        _not_found(e)


@router.patch("/{vente_id}", response_model=VenteResponse)
def update_vente(
    vente_id: int,
    data: VenteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return VenteResponse.model_validate(svc.update_vente(db, current_user.tenant_id, vente_id, data))
    except NotFound as e:
        _not_found(e)
    except BadRequest as e:
        _bad_request(e)


@router.post("/{vente_id}/payments", response_model=VentePaymentResponse, status_code=201)
def add_payment(
    vente_id: int,
    data: VentePaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payment = svc.add_payment(db, current_user.tenant_id, vente_id, data, current_user.id)
        return VentePaymentResponse.model_validate(payment)
    except NotFound as e:
        _not_found(e)
    except BadRequest as e:
        _bad_request(e)


@router.get("/{vente_id}/payments", response_model=list[VentePaymentResponse])
def list_payments(
    vente_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payments = svc.get_payments(db, current_user.tenant_id, vente_id)
        return [VentePaymentResponse.model_validate(p) for p in payments]
    except NotFound as e:
        _not_found(e)


@router.post("/{vente_id}/refund", response_model=VenteResponse)
def refund_vente(
    vente_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return VenteResponse.model_validate(svc.refund_vente(db, current_user.tenant_id, vente_id))
    except NotFound as e:
        _not_found(e)
    except BadRequest as e:
        _bad_request(e)


@router.post("/{vente_id}/cancel", response_model=VenteResponse)
def cancel_vente(
    vente_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return VenteResponse.model_validate(svc.cancel_vente(db, current_user.tenant_id, vente_id))
    except NotFound as e:
        _not_found(e)
    except BadRequest as e:
        _bad_request(e)


@router.get("/{vente_id}/pdf")
def get_vente_pdf(
    vente_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Génère et retourne le PDF de la vente."""
    from app.services.vente_pdf import generate_vente_pdf

    try:
        v = svc.get_vente(db, current_user.tenant_id, vente_id)
    except NotFound as e:
        _not_found(e)

    pdf_bytes = generate_vente_pdf(v)
    filename = f"vente-{v.reference}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
