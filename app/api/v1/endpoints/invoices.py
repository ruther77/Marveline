"""Endpoints CRUD pour les factures avec workflows de paiement."""
import logging
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.constants.errors import ErrorMessages
from app.core.exceptions import NotFound
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.models.invoice import Invoice
from app.services.invoice import InvoiceService
from app.repositories.invoice import AsyncInvoiceRepository
from app.services.invoice_pdf import generate_invoice_pdf, load_brand_for_tenant
from app.services.payment import PaymentService
from app.schemas.payment import PaymentCreate, PaymentRead
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceList,
    AddPaymentRequest,
    InvoiceChargeCreate,
    InvoiceChargeRead,
    CreditNoteCreate,
    CreditNoteResponse,
    MarkSentRequest,
    RemindRequest,
    DamageInvoiceCreate,
    TvaReportResponse,
    SequenceGapsResponse,
)
from app.schemas.common import PaginationParams, PaginatedResponse
from app.constants import ErrorMessages, InvoiceStatus, ReservationStatus
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogResponse
import app.services.invoice_credit_note as cn_svc


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("", response_model=PaginatedResponse[InvoiceList])
async def list_invoices(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, description="Filtrer par statut: draft, sent, paid, overdue, cancelled"),
    reservation_id: Optional[int] = Query(None, description="Filtrer par réservation"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_READ)),
) -> PaginatedResponse[InvoiceList]:
    """Liste toutes les factures avec pagination et filtres."""
    service = InvoiceService(db)
    invoices, total = await service.list_invoices(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        status_filter=status_filter,
        reservation_id=reservation_id,
    )
    return PaginatedResponse(
        items=[InvoiceList.model_validate(i) for i in invoices],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/sequence/gaps", response_model=SequenceGapsResponse)
async def get_sequence_gaps(
    year: int = Query(..., ge=2020, le=2100, description="Année à analyser (ex: 2026)"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_READ)),
) -> SequenceGapsResponse:
    """Détecte les trous dans la séquence de numérotation des factures."""
    prefix = f"INV-{year}-"
    result = await db.execute(
        select(Invoice.invoice_number).filter(
            Invoice.invoice_number.like(f"{prefix}%")
        ).order_by(Invoice.invoice_number)
    )
    rows = result.scalars().all()

    if not rows:
        return {"year": year, "gaps": [], "count": 0}

    numbers: list[int] = []
    for num in rows:
        try:
            numbers.append(int(num.rsplit("-", 1)[-1]))
        except (ValueError, IndexError):
            logger.warning("Numéro de facture mal formé ignoré : %r", num)

    if not numbers:
        return {"year": year, "gaps": [], "count": 0}

    numbers.sort()
    full_range = set(range(numbers[0], numbers[-1] + 1))
    gaps = sorted(full_range - set(numbers))
    return {"year": year, "gaps": gaps, "count": len(gaps)}


@router.get("/overdue", response_model=PaginatedResponse[InvoiceList])
async def list_overdue_invoices(
    as_of_date: Optional[date] = Query(None, description="Date de référence (défaut: aujourd'hui)"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_READ)),
) -> PaginatedResponse[InvoiceList]:
    """Récupère les factures en retard et met à jour leur statut."""
    service = InvoiceService(db)
    try:
        overdue_invoices = await service.check_overdue_invoices(
            tenant_id=current_user.tenant_id,
            as_of_date=as_of_date,
            limit=pagination.limit,
            skip=pagination.skip,
        )
        await db.commit()
        return PaginatedResponse(
            items=[InvoiceList.model_validate(i) for i in overdue_invoices],
            total=len(overdue_invoices),
            skip=pagination.skip,
            limit=pagination.limit,
        )
    except HTTPException:
        raise


@router.get("/tva-report", response_model=TvaReportResponse)
async def get_tva_report(
    month: str = Query(..., description="Mois au format YYYY-MM (ex: 2026-02)"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_READ)),
) -> TvaReportResponse:
    """Rapport TVA mensuel : base HT, TVA collectée et TTC par taux de TVA."""
    service = InvoiceService(db)
    data = await service.generate_tva_report(current_user.tenant_id, month)
    return TvaReportResponse.model_validate(data)


