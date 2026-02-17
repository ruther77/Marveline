"""Endpoints CRUD pour les categories de produits."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.core.permissions import Permission
from app.models.user import User
from app.services.category import CategoryService
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryTreeNode,
)
from app.schemas.common import PaginationParams, PaginatedResponse
from app.constants import ErrorMessages


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=PaginatedResponse[CategoryResponse])
def list_categories(
    pagination: PaginationParams = Depends(),
    active_only: bool = Query(True, description="Filtrer categories actives uniquement"),
    parent_id: Optional[int] = Query(None, description="Filtrer par categorie parente"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[CategoryResponse]:
    """Liste les categories avec pagination."""
    service = CategoryService(db)

    categories, total = service.list_categories(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        parent_id=parent_id,
        include_inactive=not active_only,
    )

    return PaginatedResponse(
        items=[CategoryResponse.model_validate(c) for c in categories],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/tree", response_model=list[CategoryTreeNode])
def get_category_tree(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CategoryTreeNode]:
    """Retourne l'arbre hierarchique des categories."""
    service = CategoryService(db)
    return service.get_tree(current_user.tenant_id)


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CategoryResponse:
    """Recupere les details d'une categorie."""
    service = CategoryService(db)
    category = service.get_category(category_id, current_user.tenant_id)
    return CategoryResponse.model_validate(category)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CATEGORIES_WRITE)),
) -> CategoryResponse:
    """Cree une nouvelle categorie (admin uniquement)."""
    service = CategoryService(db)
    try:
        category = service.create_category(data, current_user.tenant_id)
        db.commit()
        db.refresh(category)
        return CategoryResponse.model_validate(category)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in create_category")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating category: {str(e)}",
        )


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CATEGORIES_WRITE)),
) -> CategoryResponse:
    """Met a jour une categorie (admin uniquement)."""
    service = CategoryService(db)
    try:
        category = service.update_category(category_id, data, current_user.tenant_id)
        db.commit()
        db.refresh(category)
        return CategoryResponse.model_validate(category)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in update_category")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating category: {str(e)}",
        )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CATEGORIES_DELETE)),
) -> None:
    """Soft delete une categorie (admin uniquement)."""
    service = CategoryService(db)
    try:
        service.delete_category(category_id, current_user.tenant_id)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in delete_category")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting category: {str(e)}",
        )
