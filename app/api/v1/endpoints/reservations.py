"""Endpoints CRUD pour les réservations avec workflows métier."""
import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.models.tenant_membership import TenantMembership
from app.models.reservation import (
    Reservation,
    ReservationExtension,
    ReservationLine,
    ReservationPreCheckItem,
    ReservationRisk,
    ReservationReturnInspectionItem,
    ReservationDisputeLog,
)
from app.models.bundle import ProductBundle, BundleItem
from app.schemas.common import PaginationParams, PaginatedResponse
from app.schemas.deposit import DepositCreate, DepositUpdate, DepositRead
from app.schemas.reservation import (
    ReservationCreate,
    ReservationUpdate,
    ReservationResponse,
    ReservationList,
    ReservationLineCreate,
    ReservationLineResponse,
    ReservationRiskCreate,
    ReservationRiskUpdate,
    ReservationRiskResponse,
    PreCheckItemCreate,
    PreCheckItemResponse,
    PreCheckItemUpdate,
    ReservationExtensionCreate,
    ReservationExtensionResponse,
    ReservationSignatureCreate,
    ReservationAssignUser,
    ReservationFull,
    CloseDisputeRequest,
    ReservationAmendRequest,
    ReturnInspectionItemCreate,
    ReturnInspectionBulkCreate,
    ReturnInspectionItemResponse,
    DisputeLogCreate,
    DisputeLogResponse,
)
from app.services.deposit import DepositService
from app.services.reservation import ReservationService
from app.constants import ErrorMessages, ReservationStatus
from app.core.exceptions import NotFound

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reservations", tags=["Reservations"])


# ── Helper ────────────────────────────────────────────────────────────────────


async def _get_reservation_or_404(
    reservation_id: int, tenant_id: int, db: AsyncSession
) -> Reservation:
    """Retourne la réservation ou lève 404 si non trouvée ou cross-tenant."""
    res = await db.get(Reservation, reservation_id)
    if not res or res.tenant_id != tenant_id:
        raise NotFound(ErrorMessages.RESERVATION_NOT_FOUND)
    return res


# ── Stats (KPI) ───────────────────────────────────────────────────────────────


@router.get("/stats")
async def reservation_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> dict[str, int]:
    """Compteurs agrégés par statut — 1 requête SQL au lieu de N appels list."""
    result = await db.execute(
        select(Reservation.status, func.count())
        .where(Reservation.tenant_id == current_user.tenant_id)
        .group_by(Reservation.status)
    )
    counts = {row[0]: row[1] for row in result.all()}
    return counts


