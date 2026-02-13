"""Endpoints CRUD pour les produits (matériel de location)."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User
from app.models.product import Product
from app.services.product import ProductService
from app.repositories.product import ProductRepository
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductList,
)
from app.schemas.common import PaginationParams, PaginatedResponse
from app.constants import ErrorMessages, UserRole


router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=PaginatedResponse[ProductList])
def list_products(
    pagination: PaginationParams = Depends(),
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
    available_only: bool = Query(False, description="Ne retourner que les produits avec stock disponible (available_quantity > 0)"),
    is_active: bool = Query(True, description="Inclure uniquement les produits actifs"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PaginatedResponse[ProductList]:
    """Liste tous les produits avec pagination et filtres.

    Args:
        pagination: Paramètres de pagination (skip, limit)
        category: Filtre optionnel par catégorie
        available_only: Si True, ne retourne que produits avec stock > 0
        is_active: Si True, ne retourne que produits actifs (défaut: True)
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Liste paginée de produits

    Example:
        GET /api/v1/products?skip=0&limit=20&category=tables&available_only=true

        Response:
        {
            "items": [
                {
                    "id": 1,
                    "name": "Table ronde 150cm",
                    "sku": "TABLE-RONDE-150",
                    "category": "tables",
                    "price_per_day_cents": 2000,
                    "price_per_day_euros": 20.0,
                    ...
                }
            ],
            "total": 45,
            "skip": 0,
            "limit": 20
        }

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id
    """
    repo = ProductRepository(db)

    # Construire filtres
    filters = {}
    if category:
        filters["category"] = category
    if available_only:
        filters["available_quantity__gt"] = 0
    if not is_active:
        filters["include_inactive"] = True

    # Récupérer produits avec total
    products, total = repo.list(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        filters=filters
    )

    return PaginatedResponse(
        items=[ProductList.model_validate(p) for p in products],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ProductResponse:
    """Récupère les détails d'un produit.

    Args:
        product_id: ID du produit
        db: Session de base de données
        current_user: Utilisateur authentifié

    Returns:
        Détails complets du produit

    Raises:
        HTTPException 404: Si produit non trouvé

    Example:
        GET /api/v1/products/1

        Response:
        {
            "id": 1,
            "name": "Table ronde 150cm",
            "sku": "TABLE-RONDE-150",
            "category": "tables",
            "price_per_day_cents": 2000,
            "price_per_day_euros": 20.0,
            "deposit_amount_cents": 5000,
            "deposit_amount_euros": 50.0,
            "stock_quantity": 10,
            "available_quantity": 7,
            "condition": "excellent",
            "image_url": "https://...",
            "is_active": true,
            "tenant_id": 1,
            "created_at": "2026-01-15T10:30:00Z",
            "updated_at": "2026-02-10T14:20:00Z"
        }

    Security:
        - Authentification JWT requise
        - Filtrage automatique par tenant_id (404 si autre tenant)
    """
    repo = ProductRepository(db)

    product = repo.get_by_id(product_id, current_user.tenant_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.PRODUCT_NOT_FOUND
        )

    return ProductResponse.model_validate(product)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
) -> ProductResponse:
    """Crée un nouveau produit (admin only).

    Args:
        product_data: Données du produit à créer
        db: Session de base de données
        current_user: Utilisateur admin authentifié

    Returns:
        Produit créé

    Raises:
        HTTPException 400: Si SKU déjà existant ou données invalides
        HTTPException 403: Si utilisateur non admin

    Example:
        POST /api/v1/products
        Content-Type: application/json

        {
            "name": "Chaise Napoléon dorée",
            "sku": "CHAISE-NAP-OR",
            "category": "chaises",
            "price_per_day_cents": 500,
            "deposit_amount_cents": 1000,
            "stock_quantity": 50,
            "available_quantity": 50,
            "condition": "excellent",
            "image_url": "https://..."
        }

    Business Rules:
        - SKU unique par tenant
        - available_quantity <= stock_quantity (validé par service)
        - is_active = True par défaut

    Security:
        - Authentification JWT requise
        - Rôle admin obligatoire
        - tenant_id ajouté automatiquement depuis JWT
    """
    service = ProductService(db)

    try:
        product = service.create_product(product_data, current_user.tenant_id)
        db.commit()
        db.refresh(product)

        return ProductResponse.model_validate(product)

    except HTTPException:
        raise
    except IntegrityError as e:
        # Race condition : SKU déjà créé par thread concurrent
        if "unique constraint" in str(e).lower() or "sku" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product with SKU '{product_data.sku}' already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database integrity error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating product: {str(e)}"
        )


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    product_data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
) -> ProductResponse:
    """Met à jour un produit existant (admin only, PATCH partiel).

    Args:
        product_id: ID du produit
        product_data: Données à mettre à jour (PATCH partiel)
        db: Session de base de données
        current_user: Utilisateur admin authentifié

    Returns:
        Produit mis à jour

    Raises:
        HTTPException 404: Si produit non trouvé
        HTTPException 400: Si validation échoue (ex: available > stock)
        HTTPException 403: Si utilisateur non admin

    Example:
        PATCH /api/v1/products/1
        Content-Type: application/json

        {
            "price_per_day_cents": 600,
            "stock_quantity": 60
        }

    Business Rules:
        - SKU immutable (ne peut pas être changé)
        - available_quantity <= stock_quantity
        - Seuls champs fournis sont mis à jour (PATCH partiel)

    Security:
        - Authentification JWT requise
        - Rôle admin obligatoire
        - Filtrage automatique par tenant_id
    """
    service = ProductService(db)

    try:
        product = service.update_product(product_id, product_data, current_user.tenant_id)
        db.commit()
        db.refresh(product)

        return ProductResponse.model_validate(product)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating product: {str(e)}"
        )


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    hard_delete: bool = Query(False, description="Si True, suppression physique (défaut: soft delete)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
) -> None:
    """Supprime un produit (admin only, soft delete par défaut).

    Args:
        product_id: ID du produit
        hard_delete: Si True, suppression physique, sinon is_active=False
        db: Session de base de données
        current_user: Utilisateur admin authentifié

    Raises:
        HTTPException 404: Si produit non trouvé
        HTTPException 400: Si contraintes FK (hard delete avec réservations liées)
        HTTPException 403: Si utilisateur non admin

    Example:
        DELETE /api/v1/products/1?hard_delete=false

        Response: 204 No Content

    Business Rules:
        - Soft delete par défaut (is_active=False)
        - Hard delete seulement si aucune réservation liée
        - Produits soft-deleted exclus des listes par défaut

    Security:
        - Authentification JWT requise
        - Rôle admin obligatoire
        - Filtrage automatique par tenant_id
    """
    service = ProductService(db)

    try:
        service.delete_product(product_id, current_user.tenant_id, hard_delete=hard_delete)
        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting product: {str(e)}"
        )
