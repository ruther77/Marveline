"""Endpoints CRUD pour les factures avec workflows de paiement."""
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.invoice import Invoice
from app.services.invoice import InvoiceService
from app.repositories.invoice import InvoiceRepository
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceList,
    AddPaymentRequest,
)
from app.schemas.common import PaginationParams, PaginatedResponse
from app.constants import ErrorMessages, InvoiceStatus, ReservationStatus


router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("", response_model=PaginatedResponse[InvoiceList])
def list_invoices(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, description="Filtrer par statut: draft, sent, paid, overdue, cancelled"),
    reservation_id: Optional[int] = Query(None, description="Filtrer par réservation"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PaginatedResponse[InvoiceList]:
    """Liste toutes les factures avec pagination et filtres.

    Args:
        pagination: Paramètres de pagination (skip, limit)
        status_filter: Filtre par statut
        reservation_id: Filtre par réservation
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Liste paginée de factures

    Example:
        GET /api/v1/invoices?status_filter=paid&skip=0&limit=20

        Response:
        {
            "items": [
                {
                    "id": 1,
                    "invoice_number": "INV-2026-0001",
                    "reservation": {...},
                    "status": "paid",
                    "total_amount_cents": 50000,
                    "paid_amount_cents": 50000,
                    "is_paid": true,
                    ...
                }
            ],
            "total": 24,
            "skip": 0,
            "limit": 20
        }

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    repo = InvoiceRepository(db)

    # Construire filtres
    filters = {}
    if status_filter:
        filters["status"] = status_filter
    if reservation_id:
        filters["reservation_id"] = reservation_id

    # Récupérer factures avec total
    invoices, total = repo.list(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        filters=filters
    )

    return PaginatedResponse(
        items=[InvoiceList.model_validate(i) for i in invoices],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )


@router.get("/overdue", response_model=list[InvoiceList])
def list_overdue_invoices(
    as_of_date: Optional[date] = Query(None, description="Date de référence (défaut: aujourd'hui)"),
    limit: int = Query(100, ge=1, le=1000, description="Limite max de résultats (fix B4)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> list[InvoiceList]:
    """Récupère les factures en retard et met à jour leur statut.

    Args:
        as_of_date: Date de référence (défaut: aujourd'hui)
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Liste des factures en retard

    Example:
        GET /api/v1/invoices/overdue?as_of_date=2026-03-01

        Response:
        [
            {
                "id": 5,
                "invoice_number": "INV-2026-0005",
                "status": "overdue",
                "due_date": "2026-02-15",
                "total_amount_cents": 30000,
                "paid_amount_cents": 0,
                "remaining_amount_cents": 30000,
                ...
            }
        ]

    Business Rules:
        - Facture en retard si: due_date < as_of_date AND paid_amount < total_amount
        - Met à jour status → 'overdue'
        - Exclut factures annulées

    Transaction:
        - Commit automatique après mise à jour statuts

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = InvoiceService(db)

    try:
        overdue_invoices = service.check_overdue_invoices(
            tenant_id=current_user.tenant_id,
            as_of_date=as_of_date
        )
        db.commit()

        return [InvoiceList.model_validate(i) for i in overdue_invoices[:limit]]

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while checking overdue invoices: {str(e)}"
        )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> InvoiceResponse:
    """Récupère les détails d'une facture.

    Args:
        invoice_id: ID de la facture
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Détails complets de la facture

    Raises:
        HTTPException 404: Si facture non trouvée

    Example:
        GET /api/v1/invoices/1

        Response:
        {
            "id": 1,
            "invoice_number": "INV-2026-0001",
            "reservation": {
                "id": 1,
                "reference": "RES-2026-0001",
                ...
            },
            "issue_date": "2026-02-01",
            "due_date": "2026-02-15",
            "total_amount_cents": 50000,
            "paid_amount_cents": 50000,
            "remaining_amount_cents": 0,
            "is_paid": true,
            "status": "paid",
            "payment_method": "card",
            "payment_date": "2026-02-10",
            ...
        }

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id (404 si autre tenant)
    """
    repo = InvoiceRepository(db)

    invoice = repo.get_by_id(invoice_id, current_user.tenant_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.INVOICE_NOT_FOUND
        )

    return InvoiceResponse.model_validate(invoice)


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    invoice_data: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> InvoiceResponse:
    """Génère une facture depuis une réservation.

    Args:
        invoice_data: Données de la facture (reservation_id, dates)
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Facture créée (status=draft)

    Raises:
        HTTPException 404: Si réservation non trouvée
        HTTPException 400: Si facture déjà existe pour cette réservation

    Example:
        POST /api/v1/invoices
        Content-Type: application/json

        {
            "reservation_id": 1,
            "issue_date": "2026-03-01",
            "due_date": "2026-03-15"
        }

    Business Rules:
        - Une réservation → une seule facture (one-to-one)
        - Copie total_amount depuis réservation
        - Génère invoice_number unique (INV-YYYY-NNNN)
        - Status initial=ReservationStatus.DRAFT
        - paid_amount = 0

    Transaction:
        - Atomique (facture créée avec numéro unique)

    Security:
        - Authentification JWT requise
        - tenant_id ajouté automatiquement depuis JWT
    """
    service = InvoiceService(db)

    try:
        invoice = service.generate_from_reservation(invoice_data, current_user.tenant_id)
        db.commit()
        db.refresh(invoice)

        return InvoiceResponse.model_validate(invoice)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating invoice: {str(e)}"
        )


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: int,
    invoice_data: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> InvoiceResponse:
    """Met à jour une facture (PATCH partiel).

    Args:
        invoice_id: ID de la facture
        invoice_data: Données à mettre à jour
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Facture mise à jour

    Raises:
        HTTPException 404: Si facture non trouvée
        HTTPException 400: Si facture payée (immutable)

    Example:
        PATCH /api/v1/invoices/1
        Content-Type: application/json

        {
            "status": "sent",
            "due_date": "2026-03-20"
        }

    Business Rules:
        - reservation_id et invoice_number immutables
        - Factures 'paid' ne peuvent pas être modifiées
        - total_amount immutable (copié depuis réservation)

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = InvoiceService(db)

    try:
        invoice = service.update_invoice(invoice_id, invoice_data, current_user.tenant_id)
        db.commit()
        db.refresh(invoice)

        return InvoiceResponse.model_validate(invoice)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating invoice: {str(e)}"
        )


@router.post("/{invoice_id}/add-payment", response_model=InvoiceResponse)
def add_payment(
    invoice_id: int,
    payment_data: AddPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> InvoiceResponse:
    """Ajoute un paiement à une facture (partiel ou complet, workflow métier).

    Args:
        invoice_id: ID de la facture
        payment_data: Données du paiement (montant, méthode, date)
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Facture mise à jour

    Raises:
        HTTPException 404: Si facture non trouvée
        HTTPException 400: Si paiement invalide ou facture déjà payée

    Example:
        POST /api/v1/invoices/1/add-payment
        Content-Type: application/json

        {
            "amount_cents": 25000,
            "payment_method": "card",
            "payment_date": "2026-03-10"
        }

    Business Rules:
        - paid_amount ne peut pas dépasser total_amount
        - Si paid_amount >= total_amount → status=InvoiceStatus.PAID
        - Enregistre payment_method et payment_date
        - Peut être appelé plusieurs fois (paiements partiels)

    Transaction:
        - Atomique (mise à jour montant + status)

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = InvoiceService(db)

    try:
        invoice = service.add_payment(invoice_id, payment_data, current_user.tenant_id)
        db.commit()
        db.refresh(invoice)

        return InvoiceResponse.model_validate(invoice)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while adding payment: {str(e)}"
        )


@router.post("/{invoice_id}/cancel", response_model=InvoiceResponse)
def cancel_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> InvoiceResponse:
    """Annule une facture (workflow métier).

    Args:
        invoice_id: ID de la facture
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Facture annulée (status=cancelled)

    Raises:
        HTTPException 404: Si facture non trouvée
        HTTPException 400: Si facture déjà payée

    Example:
        POST /api/v1/invoices/1/cancel

        Response:
        {
            "id": 1,
            "invoice_number": "INV-2026-0001",
            "status": "cancelled",
            ...
        }

    Business Rules:
        - Factures 'paid' ne peuvent pas être annulées
        - Change status → 'cancelled'

    Transaction:
        - Atomique

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = InvoiceService(db)

    try:
        invoice = service.cancel_invoice(invoice_id, current_user.tenant_id)
        db.commit()
        db.refresh(invoice)

        return InvoiceResponse.model_validate(invoice)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while cancelling invoice: {str(e)}"
        )
