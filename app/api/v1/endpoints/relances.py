"""Endpoints relances — gestion des relances planifiées sur factures."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.errors import ErrorMessages
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.models.invoice import Invoice
from app.models.relance import Relance
from app.models.reservation import Reservation
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.relance import RelanceResponse, RelanceSchedule
from app.constants import RelanceStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/relances", tags=["Relances"])


async def _get_invoice_or_404(db: AsyncSession, invoice_id: int, tenant_id: int) -> Invoice:
    """Charge une facture en vérifiant l'isolation tenant."""
    invoice = (await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facture {invoice_id} introuvable"
        )
    return invoice


async def _get_relance_or_404(db: AsyncSession, relance_id: int, tenant_id: int) -> Relance:
    """Charge une relance en vérifiant l'isolation tenant."""
    relance = (await db.execute(
        select(Relance).where(Relance.id == relance_id, Relance.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not relance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Relance {relance_id} introuvable"
        )
    return relance


@router.get("", response_model=PaginatedResponse[RelanceResponse])
async def list_relances(
    invoice_id: int | None = None,
    customer_id: int | None = None,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RELANCES_READ)),
) -> PaginatedResponse[RelanceResponse]:
    """Liste les relances du tenant, avec filtres optionnels par facture ou client."""
    q = select(Relance).where(Relance.tenant_id == current_user.tenant_id)
    if invoice_id is not None:
        q = q.where(Relance.invoice_id == invoice_id)
    if customer_id is not None:
        q = (
            q.join(Invoice, Relance.invoice_id == Invoice.id)
            .join(Reservation, Invoice.reservation_id == Reservation.id)
            .where(Reservation.customer_id == customer_id)
        )
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.scalar(count_q)) or 0
    relances = (await db.execute(
        q.order_by(Relance.scheduled_at.desc())
        .offset(pagination.skip)
        .limit(pagination.limit)
    )).scalars().all()
    return PaginatedResponse[RelanceResponse](
        items=[RelanceResponse.model_validate(r) for r in relances],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.post("/schedule", response_model=RelanceResponse, status_code=status.HTTP_201_CREATED)
async def schedule_relance(
    data: RelanceSchedule,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RELANCES_WRITE)),
) -> RelanceResponse:
    """Planifie une relance sur une facture.

    La facture doit appartenir au même tenant.
    Une relance ne peut être planifiée que dans le futur.
    """
    await _get_invoice_or_404(db, data.invoice_id, current_user.tenant_id)

    # Normaliser en naive UTC (colonne TIMESTAMP WITHOUT TIME ZONE)
    scheduled_naive = (
        data.scheduled_at.astimezone(timezone.utc).replace(tzinfo=None)
        if data.scheduled_at.tzinfo
        else data.scheduled_at
    )

    if scheduled_naive <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.INVALID_DATE_RANGE
        )

    relance = Relance(
        tenant_id=current_user.tenant_id,
        invoice_id=data.invoice_id,
        scheduled_at=scheduled_naive,
        status=RelanceStatus.SCHEDULED,
        channel=data.channel,
        message=data.message,
        created_at=datetime.utcnow(),
    )
    db.add(relance)
    await db.commit()
    await db.refresh(relance)
    logger.info(
        "Relance %d planifiée pour facture %d (tenant %d) le %s",
        relance.id, data.invoice_id, current_user.tenant_id, data.scheduled_at
    )
    return RelanceResponse.model_validate(relance)


@router.post("/cancel/{relance_id}", response_model=RelanceResponse)
async def cancel_relance(
    relance_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RELANCES_WRITE)),
) -> RelanceResponse:
    """Annule une relance planifiée.

    Seules les relances au statut 'scheduled' peuvent être annulées.
    """
    relance = await _get_relance_or_404(db, relance_id, current_user.tenant_id)

    if relance.status != RelanceStatus.SCHEDULED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible d'annuler une relance au statut '{relance.status}'"
        )

    relance.status = RelanceStatus.CANCELLED
    relance.cancelled_at = datetime.utcnow()
    await db.commit()
    await db.refresh(relance)
    return RelanceResponse.model_validate(relance)


@router.post("/mark-sent/{relance_id}", response_model=RelanceResponse)
async def mark_relance_sent(
    relance_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RELANCES_WRITE)),
) -> RelanceResponse:
    """Marque une relance comme envoyée.

    Utilisé par le worker Celery ou manuellement.
    Seules les relances au statut 'scheduled' peuvent être marquées envoyées.
    """
    relance = await _get_relance_or_404(db, relance_id, current_user.tenant_id)

    if relance.status != RelanceStatus.SCHEDULED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.RELANCE_ALREADY_SENT
        )

    relance.status = RelanceStatus.SENT
    relance.sent_at = datetime.utcnow()
    await db.commit()
    await db.refresh(relance)
    return RelanceResponse.model_validate(relance)
