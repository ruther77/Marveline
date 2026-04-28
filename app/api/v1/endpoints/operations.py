"""Endpoints opérations terrain — départ, retour, QR, dommages."""
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.errors import ErrorMessages
from app.core.config import settings
from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.operations import (
    DamageReportResponse,
    DepartureBlockRequest,
    DepartureState,
    DepartureValidateRequest,
    PhotoUploadResponse,
    QrResult,
    ReturnDamageRequest,
    ReturnState,
    ReturnValidateRequest,
)
from app.services import operations as ops_svc

router = APIRouter(prefix="/operations", tags=["Operations"])
logger = logging.getLogger(__name__)

_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB


# ---------------------------------------------------------------------------
# Départ
# ---------------------------------------------------------------------------

@router.get("/departure/{reservation_id}", response_model=DepartureState)
async def get_departure_state(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
):
    """Retourne l'état de la checklist de départ."""
    return await ops_svc.get_departure_state(reservation_id, current_user.tenant_id, db)


@router.post("/departure/{reservation_id}", response_model=DepartureState)
async def validate_departure(
    reservation_id: int,
    data: DepartureValidateRequest = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_WRITE)),
):
    """Valide le départ : transition pre_check → delivered. Stocke la signature si fournie."""
    signature_url = data.signature_url if data else None
    items = data.items if data else []
    return await ops_svc.validate_departure(
        reservation_id, current_user.tenant_id, db, signature_url, items
    )


@router.post("/departure/{reservation_id}/block", response_model=DepartureState)
async def block_departure(
    reservation_id: int,
    data: DepartureBlockRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_WRITE)),
):
    """Bloque le départ en signalant un risque : → confirmed_risk."""
    return await ops_svc.block_departure(
        reservation_id, current_user.tenant_id, db, reason=data.reason,
    )


# ---------------------------------------------------------------------------
# Retour
# ---------------------------------------------------------------------------

@router.get("/return/{reservation_id}", response_model=ReturnState)
async def get_return_state(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
):
    """Retourne l'état du retour pour une réservation."""
    return await ops_svc.get_return_state(reservation_id, current_user.tenant_id, db)


@router.post("/return/{reservation_id}", response_model=ReturnState)
async def validate_return(
    reservation_id: int,
    data: ReturnValidateRequest = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_WRITE)),
):
    """Valide le retour matériel : transition delivered → returned (ou returned_dispute si dommages).

    Si des items avec dommages sont fournis, crée automatiquement :
    - un DamageType (ou réutilise l'existant)
    - un InventoryMovementDamage
    - une InvoiceCharge sur la facture si fee_cents > 0
    """
    signature_url = data.signature_url if data else None
    items = data.items if data else []
    return await ops_svc.validate_return(reservation_id, current_user.tenant_id, db, signature_url, items)


@router.post("/return/{reservation_id}/damage", response_model=DamageReportResponse)
async def declare_damage(
    reservation_id: int,
    data: ReturnDamageRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_WRITE)),
):
    """Déclare un dommage lors du retour — crée ou réutilise un DamageType."""
    return await ops_svc.declare_damage(
        reservation_id,
        current_user.tenant_id,
        db,
        damage_type_name=data.damage_type_name,
        description=data.description,
        fee_cents=data.fee_cents,
    )


# ---------------------------------------------------------------------------
# QR Code
# ---------------------------------------------------------------------------

@router.get("/qr/{code}", response_model=QrResult)
async def resolve_qr(
    code: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
):
    """Résout un code QR ou numéro de série → product_id + stock_item_id."""
    return await ops_svc.resolve_qr(code, current_user.tenant_id, db)


# ---------------------------------------------------------------------------
# Photo dommage
# ---------------------------------------------------------------------------

@router.post("/damage/photo", response_model=PhotoUploadResponse)
async def upload_damage_photo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_WRITE)),
):
    """Reçoit une photo de dommage, la sauvegarde sur disque et retourne l'URL."""
    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=ErrorMessages.IMAGE_FORMAT_INVALID,
        )

    content = await file.read()
    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 10 MiB).")

    uploads_root = settings.UPLOAD_DIR or "uploads"
    if not os.path.isabs(uploads_root):
        uploads_root = os.path.abspath(uploads_root)
    damage_dir = Path(uploads_root) / "damages"
    try:
        damage_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        fallback_dir = Path(os.path.abspath("uploads")) / "damages"
        logger.warning(
            "Upload dir %s not writable; falling back to %s",
            damage_dir,
            fallback_dir,
        )
        fallback_dir.mkdir(parents=True, exist_ok=True)
        damage_dir = fallback_dir

    ext = Path(file.filename or "photo.jpg").suffix or ".jpg"
    filename = f"damage_{uuid.uuid4().hex}{ext}"
    dest = damage_dir / filename
    dest.write_bytes(content)

    url = f"/uploads/damages/{filename}"
    return PhotoUploadResponse(url=url, filename=filename)


# ---------------------------------------------------------------------------
# Dashboard opérationnel
# ---------------------------------------------------------------------------

@router.get("/summary")
async def get_operations_summary(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
):
    """Résumé opérationnel : départs à faire, retours attendus, retards."""
    from datetime import date
    from sqlalchemy import select, func
    from app.models.reservation import Reservation
    from app.models.customer import Customer

    today = date.today()
    tid = current_user.tenant_id

    rows = (await db.execute(
        select(Reservation, Customer)
        .outerjoin(Customer, Reservation.customer_id == Customer.id)
        .where(
            Reservation.tenant_id == tid,
            Reservation.is_archived == False,  # noqa: E712
            Reservation.status.in_(["confirmed", "confirmed_risk", "pre_check", "delivered", "extended"]),
        )
        .order_by(Reservation.delivery_date)
    )).all()

    departures = []
    returns_pending = []
    returns_overdue = []

    for resa, cust in rows:
        item = {
            "id": resa.id,
            "reference": resa.reference,
            "status": resa.status,
            "customer_name": cust.display_name if cust else None,
            "delivery_date": str(resa.delivery_date) if resa.delivery_date else None,
            "return_date": str(resa.return_date) if resa.return_date else None,
            "event_date": str(resa.event_date) if resa.event_date else None,
        }

        if resa.status in ("confirmed", "confirmed_risk", "pre_check"):
            departures.append(item)
        elif resa.status in ("delivered", "extended"):
            if resa.return_date and resa.return_date < today:
                returns_overdue.append(item)
            else:
                returns_pending.append(item)

    return {
        "departures": departures,
        "returns_pending": returns_pending,
        "returns_overdue": returns_overdue,
    }