# ── CRUD principal ─────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[ReservationList])
async def list_reservations(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    customer_id: Optional[int] = Query(None),
    assigned_to_me: bool = Query(False, description="Filtrer mes reservations"),
    assigned_user_id: Optional[int] = Query(None, description="Filtrer par utilisateur affecte"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> PaginatedResponse[ReservationList]:
    """Liste toutes les reservations avec pagination et filtres."""
    effective_assigned = assigned_user_id
    if assigned_to_me:
        effective_assigned = current_user.id
    service = ReservationService(db)
    reservations, total = await service.list_reservations(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        status_filter=status_filter,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        assigned_user_id=effective_assigned,
    )
    return PaginatedResponse(
        items=[ReservationList.model_validate(r) for r in reservations],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{reservation_id}", response_model=ReservationResponse)
async def get_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> ReservationResponse:
    """Récupère les détails d'une réservation avec relations."""
    service = ReservationService(db)
    reservation = await service.get_reservation(reservation_id, current_user.tenant_id)
    return ReservationResponse.model_validate(reservation)


@router.post("", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    reservation_data: ReservationCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationResponse:
    """Crée une nouvelle réservation avec ses lignes."""
    service = ReservationService(db)
    try:
        reservation = await service.create_reservation(reservation_data, current_user.tenant_id)
        await db.commit()
        reservation = await service.get_reservation(reservation.id, current_user.tenant_id)
        return ReservationResponse.model_validate(reservation)
    except HTTPException:
        raise


@router.patch("/{reservation_id}", response_model=ReservationResponse)
async def update_reservation(
    reservation_id: int,
    reservation_data: ReservationUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationResponse:
    """Met à jour une réservation (status=draft uniquement, PATCH partiel).

    Si la résa est issue d'un devis, seuls les champs opérationnels (notes,
    livraison, contacts) sont modifiables. Pour modifier le périmètre
    (lines, dates, pricing) → utiliser POST /reservations/{id}/amend.
    """
    service = ReservationService(db)
    try:
        reservation = await service.update_reservation(
            reservation_id, reservation_data, current_user.tenant_id
        )
        await db.commit()
        reservation = await service.get_reservation(reservation.id, current_user.tenant_id)
        return ReservationResponse.model_validate(reservation)
    except HTTPException:
        raise


@router.post("/{reservation_id}/amend", response_model=ReservationResponse)
async def amend_reservation(
    reservation_id: int,
    payload: ReservationAmendRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationResponse:
    """Avenant à une réservation issue d'un devis.

    Crée une nouvelle DevisVersion (snapshot pre-amend) puis applique les
    modifications périmétriques (dates, lignes) en bypass du verrou
    ``RESERVATION_LOCKED_BY_DEVIS``. Le motif de l'avenant est obligatoire
    et tracé dans les notes de la résa.

    Raises:
        400 si la résa n'est pas issue d'un devis ou est en statut terminal.
        404 si la résa ou son devis source n'existent pas.
    """
    service = ReservationService(db)
    reservation = await service.amend_reservation(
        reservation_id, payload, current_user.tenant_id, current_user.id,
    )
    await db.commit()
    reservation = await service.get_reservation(reservation.id, current_user.tenant_id)
    return ReservationResponse.model_validate(reservation)


@router.get(
    "/{reservation_id}/lines",
    response_model=list[ReservationLineResponse],
)
async def list_reservation_lines(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> list[ReservationLineResponse]:
    """Liste les lignes d'une réservation."""
    service = ReservationService(db)
    reservation = await service.get_reservation(reservation_id, current_user.tenant_id)
    return [ReservationLineResponse.model_validate(line) for line in reservation.lines]


@router.post(
    "/{reservation_id}/lines",
    response_model=ReservationLineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_reservation_line(
    reservation_id: int,
    line_data: ReservationLineCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationLineResponse:
    """Ajoute une ligne à une réservation (status=draft uniquement)."""
    service = ReservationService(db)
    try:
        line = await service.add_line(reservation_id, line_data, current_user.tenant_id)
        await db.commit()
        return ReservationLineResponse.model_validate(line)
    except HTTPException:
        raise


@router.delete(
    "/{reservation_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_reservation_line(
    reservation_id: int,
    line_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> None:
    """Supprime une ligne d'une réservation (status=draft uniquement)."""
    service = ReservationService(db)
    try:
        await service.remove_line(reservation_id, line_id, current_user.tenant_id)
        await db.commit()
    except HTTPException:
        raise


# ── Transitions ───────────────────────────────────────────────────────────────


@router.post("/{reservation_id}/confirm", response_model=ReservationResponse)
async def confirm_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationResponse:
    """Confirme une réservation et réserve le stock."""
    service = ReservationService(db)
    try:
        reservation = await service.confirm_reservation(reservation_id, current_user.tenant_id)
        await db.commit()
        reservation = await service.get_reservation(reservation.id, current_user.tenant_id)
        return ReservationResponse.model_validate(reservation)
    except HTTPException:
        raise


@router.delete("/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> None:
    """Supprime définitivement une réservation en statut 'draft'."""
    service = ReservationService(db)
    try:
        await service.delete_reservation(reservation_id, current_user.tenant_id)
        await db.commit()
    except HTTPException:
        raise


@router.post("/{reservation_id}/cancel", response_model=ReservationResponse)
async def cancel_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationResponse:
    """Annule une réservation et libère le stock."""
    service = ReservationService(db)
    try:
        reservation = await service.cancel_reservation(reservation_id, current_user.tenant_id)
        await db.commit()
        reservation = await service.get_reservation(reservation.id, current_user.tenant_id)
        return ReservationResponse.model_validate(reservation)
    except HTTPException:
        raise


@router.post("/{reservation_id}/deliver", response_model=ReservationResponse)
async def deliver_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationResponse:
    """Marque une réservation comme livrée (confirmed → delivered)."""
    service = ReservationService(db)
    try:
        reservation = await service.deliver_reservation(reservation_id, current_user.tenant_id)
        await db.commit()
        reservation = await service.get_reservation(reservation.id, current_user.tenant_id)
        return ReservationResponse.model_validate(reservation)
    except HTTPException:
        raise


# ── Cautions (dépôts) ─────────────────────────────────────────────────────────


@router.get("/{reservation_id}/deposits", response_model=list[DepositRead])
async def list_deposits(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> list[DepositRead]:
    """Liste les cautions d'une réservation."""
    service = DepositService(db)
    deposits = await service.list_deposits(reservation_id, current_user.tenant_id)
    return [DepositRead.model_validate(d) for d in deposits]


@router.post(
    "/{reservation_id}/deposits",
    response_model=DepositRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_deposit(
    reservation_id: int,
    deposit_data: DepositCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> DepositRead:
    """Crée une caution pour une réservation (statut initial : held)."""
    service = DepositService(db)
    deposit = await service.create_deposit(reservation_id, deposit_data, current_user.tenant_id)
    await db.commit()
    return DepositRead.model_validate(deposit)


@router.get(
    "/{reservation_id}/deposits/{deposit_id}",
    response_model=DepositRead,
)
async def get_deposit(
    reservation_id: int,
    deposit_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> DepositRead:
    """Récupère une caution individuelle d'une réservation."""
    service = DepositService(db)
    deposit = await service.get_deposit(
        reservation_id=reservation_id,
        deposit_id=deposit_id,
        tenant_id=current_user.tenant_id,
    )
    return DepositRead.model_validate(deposit)


@router.patch(
    "/{reservation_id}/deposits/{deposit_id}",
    response_model=DepositRead,
)
async def update_deposit(
    reservation_id: int,
    deposit_id: int,
    deposit_data: DepositUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> DepositRead:
    """Met à jour le statut d'une caution (released/retained)."""
    service = DepositService(db)
    deposit = await service.update_deposit(
        reservation_id, deposit_id, deposit_data, current_user.tenant_id
    )
    await db.commit()
    await db.refresh(deposit)
    return DepositRead.model_validate(deposit)


# ── Pre-check ─────────────────────────────────────────────────────────────────


@router.post(
    "/{reservation_id}/pre-check",
    response_model=PreCheckItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pre_check_item(
    reservation_id: int,
    data: PreCheckItemCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> PreCheckItemResponse:
    """Ajoute un item de pre-check à une réservation."""
    await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    item = ReservationPreCheckItem(
        tenant_id=current_user.tenant_id,
        reservation_id=reservation_id,
        label=data.label,
        type=data.type,
        sort_order=data.sort_order,
        checked=False,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return PreCheckItemResponse.model_validate(item)


@router.get("/{reservation_id}/pre-check", response_model=list[PreCheckItemResponse])
async def list_pre_check(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> list[PreCheckItemResponse]:
    """Liste les items de pre-check d'une réservation."""
    await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    result = await db.execute(
        select(ReservationPreCheckItem)
        .where(
            ReservationPreCheckItem.reservation_id == reservation_id,
            ReservationPreCheckItem.tenant_id == current_user.tenant_id,
        )
        .order_by(ReservationPreCheckItem.sort_order)
    )
    items = result.scalars().all()
    return [PreCheckItemResponse.model_validate(i) for i in items]


@router.patch(
    "/{reservation_id}/pre-check/{item_id}",
    response_model=PreCheckItemResponse,
)
async def update_pre_check_item(
    reservation_id: int,
    item_id: int,
    data: PreCheckItemUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> PreCheckItemResponse:
    """Coche ou décoche un item de pre-check."""
    await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    item = await db.get(ReservationPreCheckItem, item_id)
    if not item or item.reservation_id != reservation_id or item.tenant_id != current_user.tenant_id:
        raise NotFound(ErrorMessages.RESERVATION_LINE_NOT_FOUND)
    item.checked = data.checked
    item.checked_at = datetime.now(timezone.utc) if data.checked else None
    item.checked_by = current_user.id if data.checked else None
    await db.commit()
    await db.refresh(item)
    return PreCheckItemResponse.model_validate(item)


@router.post("/{reservation_id}/pre-check/complete", response_model=ReservationResponse)
async def complete_pre_check(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationResponse:
    """Valide le pre-check et passe confirmed → pre_check."""
    service = ReservationService(db)
    reservation = await service.start_precheck(reservation_id, current_user.tenant_id)
    await db.commit()
    reservation = await service.get_reservation(reservation_id, current_user.tenant_id)
    return ReservationResponse.model_validate(reservation)


# ── Extensions ────────────────────────────────────────────────────────────────


@router.post(
    "/{reservation_id}/extend",
    response_model=ReservationExtensionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def extend_reservation(
    reservation_id: int,
    data: ReservationExtensionCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationExtensionResponse:
    """Prolonge une réservation (nouveau return_date)."""
    res = await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    if res.status not in (ReservationStatus.DELIVERED, ReservationStatus.EXTENDED):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Extension impossible depuis le statut '{res.status}'. "
                "Statuts autorisés : delivered, extended."
            ),
        )
    if res.return_date and data.new_return_date <= res.return_date:
        raise HTTPException(
            status_code=400,
            detail=ErrorMessages.RESERVATION_DATES_INVALID,
        )
    ext = ReservationExtension(
        tenant_id=current_user.tenant_id,
        reservation_id=reservation_id,
        original_return_date=res.return_date,
        new_return_date=data.new_return_date,
        reason=data.reason,
        extra_charge_cents=data.extra_charge_cents,
        created_by=current_user.id,
    )
    db.add(ext)
    res.return_date = data.new_return_date
    res.status = ReservationStatus.EXTENDED

    # Mettre à jour le mouvement RETURN schedulé avec la nouvelle date
    from app.models.inventory_movement import InventoryMovement
    from app.constants import MovementType, MovementStatus

    result = await db.execute(
        select(InventoryMovement).where(
            InventoryMovement.reservation_id == reservation_id,
            InventoryMovement.tenant_id == current_user.tenant_id,
            InventoryMovement.movement_type == MovementType.RETURN.value,
            InventoryMovement.status.in_([
                MovementStatus.SCHEDULED.value,
                MovementStatus.IN_TRANSIT.value,
            ]),
            InventoryMovement.is_active.is_(True),
        )
    )
    return_movement = result.scalar_one_or_none()
    if return_movement:
        return_movement.scheduled_date = data.new_return_date

    await db.commit()
    await db.refresh(ext)
    return ReservationExtensionResponse.model_validate(ext)


# ── Risques ───────────────────────────────────────────────────────────────────


@router.get("/{reservation_id}/risks", response_model=list[ReservationRiskResponse])
async def list_risks(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> list[ReservationRiskResponse]:
    """Liste les risques d'une réservation."""
    await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    result = await db.execute(
        select(ReservationRisk).where(
            ReservationRisk.reservation_id == reservation_id,
            ReservationRisk.tenant_id == current_user.tenant_id,
        )
    )
    risks = result.scalars().all()
    return [ReservationRiskResponse.model_validate(r) for r in risks]


@router.post(
    "/{reservation_id}/risks",
    response_model=ReservationRiskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_risk(
    reservation_id: int,
    data: ReservationRiskCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationRiskResponse:
    """Ajoute un risque à une réservation."""
    res = await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    risk = ReservationRisk(
        tenant_id=current_user.tenant_id,
        reservation_id=reservation_id,
        type=data.type,
        severity=data.severity,
        description=data.description,
        blocking=data.blocking,
    )
    db.add(risk)
    if data.blocking and res.status == ReservationStatus.CONFIRMED:
        res.status = ReservationStatus.CONFIRMED_RISK
    await db.commit()
    await db.refresh(risk)
    return ReservationRiskResponse.model_validate(risk)


@router.patch(
    "/{reservation_id}/risks/{risk_id}",
    response_model=ReservationRiskResponse,
)
async def update_risk(
    reservation_id: int,
    risk_id: int,
    data: ReservationRiskUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationRiskResponse:
    """Met à jour un risque (résolution possible via resolved_at)."""
    await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    risk = await db.get(ReservationRisk, risk_id)
    if not risk or risk.reservation_id != reservation_id or risk.tenant_id != current_user.tenant_id:
        raise NotFound(ErrorMessages.RESERVATION_NOT_FOUND)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(risk, field, value)
    await db.commit()
    await db.refresh(risk)
    return ReservationRiskResponse.model_validate(risk)


@router.delete(
    "/{reservation_id}/risks/{risk_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_risk(
    reservation_id: int,
    risk_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> None:
    """Supprime un risque d'une réservation."""
    await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    risk = await db.get(ReservationRisk, risk_id)
    if not risk or risk.reservation_id != reservation_id or risk.tenant_id != current_user.tenant_id:
        raise NotFound(ErrorMessages.RESERVATION_NOT_FOUND)
    await db.delete(risk)
    await db.commit()


# ── Affectation / Signature ───────────────────────────────────────────────────


@router.patch("/{reservation_id}/assign", response_model=ReservationResponse)
async def assign_user_to_reservation(
    reservation_id: int,
    data: ReservationAssignUser,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationResponse:
    """Affecte (ou désaffecte) un utilisateur du même tenant à une réservation."""
    res = await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    if data.user_id is not None:
        membership = (await db.execute(
            select(TenantMembership).where(
                TenantMembership.account_id == data.user_id,
                TenantMembership.tenant_id == current_user.tenant_id,
                TenantMembership.status == "active",
            )
        )).scalar_one_or_none()
        if not membership:
            raise NotFound(ErrorMessages.USER_NOT_FOUND)
    res.assigned_user_id = data.user_id
    await db.commit()

    # Notification in-app a l'utilisateur affecte
    if data.user_id and data.user_id != current_user.id:
        from app.models.notification import Notification
        try:
            db.add(Notification(
                tenant_id=current_user.tenant_id,
                user_id=data.user_id,
                type="assignment",
                title="Reservation affectee",
                message=f"La reservation {res.reference} vous a ete affectee.",
                link=f"/reservations/{reservation_id}",
            ))
            await db.commit()
        except Exception as e:
            logger.warning("Notification assignation echouee: %s", e)

    service = ReservationService(db)
    reservation = await service.get_reservation(res.id, current_user.tenant_id)
    return ReservationResponse.model_validate(reservation)


@router.post("/{reservation_id}/signature", response_model=ReservationResponse)
async def upload_signature(
    reservation_id: int,
    data: ReservationSignatureCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationResponse:
    """Enregistre la signature client (base64 ou URL)."""
    res = await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    if res.signature_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette reservation est deja signee.",
        )
    res.signature_url = data.signature_data
    res.signed_at = datetime.now(timezone.utc)
    await db.commit()
    service = ReservationService(db)
    reservation = await service.get_reservation(res.id, current_user.tenant_id)
    return ReservationResponse.model_validate(reservation)


# ── Vue complète ──────────────────────────────────────────────────────────────


# ── Workflow de clôture ───────────────────────────────────────────────────────


@router.post("/{reservation_id}/complete", response_model=ReservationResponse)
async def complete_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationResponse:
    """Clôture définitivement une réservation retournée (RETURNED → COMPLETED)."""
    service = ReservationService(db)
    try:
        reservation = await service.complete_reservation(reservation_id, current_user.tenant_id)
        await db.commit()
        reservation = await service.get_reservation(reservation.id, current_user.tenant_id)
        return ReservationResponse.model_validate(reservation)
    except HTTPException:
        raise


@router.post("/{reservation_id}/close-dispute", response_model=ReservationResponse)
async def close_dispute(
    reservation_id: int,
    data: CloseDisputeRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationResponse:
    """Résout un litige et repasse la réservation en RETURNED (RETURNED_DISPUTE → RETURNED).

    Écrit également une entrée `resolved` dans le journal de litige pour audit.
    """
    service = ReservationService(db)
    try:
        reservation = await service.close_dispute(
            reservation_id, current_user.tenant_id, data.resolution_notes
        )
        db.add(
            ReservationDisputeLog(
                tenant_id=current_user.tenant_id,
                reservation_id=reservation.id,
                action="resolved",
                description=data.resolution_notes,
                charge_cents=0,
                created_by=current_user.id,
            )
        )
        await db.commit()
        reservation = await service.get_reservation(reservation.id, current_user.tenant_id)
        return ReservationResponse.model_validate(reservation)
    except HTTPException:
        raise


# ── Return inspection ─────────────────────────────────────────────────────────


@router.post(
    "/{reservation_id}/inspection",
    response_model=list[ReturnInspectionItemResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_return_inspection(
    reservation_id: int,
    payload: ReturnInspectionBulkCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> list[ReturnInspectionItemResponse]:
    """Enregistre le constat de retour (bulk).

    Bascule automatiquement la résa en RETURNED_DISPUTE si au moins un item
    a `quantity_damaged > 0` ou `quantity_missing > 0`.
    """
    res = await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    if res.status not in (
        ReservationStatus.DELIVERED,
        ReservationStatus.EXTENDED,
        ReservationStatus.RETURNED,
        ReservationStatus.RETURNED_DISPUTE,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Inspection impossible sur réservation au statut '{res.status}'. "
                "Statuts autorisés : delivered, extended, returned, returned_dispute."
            ),
        )

    inspected_at = datetime.now(timezone.utc)
    items: list[ReservationReturnInspectionItem] = []
    has_issue = False

    for item_data in payload.items:
        if item_data.quantity_damaged > 0 or item_data.quantity_missing > 0:
            has_issue = True
        item = ReservationReturnInspectionItem(
            tenant_id=current_user.tenant_id,
            reservation_id=reservation_id,
            reservation_line_id=item_data.reservation_line_id,
            label=item_data.label,
            quantity_expected=item_data.quantity_expected,
            quantity_returned=item_data.quantity_returned,
            quantity_damaged=item_data.quantity_damaged,
            quantity_missing=item_data.quantity_missing,
            condition=item_data.condition,
            damage_description=item_data.damage_description,
            photo_url=item_data.photo_url,
            charge_cents=item_data.charge_cents,
            inspected_by=current_user.id,
            inspected_at=inspected_at,
        )
        db.add(item)
        items.append(item)

    if has_issue and res.status not in (
        ReservationStatus.RETURNED_DISPUTE,
        ReservationStatus.COMPLETED,
    ):
        res.status = ReservationStatus.RETURNED_DISPUTE
        total_charge = sum(it.charge_cents for it in items)
        db.add(
            ReservationDisputeLog(
                tenant_id=current_user.tenant_id,
                reservation_id=reservation_id,
                action="opened",
                description=(
                    f"Litige ouvert : {sum(1 for it in items if it.quantity_damaged > 0)} "
                    f"item(s) endommagé(s), "
                    f"{sum(1 for it in items if it.quantity_missing > 0)} item(s) manquant(s)"
                ),
                charge_cents=total_charge,
                created_by=current_user.id,
            )
        )

    await db.commit()
    for item in items:
        await db.refresh(item)
    return [ReturnInspectionItemResponse.model_validate(it) for it in items]


@router.get(
    "/{reservation_id}/inspection",
    response_model=list[ReturnInspectionItemResponse],
)
async def list_return_inspection(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> list[ReturnInspectionItemResponse]:
    """Liste les items du constat de retour d'une réservation."""
    await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    result = await db.execute(
        select(ReservationReturnInspectionItem)
        .where(
            ReservationReturnInspectionItem.reservation_id == reservation_id,
            ReservationReturnInspectionItem.tenant_id == current_user.tenant_id,
        )
        .order_by(ReservationReturnInspectionItem.id)
    )
    items = result.scalars().all()
    return [ReturnInspectionItemResponse.model_validate(it) for it in items]


# ── Dispute logs ──────────────────────────────────────────────────────────────


@router.post(
    "/{reservation_id}/dispute-logs",
    response_model=DisputeLogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_dispute_log(
    reservation_id: int,
    data: DisputeLogCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> DisputeLogResponse:
    """Ajoute une entrée d'audit dans le journal d'un litige (append-only)."""
    await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    log = ReservationDisputeLog(
        tenant_id=current_user.tenant_id,
        reservation_id=reservation_id,
        action=data.action,
        description=data.description,
        charge_cents=data.charge_cents,
        created_by=current_user.id,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return DisputeLogResponse.model_validate(log)


@router.get(
    "/{reservation_id}/dispute-logs",
    response_model=list[DisputeLogResponse],
)
async def list_dispute_logs(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> list[DisputeLogResponse]:
    """Retourne le journal chronologique d'un litige."""
    await _get_reservation_or_404(reservation_id, current_user.tenant_id, db)
    result = await db.execute(
        select(ReservationDisputeLog)
        .where(
            ReservationDisputeLog.reservation_id == reservation_id,
            ReservationDisputeLog.tenant_id == current_user.tenant_id,
        )
        .order_by(ReservationDisputeLog.created_at)
    )
    logs = result.scalars().all()
    return [DisputeLogResponse.model_validate(log) for log in logs]


@router.post(
    "/{reservation_id}/remind-deposit",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remind_deposit(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> None:
    """Envoie un rappel d'acompte au client pour une réservation confirmée."""
    service = ReservationService(db)
    try:
        await service.remind_deposit(reservation_id, current_user.tenant_id)
    except HTTPException:
        raise


# ── Vue complète ──────────────────────────────────────────────────────────────


@router.get("/{reservation_id}/full", response_model=ReservationFull)
async def get_reservation_full(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_READ)),
) -> ReservationFull:
    """Détail complet d'une réservation avec risks, pre-check, extensions."""
    result = await db.execute(
        select(Reservation)
        .options(
            selectinload(Reservation.customer),
            selectinload(Reservation.lines).selectinload(ReservationLine.product),
            selectinload(Reservation.lines).selectinload(ReservationLine.bundle).selectinload(ProductBundle.items).selectinload(BundleItem.product),
            selectinload(Reservation.lines).selectinload(ReservationLine.variant),
            selectinload(Reservation.risks),
            selectinload(Reservation.pre_check_items),
            selectinload(Reservation.extensions),
            selectinload(Reservation.invoices),
        )
        .where(
            Reservation.id == reservation_id,
            Reservation.tenant_id == current_user.tenant_id,
        )
    )
    res = result.scalar_one_or_none()
    if not res:
        raise NotFound(ErrorMessages.RESERVATION_NOT_FOUND)
    return ReservationFull.model_validate(res)


# ── Archivage ─────────────────────────────────────────────────────────────────


@router.post("/{reservation_id}/archive", response_model=ReservationResponse)
async def archive_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.RESERVATIONS_WRITE)),
) -> ReservationResponse:
    """Archive une réservation terminée ou annulée.

    Masque la réservation des listes courantes sans suppression physique.
    Statuts autorisés : completed, cancelled.
    """
    service = ReservationService(db)
    try:
        reservation = await service.archive_reservation(reservation_id, current_user.tenant_id)
        await db.commit()
        refreshed = await service.get_reservation(reservation_id, current_user.tenant_id)
        return ReservationResponse.model_validate(refreshed)
    except HTTPException:
        raise
