"""Endpoints CRUD pour les devis avec workflows de transitions d'état."""
import logging
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.models.devis import Devis
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
    DevisSignatureRequest,
    DevisSignatureResponse,
    DevisConvertResponse,
    DevisCoverageResponse,
    DevisCoverageItemCreate,
    DevisCoverageItemUpdate,
    DevisCoverageItemResponse,
    DevisRefuseRequest,
    DevisNegotiationConcludeRequest,
)
from app.schemas.common import PaginationParams, PaginatedResponse
from app.constants import DevisStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devis", tags=["Devis"])


# ── Helpers de construction réponse ───────────────────────────────────────────


def _build_devis_response(d, converted_reservation_reference: Optional[str] = None) -> DevisResponse:
    """Construit un DevisResponse depuis un objet Devis ORM."""
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
        delivery_date=getattr(d, "delivery_date", None),
        return_date=getattr(d, "return_date", None),
        refusal_reason=getattr(d, "refusal_reason", None),
        valid_until=d.valid_until,
        tva_rate=d.tva_rate,
        subtotal_cents=d.subtotal_cents,
        tva_cents=d.tva_cents,
        total_cents=d.total_cents,
        discount_pct=d.discount_pct,
        caution_required=d.caution_required,
        caution_amount_cents=d.caution_amount_cents,
        notes=d.notes,
        conditions_paiement=getattr(d, "conditions_paiement", None),
        message_accompagnement=getattr(d, "message_accompagnement", None),
        signature_url=getattr(d, "signature_url", None),
        signed_at=getattr(d, "signed_at", None),
        converted_reservation_id=d.converted_reservation_id,
        converted_reservation_reference=converted_reservation_reference,
        created_at=d.created_at,
        updated_at=d.updated_at,
        is_active=d.is_active,
        lines=[
            {
                "id": l.id, "devis_id": l.devis_id, "product_id": l.product_id,
                "bundle_id": l.bundle_id, "variant_id": l.variant_id,
                "variant_label": l.variant.label if getattr(l, "variant", None) else None,
                "label": l.label, "quantity": l.quantity,
                "unit_price_cents": l.unit_price_cents, "discount_pct": l.discount_pct,
                "subtotal_cents": l.subtotal_cents, "sort_order": l.sort_order,
                "bundle_name": l.bundle.name if l.bundle else None,
                "bundle_items": [
                    {
                        "product_id": bi.product_id,
                        "product_name": bi.product.name if bi.product else "",
                        "variant_id": bi.variant_id,
                        "variant_label": bi.variant.label if getattr(bi, "variant", None) else None,
                        "quantity": bi.quantity,
                        "display_order": bi.display_order,
                    }
                    for bi in l.bundle.items
                ] if l.bundle and hasattr(l.bundle, "items") else None,
                "weight_grams": getattr(l.product, "weight_grams", None) if l.product else None,
                "volume_cm3": getattr(l.product, "volume_cm3", None) if l.product else None,
                "created_at": l.created_at, "updated_at": l.updated_at,
            }
            for l in d.lines
        ],
        modules=[
            {
                "id": m.id, "devis_id": m.devis_id, "module_type": m.module_type,
                "label": m.label, "content_json": m.content_json,
                "delivery_status": getattr(m, "delivery_status", "a_cadrer"),
                "is_active": m.is_active,
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


# ── Stats (KPI) ───────────────────────────────────────────────────────────────


@router.get("/stats")
async def devis_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.DEVIS_READ)),
) -> dict[str, int]:
    """Compteurs agrégés par statut — 1 requête SQL au lieu de N appels list."""
    result = await db.execute(
        select(Devis.status, func.count())
        .where(
            Devis.tenant_id == current_user.tenant_id,
            Devis.is_active == True,  # noqa: E712
        )
        .group_by(Devis.status)
    )
    counts = {row[0]: row[1] for row in result.all()}
    return counts


