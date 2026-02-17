"""Endpoints CRUD pour les clients (particuliers et entreprises)."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.customer import CustomerService
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerList,
)
from app.schemas.common import PaginationParams, PaginatedResponse
from app.constants import ErrorMessages


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=PaginatedResponse[CustomerList])
def list_customers(
    pagination: PaginationParams = Depends(),
    search_query: Optional[str] = Query(None, description="Rechercher par nom, prénom, email, ou entreprise"),
    customer_type: Optional[str] = Query(None, description="Filtrer par type: individual ou company"),
    is_active: bool = Query(True, description="Inclure uniquement les clients actifs"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PaginatedResponse[CustomerList]:
    """Liste tous les clients avec pagination et filtres.

    Args:
        pagination: Paramètres de pagination (skip, limit)
        search_query: Recherche textuelle sur nom/prénom/email/entreprise
        customer_type: Filtre par type (individual, company)
        is_active: Si True, ne retourne que clients actifs (défaut: True)
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Liste paginée de clients

    Example:
        GET /api/v1/customers?skip=0&limit=20&search_query=dupont&customer_type=individual

        Response:
        {
            "items": [
                {
                    "id": 1,
                    "customer_type": "individual",
                    "first_name": "Jean",
                    "last_name": "Dupont",
                    "email": "jean.dupont@example.com",
                    "phone": "+33612345678",
                    ...
                }
            ],
            "total": 12,
            "skip": 0,
            "limit": 20
        }

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = CustomerService(db)

    customers, total = service.list_customers(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        search_query=search_query,
        customer_type=customer_type,
        include_inactive=not is_active,
    )

    return PaginatedResponse(
        items=[CustomerList.model_validate(c) for c in customers],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> CustomerResponse:
    """Récupère les détails d'un client.

    Args:
        customer_id: ID du client
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Détails complets du client

    Raises:
        HTTPException 404: Si client non trouvé

    Example:
        GET /api/v1/customers/1

        Response:
        {
            "id": 1,
            "customer_type": "individual",
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean.dupont@example.com",
            "phone": "+33612345678",
            "address": "10 rue de la Paix",
            "city": "Paris",
            "postal_code": "75001",
            "company_name": null,
            "siret": null,
            "notes": "Client VIP",
            "is_active": true,
            "tenant_id": 1,
            "created_at": "2026-01-10T09:00:00Z",
            "updated_at": "2026-02-10T11:30:00Z"
        }

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id (404 si autre tenant)
    """
    service = CustomerService(db)
    customer = service.get_customer(customer_id, current_user.tenant_id)
    return CustomerResponse.model_validate(customer)


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> CustomerResponse:
    """Crée un nouveau client.

    Args:
        customer_data: Données du client à créer
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Client créé

    Raises:
        HTTPException 400: Si email déjà existant ou données invalides

    Example:
        POST /api/v1/customers
        Content-Type: application/json

        {
            "customer_type": "individual",
            "first_name": "Marie",
            "last_name": "Martin",
            "email": "marie.martin@example.com",
            "phone": "+33687654321",
            "address": "25 avenue des Champs",
            "city": "Lyon",
            "postal_code": "69001"
        }

    Business Rules:
        - Type "individual": first_name + last_name obligatoires
        - Type "company": company_name + siret obligatoires
        - Email unique par tenant (optionnel)
        - is_active = True par défaut

    Security:
        - Authentification JWT requise
        - tenant_id ajouté automatiquement depuis JWT
    """
    service = CustomerService(db)

    try:
        customer = service.create_customer(customer_data, current_user.tenant_id)
        db.commit()
        db.refresh(customer)
        return CustomerResponse.model_validate(customer)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in create_customer")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating customer: {str(e)}"
        )


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> CustomerResponse:
    """Met à jour un client existant (PATCH partiel).

    Args:
        customer_id: ID du client
        customer_data: Données à mettre à jour (PATCH partiel)
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Client mis à jour

    Raises:
        HTTPException 404: Si client non trouvé
        HTTPException 400: Si validation échoue ou email déjà utilisé

    Example:
        PATCH /api/v1/customers/1
        Content-Type: application/json

        {
            "phone": "+33612345678",
            "address": "Nouvelle adresse",
            "notes": "Client fidèle"
        }

    Business Rules:
        - Validation cohérence customer_type si modifié
        - Email unique si modifié
        - Seuls champs fournis sont mis à jour (PATCH partiel)

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = CustomerService(db)

    try:
        customer = service.update_customer(customer_id, customer_data, current_user.tenant_id)
        db.commit()
        db.refresh(customer)
        return CustomerResponse.model_validate(customer)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in update_customer")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating customer: {str(e)}"
        )


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int,
    hard_delete: bool = Query(False, description="Si True, suppression physique (défaut: soft delete)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> None:
    """Supprime un client (soft delete par défaut).

    Args:
        customer_id: ID du client
        hard_delete: Si True, suppression physique, sinon is_active=False
        db: Session de base de données
        current_user: Utilisateur authentifié

    Raises:
        HTTPException 404: Si client non trouvé
        HTTPException 400: Si contraintes FK (hard delete avec réservations liées)

    Example:
        DELETE /api/v1/customers/1?hard_delete=false

        Response: 204 No Content

    Business Rules:
        - Soft delete par défaut (is_active=False)
        - Hard delete seulement si aucune réservation liée
        - Clients soft-deleted exclus des listes par défaut

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    service = CustomerService(db)

    try:
        service.delete_customer(customer_id, current_user.tenant_id, hard_delete)
        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in delete_customer")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting customer: {str(e)}"
        )
