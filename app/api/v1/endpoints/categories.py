"""Endpoints CRUD pour les categories de produits."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
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
async def list_categories(
    pagination: PaginationParams = Depends(),
    active_only: bool = Query(True, description="Filtrer categories actives uniquement"),
    parent_id: Optional[int] = Query(None, description="Filtrer par categorie parente"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CATEGORIES_READ)),
) -> PaginatedResponse[CategoryResponse]:
    """Liste les categories avec pagination."""
    service = CategoryService(db)
    categories, total = await service.list_categories(
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
async def get_category_tree(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CATEGORIES_READ)),
) -> list[CategoryTreeNode]:
    """Retourne l'arbre hierarchique des categories."""
    service = CategoryService(db)
    return await service.get_tree(current_user.tenant_id)


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CATEGORIES_READ)),
) -> CategoryResponse:
    """Recupere les details d'une categorie."""
    service = CategoryService(db)
    category = await service.get_category(category_id, current_user.tenant_id)
    return CategoryResponse.model_validate(category)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CATEGORIES_WRITE)),
) -> CategoryResponse:
    """Cree une nouvelle categorie (categories:write requis)."""
    service = CategoryService(db)
    try:
        category = await service.create_category(data, current_user.tenant_id)
        await db.commit()
        return CategoryResponse.model_validate(category)
    except HTTPException:
        raise


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CATEGORIES_WRITE)),
) -> CategoryResponse:
    """Met a jour une categorie (categories:write requis)."""
    service = CategoryService(db)
    try:
        category = await service.update_category(category_id, data, current_user.tenant_id)
        await db.commit()
        return CategoryResponse.model_validate(category)
    except HTTPException:
        raise


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.CATEGORIES_DELETE)),
) -> None:
    """Soft delete une categorie (categories:delete requis)."""
    service = CategoryService(db)
    try:
        await service.delete_category(category_id, current_user.tenant_id)
        await db.commit()
    except HTTPException:
        raise
