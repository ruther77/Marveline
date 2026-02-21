"""Endpoints CRUD pour les devis avec workflows de transitions d'état."""
import logging
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.devis import DevisService
from app.schemas.devis import (
    DevisCreate,
    DevisUpdate,
    DevisConvert,
    DevisListItem,
    DevisResponse,
    DevisModuleCreate,
    DevisModuleUpdate,
    DevisModuleResponse,
    DevisPhaseCreate,
    DevisPhaseUpdate,
    DevisPhaseResponse,
    DevisVersionResponse,
    DevisNegotiationCreate,
    DevisNegotiationResponse,
    DevisChangeRequestCreate,
    DevisChangeRequestUpdate,
    DevisChangeRequestResponse,
)
from app.schemas.common import PaginationParams, PaginatedResponse
from app.constants import DevisStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devis", tags=["Devis"])


def _get_service(db: Session = Depends(get_db)) -> DevisService:
    return DevisService(db)


@router.get("", response_model=PaginatedResponse[DevisListItem])
def list_devis(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, description="Filtrer par statut"),
    customer_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[DevisListItem]:
    """Liste tous les devis du tenant avec pagination et filtres."""
    svc = DevisService(db)
    devis_list = svc.list(
        tenant_id=current_user.tenant_id,
        status=status_filter,
        customer_id=customer_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    total = len(devis_list)
    items = []
    for d in devis_list:
        customer_name = ""
        if d.customer:
            customer_name = f"{d.customer.first_name} {d.customer.last_name}".strip()
        items.append(DevisListItem(
            id=d.id,
            reference=d.reference,
            status=d.status,
            customer_id=d.customer_id,
            customer_name=customer_name,
            total_cents=d.total_cents,
            valid_until=d.valid_until,
            event_date=d.event_date,
            created_at=d.created_at,
            updated_at=d.updated_at,
            is_active=d.is_active,
        ))
    return PaginatedResponse(items=items, total=total, skip=pagination.skip, limit=pagination.limit)


@router.get("/{devis_id}", response_model=DevisResponse)
def get_devis(
    devis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisResponse:
    """Récupère un devis complet avec toutes ses relations."""
    svc = DevisService(db)
    d = svc.get(devis_id, current_user.tenant_id)
    customer_name = ""
    if d.customer:
        customer_name = f"{d.customer.first_name} {d.customer.last_name}".strip()
    return DevisResponse(
        id=d.id,
        tenant_id=d.tenant_id,
        reference=d.reference,
        customer_id=d.customer_id,
        customer_name=customer_name,
        status=d.status,
        event_date=d.event_date,
        event_location=d.event_location,
        valid_until=d.valid_until,
        tva_rate=d.tva_rate,
        subtotal_cents=d.subtotal_cents,
        tva_cents=d.tva_cents,
        total_cents=d.total_cents,
        discount_pct=d.discount_pct,
        caution_required=d.caution_required,
        caution_amount_cents=d.caution_amount_cents,
        notes=d.notes,
        converted_reservation_id=d.converted_reservation_id,
        created_at=d.created_at,
        updated_at=d.updated_at,
        is_active=d.is_active,
        lines=[
            {
                "id": l.id, "devis_id": l.devis_id, "product_id": l.product_id,
                "label": l.label, "quantity": l.quantity,
                "unit_price_cents": l.unit_price_cents, "discount_pct": l.discount_pct,
                "subtotal_cents": l.subtotal_cents, "sort_order": l.sort_order,
                "created_at": l.created_at, "updated_at": l.updated_at,
            }
            for l in d.lines
        ],
        modules=[
            {
                "id": m.id, "devis_id": m.devis_id, "module_type": m.module_type,
                "label": m.label, "content_json": m.content_json, "is_active": m.is_active,
                "created_at": m.created_at, "updated_at": m.updated_at,
            }
            for m in d.modules
        ],
        phases=[
            {
                "id": p.id, "devis_id": p.devis_id, "label": p.label,
                "date_start": p.date_start, "date_end": p.date_end,
                "sort_order": p.sort_order, "is_active": p.is_active,
                "created_at": p.created_at, "updated_at": p.updated_at,
            }
            for p in d.phases
        ],
        negotiations=[
            {
                "id": n.id, "devis_id": n.devis_id, "author_id": n.author_id,
                "message": n.message, "proposed_amount_cents": n.proposed_amount_cents,
                "created_at": n.created_at,
            }
            for n in d.negotiations
        ],
        change_requests=[
            {
                "id": cr.id, "devis_id": cr.devis_id, "author_id": cr.author_id,
                "description": cr.description, "status": cr.status,
                "created_at": cr.created_at, "updated_at": cr.updated_at,
            }
            for cr in d.change_requests
        ],
    )


@router.post("", response_model=DevisResponse, status_code=status.HTTP_201_CREATED)
def create_devis(
    payload: DevisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisResponse:
    """Crée un nouveau devis en statut draft."""
    svc = DevisService(db)
    d = svc.create(current_user.tenant_id, payload)
    db.commit()
    db.refresh(d)
    return get_devis(d.id, db, current_user)


@router.patch("/{devis_id}", response_model=DevisResponse)
def update_devis(
    devis_id: int,
    payload: DevisUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisResponse:
    """Met à jour un devis (seulement en statut draft)."""
    svc = DevisService(db)
    svc.update(devis_id, current_user.tenant_id, payload)
    db.commit()
    return get_devis(devis_id, db, current_user)


@router.post("/{devis_id}/send", response_model=DevisResponse)
def send_devis(
    devis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisResponse:
    """Envoie le devis au client (draft → sent). Crée un snapshot v1."""
    svc = DevisService(db)
    svc.send(devis_id, current_user.tenant_id, current_user.id)
    db.commit()
    return get_devis(devis_id, db, current_user)


@router.post("/{devis_id}/accept", response_model=DevisResponse)
def accept_devis(
    devis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisResponse:
    """Accepte le devis."""
    svc = DevisService(db)
    svc.accept(devis_id, current_user.tenant_id)
    db.commit()
    return get_devis(devis_id, db, current_user)


@router.post("/{devis_id}/refuse", response_model=DevisResponse)
def refuse_devis(
    devis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisResponse:
    """Refuse le devis."""
    svc = DevisService(db)
    svc.refuse(devis_id, current_user.tenant_id)
    db.commit()
    return get_devis(devis_id, db, current_user)


@router.post("/{devis_id}/cancel", response_model=DevisResponse)
def cancel_devis(
    devis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisResponse:
    """Annule le devis."""
    svc = DevisService(db)
    svc.cancel(devis_id, current_user.tenant_id)
    db.commit()
    return get_devis(devis_id, db, current_user)


@router.post("/{devis_id}/renew", response_model=DevisResponse)
def renew_devis(
    devis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisResponse:
    """Renouvelle un devis expiré (crée un nouveau brouillon, validité +30 jours)."""
    from datetime import timedelta
    new_valid_until = (date.today() + timedelta(days=30)).isoformat()
    svc = DevisService(db)
    new_devis = svc.renew(devis_id, current_user.tenant_id, new_valid_until)
    db.commit()
    return get_devis(new_devis.id, db, current_user)


@router.post("/{devis_id}/convert", response_model=dict)
def convert_devis(
    devis_id: int,
    payload: DevisConvert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Convertit un devis accepté en réservation."""
    svc = DevisService(db)
    reservation = svc.convert_to_reservation(devis_id, current_user.tenant_id, payload)
    db.commit()
    return {"reservation_id": reservation.id, "devis_id": devis_id}


@router.get("/{devis_id}/versions", response_model=list[DevisVersionResponse])
def list_versions(
    devis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DevisVersionResponse]:
    """Liste toutes les versions (snapshots) du devis."""
    svc = DevisService(db)
    return svc.list_versions(devis_id, current_user.tenant_id)


@router.post("/{devis_id}/negotiation", response_model=DevisNegotiationResponse, status_code=status.HTTP_201_CREATED)
def add_negotiation(
    devis_id: int,
    payload: DevisNegotiationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisNegotiationResponse:
    """Ajoute un message de négociation."""
    svc = DevisService(db)
    n = svc.add_negotiation(devis_id, current_user.tenant_id, current_user.id, payload)
    db.commit()
    db.refresh(n)
    return DevisNegotiationResponse(
        id=n.id, devis_id=n.devis_id, author_id=n.author_id,
        message=n.message, proposed_amount_cents=n.proposed_amount_cents,
        created_at=n.created_at,
    )


@router.post("/{devis_id}/change-request", response_model=DevisChangeRequestResponse, status_code=status.HTTP_201_CREATED)
def add_change_request(
    devis_id: int,
    payload: DevisChangeRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisChangeRequestResponse:
    """Crée une demande de modification."""
    svc = DevisService(db)
    cr = svc.add_change_request(devis_id, current_user.tenant_id, current_user.id, payload)
    db.commit()
    db.refresh(cr)
    return DevisChangeRequestResponse(
        id=cr.id, devis_id=cr.devis_id, author_id=cr.author_id,
        description=cr.description, status=cr.status,
        created_at=cr.created_at, updated_at=cr.updated_at,
    )


@router.patch("/{devis_id}/change-request/{cr_id}", response_model=DevisChangeRequestResponse)
def update_change_request(
    devis_id: int,
    cr_id: int,
    payload: DevisChangeRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisChangeRequestResponse:
    """Met à jour le statut d'une demande de modification."""
    svc = DevisService(db)
    cr = svc.update_change_request(devis_id, current_user.tenant_id, cr_id, payload)
    db.commit()
    db.refresh(cr)
    return DevisChangeRequestResponse(
        id=cr.id, devis_id=cr.devis_id, author_id=cr.author_id,
        description=cr.description, status=cr.status,
        created_at=cr.created_at, updated_at=cr.updated_at,
    )


@router.post("/{devis_id}/modules", response_model=DevisModuleResponse, status_code=status.HTTP_201_CREATED)
def add_module(
    devis_id: int,
    payload: DevisModuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisModuleResponse:
    """Ajoute un module au devis."""
    svc = DevisService(db)
    m = svc.add_module(devis_id, current_user.tenant_id, payload)
    db.commit()
    db.refresh(m)
    return DevisModuleResponse(
        id=m.id, devis_id=m.devis_id, module_type=m.module_type,
        label=m.label, content_json=m.content_json, is_active=m.is_active,
        created_at=m.created_at, updated_at=m.updated_at,
    )


@router.patch("/{devis_id}/modules/{module_id}", response_model=DevisModuleResponse)
def update_module(
    devis_id: int,
    module_id: int,
    payload: DevisModuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisModuleResponse:
    """Met à jour un module du devis."""
    svc = DevisService(db)
    m = svc.update_module(devis_id, current_user.tenant_id, module_id, payload)
    db.commit()
    db.refresh(m)
    return DevisModuleResponse(
        id=m.id, devis_id=m.devis_id, module_type=m.module_type,
        label=m.label, content_json=m.content_json, is_active=m.is_active,
        created_at=m.created_at, updated_at=m.updated_at,
    )


@router.post("/{devis_id}/phases", response_model=DevisPhaseResponse, status_code=status.HTTP_201_CREATED)
def add_phase(
    devis_id: int,
    payload: DevisPhaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisPhaseResponse:
    """Ajoute une phase au devis."""
    svc = DevisService(db)
    p = svc.add_phase(devis_id, current_user.tenant_id, payload)
    db.commit()
    db.refresh(p)
    return DevisPhaseResponse(
        id=p.id, devis_id=p.devis_id, label=p.label,
        date_start=p.date_start, date_end=p.date_end,
        sort_order=p.sort_order, is_active=p.is_active,
        created_at=p.created_at, updated_at=p.updated_at,
    )


@router.patch("/{devis_id}/phases/{phase_id}", response_model=DevisPhaseResponse)
def update_phase(
    devis_id: int,
    phase_id: int,
    payload: DevisPhaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisPhaseResponse:
    """Met à jour une phase du devis."""
    svc = DevisService(db)
    p = svc.update_phase(devis_id, current_user.tenant_id, phase_id, payload)
    db.commit()
    db.refresh(p)
    return DevisPhaseResponse(
        id=p.id, devis_id=p.devis_id, label=p.label,
        date_start=p.date_start, date_end=p.date_end,
        sort_order=p.sort_order, is_active=p.is_active,
        created_at=p.created_at, updated_at=p.updated_at,
    )


# ── PDF & Duplication ──────────────────────────────────────────────────────────


@router.get("/{devis_id}/pdf")
def get_devis_pdf(
    devis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Génère et retourne le PDF du devis."""
    from app.services.devis_pdf import generate_devis_pdf

    svc = DevisService(db)
    d = svc.get(devis_id, current_user.tenant_id)
    pdf_bytes = generate_devis_pdf(d)
    filename = f"devis-{d.reference}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/{devis_id}/duplicate", response_model=DevisResponse, status_code=status.HTTP_201_CREATED)
def duplicate_devis(
    devis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevisResponse:
    """Duplique un devis existant en brouillon avec une nouvelle référence."""
    svc = DevisService(db)
    new_devis = svc.duplicate(devis_id, current_user.tenant_id)
    return get_devis(new_devis.id, db, current_user)