@router.get("/payments", response_model=PaginatedResponse[PaymentRead])
async def list_all_payments(
    date_from: Optional[date] = Query(None, description="Date début (incluse)"),
    date_to: Optional[date] = Query(None, description="Date fin (incluse)"),
    payment_method: Optional[str] = Query(None, description="Méthode de paiement"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_READ)),
) -> PaginatedResponse[PaymentRead]:
    """Liste tous les paiements du tenant (toutes factures confondues)."""
    from sqlalchemy import func
    from app.models.payment import Payment

    base = select(Payment).filter(Payment.tenant_id == current_user.tenant_id)
    if date_from:
        base = base.filter(Payment.payment_date >= date_from)
    if date_to:
        base = base.filter(Payment.payment_date <= date_to)
    if payment_method:
        base = base.filter(Payment.payment_method == payment_method)
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0
    query = base.order_by(Payment.payment_date.desc()).offset(pagination.skip).limit(pagination.limit)
    payments = (await db.execute(query)).scalars().all()
    return PaginatedResponse(
        items=[PaymentRead.model_validate(p) for p in payments],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_READ)),
) -> Response:
    """Génère et retourne le PDF d'une facture."""
    service = InvoiceService(db)
    invoice = await service.get_invoice(invoice_id, current_user.tenant_id)
    brand = await load_brand_for_tenant(db, current_user.tenant_id)
    try:
        pdf_bytes = generate_invoice_pdf(invoice, brand=brand)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Erreur génération PDF facture %s", invoice_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorMessages.INVOICE_PDF_GENERATION_FAILED,
        )
    filename = f"facture-{invoice.invoice_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_READ)),
) -> InvoiceResponse:
    """Récupère les détails d'une facture."""
    service = InvoiceService(db)
    invoice = await service.get_invoice(invoice_id, current_user.tenant_id)
    return InvoiceResponse.model_validate(invoice)


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice_data: InvoiceCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_WRITE)),
) -> InvoiceResponse:
    """Génère une facture depuis une réservation."""
    service = InvoiceService(db)
    try:
        invoice = await service.generate_from_reservation(
            invoice_data,
            current_user.tenant_id,
            invoice_type=invoice_data.invoice_type or "full",
        )
        await db.commit()
        return InvoiceResponse.model_validate(invoice)
    except HTTPException:
        raise


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: int,
    invoice_data: InvoiceUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_WRITE)),
) -> InvoiceResponse:
    """Met à jour une facture (PATCH partiel)."""
    service = InvoiceService(db)
    try:
        invoice = await service.update_invoice(invoice_id, invoice_data, current_user.tenant_id)
        await db.commit()
        return InvoiceResponse.model_validate(invoice)
    except HTTPException:
        raise


@router.post(
    "/{invoice_id}/add-payment",
    response_model=InvoiceResponse,
    deprecated=True,
)
async def add_payment(
    invoice_id: int,
    payment_data: AddPaymentRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_WRITE)),
) -> InvoiceResponse:
    """[DÉPRÉCIÉ] Ajoute un paiement à une facture. Utiliser POST /{id}/payments à la place."""
    service = InvoiceService(db)
    try:
        invoice = await service.add_payment(invoice_id, payment_data, current_user.tenant_id)
        await db.commit()
        return InvoiceResponse.model_validate(invoice)
    except HTTPException:
        raise


@router.post("/{invoice_id}/cancel", response_model=InvoiceResponse)
async def cancel_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_WRITE)),
) -> InvoiceResponse:
    """Annule une facture."""
    service = InvoiceService(db)
    try:
        invoice = await service.cancel_invoice(invoice_id, current_user.tenant_id)
        await db.commit()
        return InvoiceResponse.model_validate(invoice)
    except HTTPException:
        raise


@router.post(
    "/{invoice_id}/add-charge",
    response_model=InvoiceChargeRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_charge(
    invoice_id: int,
    charge_data: InvoiceChargeCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_WRITE)),
) -> InvoiceChargeRead:
    """Ajoute une charge additionnelle (dommage ou main-d'œuvre) à une facture."""
    service = InvoiceService(db)
    try:
        charge = await service.add_charge(invoice_id, current_user.tenant_id, charge_data)
        await db.commit()
        return InvoiceChargeRead.model_validate(charge)
    except HTTPException:
        raise


@router.post(
    "/{invoice_id}/payments",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment(
    invoice_id: int,
    payment_data: PaymentCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_WRITE)),
) -> PaymentRead:
    """Enregistre un paiement sur une facture."""
    service = PaymentService(db)
    payment = await service.add_payment(invoice_id, payment_data, current_user.tenant_id)
    await db.commit()
    return PaymentRead.model_validate(payment)


@router.get("/{invoice_id}/payments", response_model=PaginatedResponse[PaymentRead])
async def list_payments(
    invoice_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_READ)),
) -> PaginatedResponse[PaymentRead]:
    """Liste les paiements d'une facture."""
    service = PaymentService(db)
    payments = await service.list_payments(invoice_id, current_user.tenant_id)
    items = [PaymentRead.model_validate(p) for p in payments]
    return PaginatedResponse[PaymentRead](items=items, total=len(items), skip=0, limit=max(len(items), 1))


# ---------------------------------------------------------------------------
# Credit Notes (avoirs)
# ---------------------------------------------------------------------------


@router.post("/damage", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_damage_invoice(
    data: DamageInvoiceCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_WRITE)),
) -> InvoiceResponse:
    """Crée une facture de dommages liée à une réservation."""
    invoice = await cn_svc.create_damage_invoice(
        db,
        tenant_id=current_user.tenant_id,
        reservation_id=data.reservation_id,
        charges=[c.model_dump() for c in data.charges],
        notes=data.notes,
    )
    return InvoiceResponse.model_validate(invoice)