# ── Liste & Détail ─────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[DevisListItem])
async def list_devis(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrer par statut"),
    customer_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    search: Optional[str] = Query(None, description="Recherche sur la référence"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_READ)),
) -> PaginatedResponse[DevisListItem]:
    """Liste tous les devis du tenant avec pagination et filtres."""
    svc = DevisService(db)
    devis_list, total = await svc.list(
        tenant_id=current_user.tenant_id,
        status=status_filter,
        customer_id=customer_id,
        search=search,
        skip=pagination.skip,
        limit=pagination.limit,
    )
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
async def get_devis(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_READ)),
) -> DevisResponse:
    """Récupère un devis complet avec toutes ses relations."""
    svc = DevisService(db)
    d = await svc.get(devis_id, current_user.tenant_id)
    resa_ref: Optional[str] = None
    if d.converted_reservation_id:
        from app.models.reservation import Reservation
        resa_ref = await db.scalar(
            select(Reservation.reference).where(
                Reservation.id == d.converted_reservation_id,
                Reservation.tenant_id == current_user.tenant_id,
            )
        )
    return _build_devis_response(d, converted_reservation_reference=resa_ref)


# ── CRUD ──────────────────────────────────────────────────────────────────────


@router.post("", response_model=DevisResponse, status_code=status.HTTP_201_CREATED)
async def create_devis(
    payload: DevisCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisResponse:
    """Crée un nouveau devis en statut draft."""
    svc = DevisService(db)
    d = await svc.create(current_user.tenant_id, payload)
    return _build_devis_response(d)


@router.patch("/{devis_id}", response_model=DevisResponse)
async def update_devis(
    devis_id: int,
    payload: DevisUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisResponse:
    """Met à jour un devis (seulement en statut draft)."""
    svc = DevisService(db)
    d = await svc.update(devis_id, current_user.tenant_id, payload)
    return _build_devis_response(d)


# ── Transitions d'état ────────────────────────────────────────────────────────


@router.post("/{devis_id}/send", response_model=DevisResponse)
async def send_devis(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisResponse:
    """Envoie le devis au client (draft → sent). Crée un snapshot v1."""
    svc = DevisService(db)
    d = await svc.send(devis_id, current_user.tenant_id, current_user.id)
    return _build_devis_response(d)


@router.post("/{devis_id}/accept", response_model=DevisResponse)
async def accept_devis(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisResponse:
    """Accepte le devis et fige une version (snapshot du contrat signé)."""
    svc = DevisService(db)
    d = await svc.accept(devis_id, current_user.tenant_id, current_user.id)
    return _build_devis_response(d)


@router.post("/{devis_id}/negotiation/start", response_model=DevisResponse)
async def start_negotiation(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisResponse:
    """Démarre (ou reprend) la négociation du devis."""
    svc = DevisService(db)
    d = await svc.start_negotiation(devis_id, current_user.tenant_id)
    return _build_devis_response(d)


@router.post("/{devis_id}/version-pending", response_model=DevisResponse)
async def mark_version_pending(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisResponse:
    """Marque le devis en attente d'une nouvelle version (negotiation -> version_pending)."""
    svc = DevisService(db)
    d = await svc.mark_version_pending(devis_id, current_user.tenant_id)
    return _build_devis_response(d)


@router.post("/{devis_id}/refuse", response_model=DevisResponse)
async def refuse_devis(
    devis_id: int,
    payload: Optional[DevisRefuseRequest] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisResponse:
    """Refuse le devis avec raison optionnelle."""
    svc = DevisService(db)
    reason = payload.reason if payload else None
    d = await svc.refuse(devis_id, current_user.tenant_id, reason=reason)
    return _build_devis_response(d)


@router.post("/{devis_id}/cancel", response_model=DevisResponse)
async def cancel_devis(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisResponse:
    """Annule le devis."""
    svc = DevisService(db)
    d = await svc.cancel(devis_id, current_user.tenant_id)
    return _build_devis_response(d)


@router.post("/{devis_id}/expire", response_model=DevisResponse)
async def expire_devis(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisResponse:
    """Marque un devis envoyé comme expiré."""
    svc = DevisService(db)
    d = await svc.expire(devis_id, current_user.tenant_id)
    return _build_devis_response(d)


@router.post("/{devis_id}/renew", response_model=DevisResponse)
async def renew_devis(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisResponse:
    """Renouvelle un devis expiré (crée un nouveau brouillon, validité +30 jours)."""
    from datetime import timedelta
    new_valid_until = (date.today() + timedelta(days=30)).isoformat()
    svc = DevisService(db)
    d = await svc.renew(devis_id, current_user.tenant_id, new_valid_until)
    return _build_devis_response(d)


@router.post("/{devis_id}/convert", response_model=DevisConvertResponse)
async def convert_devis(
    devis_id: int,
    payload: DevisConvert,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisConvertResponse:
    """Convertit un devis accepté en réservation et snapshot la version finale."""
    svc = DevisService(db)
    devis = await svc.convert_to_reservation(
        devis_id, current_user.tenant_id, payload, current_user.id,
    )
    await db.commit()
    return DevisConvertResponse(
        reservation_id=devis.converted_reservation_id,
        devis_id=devis_id,
        status=devis.status,
        converted_reservation_id=devis.converted_reservation_id,
    )


# ── Versions ──────────────────────────────────────────────────────────────────


@router.get("/{devis_id}/versions", response_model=list[DevisVersionResponse])
async def list_versions(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_READ)),
) -> list[DevisVersionResponse]:
    """Liste toutes les versions (snapshots) du devis."""
    svc = DevisService(db)
    return await svc.list_versions(devis_id, current_user.tenant_id)


# ── Négociations ──────────────────────────────────────────────────────────────


@router.post("/{devis_id}/negotiation", response_model=DevisNegotiationResponse, status_code=status.HTTP_201_CREATED)
async def add_negotiation(
    devis_id: int,
    payload: DevisNegotiationCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisNegotiationResponse:
    """Ajoute un message de négociation."""
    svc = DevisService(db)
    n = await svc.add_negotiation(devis_id, current_user.tenant_id, current_user.id, payload)
    return DevisNegotiationResponse(
        id=n.id, devis_id=n.devis_id, author_id=n.author_id,
        message=n.message, proposed_amount_cents=n.proposed_amount_cents,
        created_at=n.created_at,
    )


@router.post("/{devis_id}/negotiation/conclude", response_model=DevisResponse)
async def conclude_negotiation(
    devis_id: int,
    payload: DevisNegotiationConcludeRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisResponse:
    """Conclut formellement une négociation : accepte ou refuse le devis."""
    svc = DevisService(db)
    if payload.outcome == "accepted":
        d = await svc.accept(devis_id, current_user.tenant_id, current_user.id)
    else:
        d = await svc.refuse(devis_id, current_user.tenant_id, payload.reason)
    return _build_devis_response(d)


# ── Change requests ───────────────────────────────────────────────────────────


@router.get("/{devis_id}/change-requests", response_model=list[DevisChangeRequestResponse])
async def list_change_requests(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_READ)),
) -> list[DevisChangeRequestResponse]:
    """Liste toutes les demandes de modification du devis."""
    svc = DevisService(db)
    items = await svc.list_change_requests(devis_id, current_user.tenant_id)
    return [
        DevisChangeRequestResponse(
            id=cr.id, devis_id=cr.devis_id, author_id=cr.author_id,
            description=cr.description, status=cr.status,
            created_at=cr.created_at, updated_at=cr.updated_at,
        )
        for cr in items
    ]


@router.post("/{devis_id}/change-request", response_model=DevisChangeRequestResponse, status_code=status.HTTP_201_CREATED)
async def add_change_request(
    devis_id: int,
    payload: DevisChangeRequestCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisChangeRequestResponse:
    """Crée une demande de modification."""
    svc = DevisService(db)
    cr = await svc.add_change_request(devis_id, current_user.tenant_id, current_user.id, payload)
    return DevisChangeRequestResponse(
        id=cr.id, devis_id=cr.devis_id, author_id=cr.author_id,
        description=cr.description, status=cr.status,
        created_at=cr.created_at, updated_at=cr.updated_at,
    )


@router.patch("/{devis_id}/change-request/{cr_id}", response_model=DevisChangeRequestResponse)
async def update_change_request(
    devis_id: int,
    cr_id: int,
    payload: DevisChangeRequestUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisChangeRequestResponse:
    """Met à jour le statut d'une demande de modification."""
    svc = DevisService(db)
    cr = await svc.update_change_request(devis_id, current_user.tenant_id, cr_id, payload)
    return DevisChangeRequestResponse(
        id=cr.id, devis_id=cr.devis_id, author_id=cr.author_id,
        description=cr.description, status=cr.status,
        created_at=cr.created_at, updated_at=cr.updated_at,
    )


# ── Modules ───────────────────────────────────────────────────────────────────


@router.get("/{devis_id}/modules", response_model=list[DevisModuleResponse])
async def list_modules(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_READ)),
) -> list[DevisModuleResponse]:
    """Liste les modules du devis."""
    svc = DevisService(db)
    return [DevisModuleResponse.model_validate(m) for m in await svc.list_modules(devis_id, current_user.tenant_id)]


@router.post("/{devis_id}/modules", response_model=DevisModuleResponse, status_code=status.HTTP_201_CREATED)
async def add_module(
    devis_id: int,
    payload: DevisModuleCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisModuleResponse:
    """Ajoute un module au devis."""
    svc = DevisService(db)
    m = await svc.add_module(devis_id, current_user.tenant_id, payload)
    return DevisModuleResponse(
        id=m.id, devis_id=m.devis_id, module_type=m.module_type,
        label=m.label, content_json=m.content_json,
        delivery_status=getattr(m, "delivery_status", "a_cadrer"),
        is_active=m.is_active,
        created_at=m.created_at, updated_at=m.updated_at,
    )


@router.patch("/{devis_id}/modules/{module_id}", response_model=DevisModuleResponse)
async def update_module(
    devis_id: int,
    module_id: int,
    payload: DevisModuleUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisModuleResponse:
    """Met à jour un module du devis."""
    svc = DevisService(db)
    m = await svc.update_module(devis_id, module_id, current_user.tenant_id, payload)
    return DevisModuleResponse(
        id=m.id, devis_id=m.devis_id, module_type=m.module_type,
        label=m.label, content_json=m.content_json,
        delivery_status=getattr(m, "delivery_status", "a_cadrer"),
        is_active=m.is_active,
        created_at=m.created_at, updated_at=m.updated_at,
    )


@router.delete("/{devis_id}/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_module(
    devis_id: int,
    module_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> None:
    """Supprime un module du devis."""
    svc = DevisService(db)
    await svc.delete_module(devis_id, module_id, current_user.tenant_id)


# ── Phases ────────────────────────────────────────────────────────────────────


@router.get("/{devis_id}/phases", response_model=list[DevisPhaseResponse])
async def list_phases(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_READ)),
) -> list[DevisPhaseResponse]:
    """Liste les phases du devis triées par sort_order."""
    svc = DevisService(db)
    return [DevisPhaseResponse.model_validate(p) for p in await svc.list_phases(devis_id, current_user.tenant_id)]


@router.post("/{devis_id}/phases", response_model=DevisPhaseResponse, status_code=status.HTTP_201_CREATED)
async def add_phase(
    devis_id: int,
    payload: DevisPhaseCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisPhaseResponse:
    """Ajoute une phase au devis."""
    svc = DevisService(db)
    p = await svc.add_phase(devis_id, current_user.tenant_id, payload)
    return DevisPhaseResponse(
        id=p.id, devis_id=p.devis_id, label=p.label,
        date_start=p.date_start, date_end=p.date_end,
        sort_order=p.sort_order, is_active=p.is_active,
        created_at=p.created_at, updated_at=p.updated_at,
    )


@router.patch("/{devis_id}/phases/{phase_id}", response_model=DevisPhaseResponse)
async def update_phase(
    devis_id: int,
    phase_id: int,
    payload: DevisPhaseUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisPhaseResponse:
    """Met à jour une phase du devis."""
    svc = DevisService(db)
    p = await svc.update_phase(devis_id, current_user.tenant_id, phase_id, payload)
    return DevisPhaseResponse(
        id=p.id, devis_id=p.devis_id, label=p.label,
        date_start=p.date_start, date_end=p.date_end,
        sort_order=p.sort_order, is_active=p.is_active,
        created_at=p.created_at, updated_at=p.updated_at,
    )


@router.delete("/{devis_id}/phases/{phase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phase(
    devis_id: int,
    phase_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> None:
    """Supprime une phase du devis."""
    svc = DevisService(db)
    await svc.delete_phase(devis_id, phase_id, current_user.tenant_id)


# ── Coverage ──────────────────────────────────────────────────────────────────


@router.get("/{devis_id}/coverage", response_model=DevisCoverageResponse)
async def get_devis_coverage(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_READ)),
) -> DevisCoverageResponse:
    """Retourne la couverture d'un devis : % modules livrés, progression phases."""
    from datetime import date as date_type

    svc = DevisService(db)
    d = await svc.get(devis_id, current_user.tenant_id)

    today = date_type.today()
    phases_past = sum(1 for p in d.phases if p.date_end < today)
    phases_current = sum(1 for p in d.phases if p.date_start <= today <= p.date_end)
    phases_future = sum(1 for p in d.phases if p.date_start > today)
    total_phases = len(d.phases)
    phase_completion_pct = round(phases_past * 100 / total_phases) if total_phases else 0

    active_modules = [m for m in d.modules if m.is_active]
    module_types = list({m.module_type for m in active_modules})

    return DevisCoverageResponse(
        devis_id=d.id,
        reference=d.reference,
        status=d.status,
        total_modules=len(d.modules),
        active_modules=len(active_modules),
        module_types=sorted(module_types),
        total_phases=total_phases,
        phases_past=phases_past,
        phases_current=phases_current,
        phases_future=phases_future,
        phase_completion_pct=phase_completion_pct,
        total_lines=len(d.lines),
        subtotal_cents=d.subtotal_cents,
    )


# ── Coverage items (matrice fonctionnelle) ────────────────────────────────────


@router.get("/{devis_id}/coverage-items", response_model=list[DevisCoverageItemResponse])
async def list_coverage_items(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_READ)),
) -> list[DevisCoverageItemResponse]:
    """Liste les items de couverture fonctionnelle du devis."""
    svc = DevisService(db)
    return await svc.list_coverage_items(devis_id, current_user.tenant_id)


@router.post("/{devis_id}/coverage-items", response_model=DevisCoverageItemResponse, status_code=status.HTTP_201_CREATED)
async def add_coverage_item(
    devis_id: int,
    payload: DevisCoverageItemCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisCoverageItemResponse:
    """Ajoute un item de couverture fonctionnelle."""
    svc = DevisService(db)
    return await svc.add_coverage_item(devis_id, current_user.tenant_id, payload)


@router.patch("/{devis_id}/coverage-items/{item_id}", response_model=DevisCoverageItemResponse)
async def update_coverage_item(
    devis_id: int,
    item_id: int,
    payload: DevisCoverageItemUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisCoverageItemResponse:
    """Met à jour un item de couverture fonctionnelle (titre, statut, ordre)."""
    svc = DevisService(db)
    return await svc.update_coverage_item(devis_id, item_id, current_user.tenant_id, payload)


@router.delete("/{devis_id}/coverage-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coverage_item(
    devis_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> None:
    """Supprime un item de couverture fonctionnelle."""
    svc = DevisService(db)
    await svc.delete_coverage_item(devis_id, item_id, current_user.tenant_id)


# ── PDF & Duplication ──────────────────────────────────────────────────────────


@router.get("/{devis_id}/lines/history")
async def list_line_history(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.DEVIS_READ)),
):
    """Historique des modifications de toutes les lignes d'un devis (G28)."""
    from app.schemas.devis import DevisLineHistoryResponse
    from app.models.devis import DevisLineHistory

    service = DevisService(db)
    devis = await service._get_or_404(devis_id, current_user.tenant_id)

    stmt = (
        select(DevisLineHistory)
        .where(DevisLineHistory.devis_id == devis.id)
        .order_by(DevisLineHistory.created_at.desc())
        .limit(200)
    )
    result = await db.execute(stmt)
    entries = result.scalars().all()
    return [DevisLineHistoryResponse.model_validate(e) for e in entries]


@router.get("/bundles/{bundle_id}/items-preview")
async def preview_bundle_items(
    bundle_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.DEVIS_READ)),
):
    """Apercu des items d'un bundle avant ajout au devis."""
    from app.schemas.devis import BundlePreviewResponse, BundleItemPreview
    from app.models.bundle import ProductBundle
    from sqlalchemy.orm import selectinload

    from app.models.bundle import BundleItem

    stmt = (
        select(ProductBundle)
        .options(
            selectinload(ProductBundle.items).selectinload(BundleItem.product),
            selectinload(ProductBundle.items).selectinload(BundleItem.variant),
        )
        .where(
            ProductBundle.id == bundle_id,
            ProductBundle.tenant_id == current_user.tenant_id,
            ProductBundle.is_active.is_(True),
        )
    )
    result = await db.execute(stmt)
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    items = []
    for bi in bundle.items:
        product_name = bi.product.name if bi.product else ""
        product_image_url = bi.product.image_url if bi.product else None
        variant_label = bi.variant.label if bi.variant else None
        items.append(BundleItemPreview(
            product_id=bi.product_id,
            product_name=product_name,
            product_image_url=product_image_url,
            variant_id=getattr(bi, "variant_id", None),
            variant_label=variant_label,
            quantity=bi.quantity,
            display_order=bi.display_order,
        ))

    return BundlePreviewResponse(
        bundle_id=bundle.id,
        bundle_name=bundle.name,
        bundle_image_url=bundle.image_url,
        bundle_price_cents=bundle.bundle_price_cents,
        items=items,
    )


@router.get("/{devis_id}/pdf")
async def get_devis_pdf(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_READ)),
):
    """Génère et retourne le PDF du devis."""
    from app.services.devis_pdf import generate_devis_pdf

    svc = DevisService(db)
    d = await svc.get(devis_id, current_user.tenant_id)
    pdf_bytes = generate_devis_pdf(d)
    filename = f"devis-{d.reference}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/{devis_id}/signature", response_model=DevisSignatureResponse, status_code=status.HTTP_200_OK)
async def add_signature(
    devis_id: int,
    payload: DevisSignatureRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisSignatureResponse:
    """Enregistre la signature électronique d'un devis (statut 'sent' requis)."""
    svc = DevisService(db)
    devis = await svc.add_signature(devis_id, current_user.tenant_id, payload.signature_data)
    return DevisSignatureResponse(
        id=devis.id,
        signature_url=devis.signature_url,
        signed_at=devis.signed_at,
    )


@router.post("/{devis_id}/duplicate", response_model=DevisResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_devis(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.DEVIS_WRITE)),
) -> DevisResponse:
    """Duplique un devis existant en brouillon avec une nouvelle référence."""
    svc = DevisService(db)
    d = await svc.duplicate(devis_id, current_user.tenant_id)
    return _build_devis_response(d)


# ── Pieces jointes (G7) ──────────────────────────────────────────────────────

ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_ATTACHMENTS_PER_DEVIS = 10


@router.post("/{devis_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    devis_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.DEVIS_WRITE)),
):
    """Upload une piece jointe sur un devis."""
    from app.schemas.devis import DevisAttachmentResponse
    from app.models.devis import DevisAttachment
    import os
    import uuid as _uuid

    svc = DevisService(db)
    devis = await svc._get_or_404(devis_id, current_user.tenant_id)

    # Verifier le nombre d'attachments existants
    from sqlalchemy import func as sa_func
    count_stmt = select(sa_func.count(DevisAttachment.id)).where(
        DevisAttachment.devis_id == devis.id
    )
    count = (await db.execute(count_stmt)).scalar_one()
    if count >= MAX_ATTACHMENTS_PER_DEVIS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_ATTACHMENTS_PER_DEVIS} attachments per devis")

    # Valider MIME
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Accepted: {', '.join(ALLOWED_MIME_TYPES)}")

    # Lire le contenu et verifier la taille
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_FILE_SIZE // (1024*1024)} MB")

    # Stocker le fichier
    upload_dir = os.path.join("uploads", "devis", str(devis.id))
    os.makedirs(upload_dir, exist_ok=True)
    safe_filename = f"{_uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    attachment = DevisAttachment(
        tenant_id=current_user.tenant_id,
        devis_id=devis.id,
        filename=file.filename,
        mime_type=file.content_type,
        file_path=file_path,
        file_size=len(content),
        uploaded_by=current_user.id,
        sort_order=count,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return DevisAttachmentResponse.model_validate(attachment)


@router.get("/{devis_id}/attachments")
async def list_attachments(
    devis_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.DEVIS_READ)),
):
    """Liste les pieces jointes d'un devis."""
    from app.schemas.devis import DevisAttachmentResponse
    from app.models.devis import DevisAttachment

    svc = DevisService(db)
    await svc._get_or_404(devis_id, current_user.tenant_id)

    stmt = (
        select(DevisAttachment)
        .where(DevisAttachment.devis_id == devis_id)
        .order_by(DevisAttachment.sort_order)
    )
    result = await db.execute(stmt)
    attachments = result.scalars().all()
    return [DevisAttachmentResponse.model_validate(a) for a in attachments]


@router.get("/{devis_id}/attachments/{attachment_id}/download")
async def download_attachment(
    devis_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.DEVIS_READ)),
):
    """Telecharge une piece jointe."""
    from app.models.devis import DevisAttachment
    import os

    svc = DevisService(db)
    await svc._get_or_404(devis_id, current_user.tenant_id)

    stmt = select(DevisAttachment).where(
        DevisAttachment.id == attachment_id,
        DevisAttachment.devis_id == devis_id,
    )
    result = await db.execute(stmt)
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    if not os.path.exists(attachment.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=attachment.file_path,
        filename=attachment.filename,
        media_type=attachment.mime_type,
    )


@router.delete("/{devis_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    devis_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.DEVIS_WRITE)),
):
    """Supprime une piece jointe."""
    from app.models.devis import DevisAttachment
    import os

    svc = DevisService(db)
    await svc._get_or_404(devis_id, current_user.tenant_id)

    stmt = select(DevisAttachment).where(
        DevisAttachment.id == attachment_id,
        DevisAttachment.devis_id == devis_id,
    )
    result = await db.execute(stmt)
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    file_path = attachment.file_path
    await db.delete(attachment)
    await db.commit()

    # Supprimer le fichier physique apres commit DB
    if os.path.exists(file_path):
        os.remove(file_path)
