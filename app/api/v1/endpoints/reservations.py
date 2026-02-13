"""Endpoints CRUD pour les réservations avec workflows métier."""
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.reservation import Reservation
from app.services.reservation import ReservationService
from app.repositories.reservation import ReservationRepository
from app.schemas.reservation import (
    ReservationCreate,
    ReservationUpdate,
    ReservationResponse,
    ReservationList,
)
from app.schemas.common import PaginationParams, PaginatedResponse
from app.constants import ErrorMessages, ReservationStatus


router = APIRouter(prefix="/reservations", tags=["Reservations"])


@router.get("", response_model=PaginatedResponse[ReservationList])
def list_reservations(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, description="Filtrer par statut: draft, confirmed, in_progress, completed, cancelled"),
    start_date: Optional[date] = Query(None, description="Date de début de plage (delivery_date >= start_date)"),
    end_date: Optional[date] = Query(None, description="Date de fin de plage (delivery_date <= end_date)"),
    customer_id: Optional[int] = Query(None, description="Filtrer par client"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PaginatedResponse[ReservationList]:
    """Liste toutes les réservations avec pagination et filtres.

    Args:
        pagination: Paramètres de pagination (skip, limit)
        status_filter: Filtre par statut
        start_date: Date de début de plage (filtre delivery_date)
        end_date: Date de fin de plage (filtre delivery_date)
        customer_id: Filtre par client
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Liste paginée de réservations

    Example:
        GET /api/v1/reservations?status_filter=confirmed&start_date=2026-03-01&end_date=2026-03-31

        Response:
        {
            "items": [
                {
                    "id": 1,
                    "reference": "RES-2026-0001",
                    "customer": {...},
                    "status": "confirmed",
                    "delivery_date": "2026-03-15",
                    "rental_days": 3,
                    ...
                }
            ],
            "total": 8,
            "skip": 0,
            "limit": 20
        }

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    repo = ReservationRepository(db)

    # Filtre par statut si fourni
    if status_filter:
        reservations, total = repo.list_by_status(
            status=status_filter,
            tenant_id=current_user.tenant_id,
            skip=pagination.skip,
            limit=pagination.limit
        )

    # Filtre par plage de dates si fourni
    elif start_date or end_date:
        reservations, total = repo.list_by_date_range(
            start_date=start_date,
            end_date=end_date,
            tenant_id=current_user.tenant_id,
            skip=pagination.skip,
            limit=pagination.limit
        )

    # Liste standard
    else:
        filters = {}
        if customer_id:
            filters["customer_id"] = customer_id

        reservations, total = repo.list(
            tenant_id=current_user.tenant_id,
            skip=pagination.skip,
            limit=pagination.limit,
            filters=filters
        )

    return PaginatedResponse(
        items=[ReservationList.model_validate(r) for r in reservations],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )


@router.get("/{reservation_id}", response_model=ReservationResponse)
def get_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ReservationResponse:
    """Récupère les détails d'une réservation avec relations.

    Args:
        reservation_id: ID de la réservation
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Détails complets de la réservation (customer, lines avec products)

    Raises:
        HTTPException 404: Si réservation non trouvée

    Example:
        GET /api/v1/reservations/1

        Response:
        {
            "id": 1,
            "reference": "RES-2026-0001",
            "customer": {
                "id": 5,
                "first_name": "Jean",
                "last_name": "Dupont",
                ...
            },
            "lines": [
                {
                    "id": 1,
                    "product": {"id": 10, "name": "Table ronde", ...},
                    "quantity": 5,
                    "unit_price_cents": 2000,
                    "subtotal_cents": 30000,
                    ...
                }
            ],
            "status": "confirmed",
            "delivery_date": "2026-03-15",
            "return_date": "2026-03-17",
            "rental_days": 3,
            "total_amount_cents": 30000,
            "deposit_amount_cents": 25000,
            ...
        }

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id (404 si autre tenant)
    """
    repo = ReservationRepository(db)

    reservation = repo.get_by_id_with_relations(reservation_id, current_user.tenant_id)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.RESERVATION_NOT_FOUND
        )

    return ReservationResponse.model_validate(reservation)


@router.post("", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
def create_reservation(
    reservation_data: ReservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ReservationResponse:
    """Crée une nouvelle réservation avec ses lignes.

    Args:
        reservation_data: Données de la réservation (customer, dates, lignes)
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Réservation créée (status=draft)

    Raises:
        HTTPException 404: Si customer ou produits non trouvés
        HTTPException 400: Si validation échoue

    Example:
        POST /api/v1/reservations
        Content-Type: application/json

        {
            "customer_id": 5,
            "event_date": "2026-03-16",
            "delivery_date": "2026-03-15",
            "return_date": "2026-03-17",
            "event_location": "Château de Versailles",
            "lines": [
                {
                    "product_id": 10,
                    "quantity": 5
                },
                {
                    "product_id": 15,
                    "quantity": 20
                }
            ]
        }

    Business Rules:
        - Génère référence unique automatiquement (RES-YYYY-NNNN)
        - Status initial=ReservationStatus.DRAFT
        - Calcule total_amount et deposit_amount depuis les lignes
        - Copie prix produits (snapshot au moment réservation)
        - Vérifie cohérence dates (delivery <= event <= return)

    Transaction:
        - Atomique (réservation + toutes lignes créées ensemble)
        - Rollback si erreur sur n'importe quelle ligne

    Security:
        - Authentification JWT requise
        - tenant_id ajouté automatiquement depuis JWT
    """
    service = ReservationService(db)

    try:
        reservation = service.create_reservation(reservation_data, current_user.tenant_id)
        db.commit()
        db.refresh(reservation)

        # Recharger avec relations pour response complète
        repo = ReservationRepository(db)
        reservation = repo.get_by_id_with_relations(reservation.id, current_user.tenant_id)

        return ReservationResponse.model_validate(reservation)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating reservation: {str(e)}"
        )


@router.patch("/{reservation_id}", response_model=ReservationResponse)
def update_reservation(
    reservation_id: int,
    reservation_data: ReservationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ReservationResponse:
    """Met à jour une réservation (status=draft uniquement, PATCH partiel).

    Args:
        reservation_id: ID de la réservation
        reservation_data: Données à mettre à jour (PATCH partiel)
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Réservation mise à jour

    Raises:
        HTTPException 404: Si réservation non trouvée
        HTTPException 400: Si status != 'draft'

    Example:
        PATCH /api/v1/reservations/1
        Content-Type: application/json

        {
            "event_location": "Nouvel emplacement",
            "delivery_date": "2026-03-14"
        }

    Business Rules:
        - Seules les réservations 'draft' peuvent être modifiées
        - customer_id et reference immutables
        - Les lignes ne sont pas modifiables via update (endpoints dédiés)

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = ReservationService(db)

    try:
        reservation = service.update_reservation(reservation_id, reservation_data, current_user.tenant_id)
        db.commit()
        db.refresh(reservation)

        # Recharger avec relations
        repo = ReservationRepository(db)
        reservation = repo.get_by_id_with_relations(reservation.id, current_user.tenant_id)

        return ReservationResponse.model_validate(reservation)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating reservation: {str(e)}"
        )