@router.post("/{invoice_id}/credit-note", response_model=CreditNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_credit_note(
    invoice_id: int,
    data: CreditNoteCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_WRITE)),
) -> CreditNoteResponse:
    """Crée un avoir sur une facture."""
    cn = await cn_svc.create_credit_note(db, current_user.tenant_id, invoice_id, data)
    return CreditNoteResponse.model_validate(cn)


@router.get("/{invoice_id}/credit-notes", response_model=PaginatedResponse[CreditNoteResponse])
async def list_credit_notes(
    invoice_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_READ)),
) -> PaginatedResponse[CreditNoteResponse]:
    """Liste les avoirs d'une facture."""
    notes = await cn_svc.list_credit_notes(db, current_user.tenant_id, invoice_id)
    items = [CreditNoteResponse.model_validate(n) for n in notes]
    return PaginatedResponse[CreditNoteResponse](items=items, total=len(items), skip=0, limit=max(len(items), 1))


@router.post("/{invoice_id}/credit-notes/{cn_id}/issue", response_model=CreditNoteResponse)
async def issue_credit_note(
    invoice_id: int,
    cn_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.INVOICES_WRITE)),
) -> CreditNoteResponse:
    """Emet un avoir (draft → issued)."""
    cn = await cn_svc.issue_credit_note(db, current_user.tenant_id, invoice_id, cn_id)
    return CreditNoteResponse.model_validate(cn)


@router.post("/{invoice_id}/credit-notes/{cn_id}/apply", response_model=CreditNoteResponse)
async def apply_credit_note(
    invoice_id: int,
    cn_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_WRITE)),
) -> CreditNoteResponse:
    """Impute un avoir sur la prochaine facture (issued → applied)."""
    cn = await cn_svc.apply_credit_note(db, current_user.tenant_id, invoice_id, cn_id)
    return CreditNoteResponse.model_validate(cn)


@router.post("/{invoice_id}/credit-notes/{cn_id}/refund", response_model=CreditNoteResponse)
async def refund_credit_note(
    invoice_id: int,
    cn_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_WRITE)),
) -> CreditNoteResponse:
    """Rembourse un avoir (issued → refunded)."""
    cn = await cn_svc.refund_credit_note(db, current_user.tenant_id, invoice_id, cn_id)
    return CreditNoteResponse.model_validate(cn)


@router.post("/{invoice_id}/mark-sent", response_model=InvoiceResponse)
async def mark_sent(
    invoice_id: int,
    data: MarkSentRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_WRITE)),
) -> InvoiceResponse:
    """Marque une facture comme envoyée."""
    invoice = await cn_svc.mark_invoice_sent(
        db, current_user.tenant_id, invoice_id,
        sent_date=data.sent_at, notes=data.notes,
    )
    return InvoiceResponse.model_validate(invoice)


@router.post("/{invoice_id}/remind", response_model=InvoiceResponse)
async def remind(
    invoice_id: int,
    data: RemindRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_WRITE)),
) -> InvoiceResponse:
    """Enregistre une relance sur une facture."""
    invoice = await cn_svc.remind_invoice(db, current_user.tenant_id, invoice_id, notes=data.notes)
    return InvoiceResponse.model_validate(invoice)


@router.get("/{invoice_id}/full", response_model=InvoiceResponse)
async def get_invoice_full(
    invoice_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_READ)),
) -> InvoiceResponse:
    """Retourne la facture avec toutes ses relations (réservation, client, charges, paiements)."""
    repo = AsyncInvoiceRepository(db)
    invoice = await repo.get_by_id_with_relations(invoice_id, current_user.tenant_id)
    if not invoice:
        raise NotFound(ErrorMessages.INVOICE_NOT_FOUND)
    return InvoiceResponse.model_validate(invoice)


@router.get("/{invoice_id}/audit", response_model=PaginatedResponse[AuditLogResponse])
async def get_invoice_audit(
    invoice_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat =Depends(require_scope(Scope.INVOICES_READ)),
) -> PaginatedResponse[AuditLogResponse]:
    """Retourne le journal d'audit de la facture."""
    repo = AsyncInvoiceRepository(db)
    invoice = await repo.get_by_id(invoice_id, current_user.tenant_id)
    if not invoice:
        raise NotFound(ErrorMessages.INVOICE_NOT_FOUND)
    result = await db.execute(
        select(AuditLog)
        .filter(
            AuditLog.tenant_id == current_user.tenant_id,
            AuditLog.entity_type == "Invoice",
            AuditLog.entity_id == invoice_id,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    items = [AuditLogResponse.model_validate(log) for log in logs]
    return PaginatedResponse[AuditLogResponse](items=items, total=len(items), skip=0, limit=limit)