@router.post("/{reservation_id}/confirm", response_model=ReservationResponse)
def confirm_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ReservationResponse:
    """Confirme une réservation et réserve le stock (workflow métier).

    Args:
        reservation_id: ID de la réservation
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Réservation confirmée (status=confirmed)

    Raises:
        HTTPException 404: Si réservation non trouvée
        HTTPException 400: Si status != 'draft' ou stock insuffisant

    Example:
        POST /api/v1/reservations/1/confirm

        Response:
        {
            "id": 1,
            "reference": "RES-2026-0001",
            "status": "confirmed",
            ...
        }

    Business Rules:
        - Statut doit être 'draft'
        - Réserve stock pour chaque ligne (available_quantity -= quantity)
        - Change status → 'confirmed'
        - Transaction atomique (rollback si stock insuffisant)

    Transaction:
        - ATOMIQUE: Toutes réservations stock réussies OU rollback complet
        - Si une seule ligne échoue → rollback de toutes les lignes

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = ReservationService(db)

    try:
        reservation = service.confirm_reservation(reservation_id, current_user.tenant_id)
        db.commit()
        db.refresh(reservation)

        # Recharger avec relations
        repo = ReservationRepository(db)
        reservation = repo.get_by_id_with_relations(reservation.id, current_user.tenant_id)

        return ReservationResponse.model_validate(reservation)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while confirming reservation: {str(e)}"
        )


@router.post("/{reservation_id}/cancel", response_model=ReservationResponse)
def cancel_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ReservationResponse:
    """Annule une réservation et libère le stock (workflow métier).

    Args:
        reservation_id: ID de la réservation
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Réservation annulée (status=cancelled)

    Raises:
        HTTPException 404: Si réservation non trouvée
        HTTPException 400: Si status = 'returned' ou 'cancelled'

    Example:
        POST /api/v1/reservations/1/cancel

        Response:
        {
            "id": 1,
            "reference": "RES-2026-0001",
            "status": "cancelled",
            ...
        }

    Business Rules:
        - Statut ne peut pas être 'returned' ou 'cancelled'
        - Libère stock si status était 'confirmed' ou 'delivered'
        - Change status → 'cancelled'
        - Transaction atomique

    Transaction:
        - ATOMIQUE: Toutes libérations stock réussies OU rollback complet

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = ReservationService(db)

    try:
        reservation = service.cancel_reservation(reservation_id, current_user.tenant_id)
        db.commit()
        db.refresh(reservation)

        # Recharger avec relations
        repo = ReservationRepository(db)
        reservation = repo.get_by_id_with_relations(reservation.id, current_user.tenant_id)

        return ReservationResponse.model_validate(reservation)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while cancelling reservation: {str(e)}"
        )
