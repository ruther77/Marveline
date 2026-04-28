"""Endpoints CRUD pour les fournisseurs."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.errors import ErrorMessages
from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.repositories.supplier import AsyncSupplierRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


async def _get_or_404(supplier_id: int, tenant_id: int, db: AsyncSession):
    repo = AsyncSupplierRepository(db)
    s = await repo.get_by_id(supplier_id, tenant_id)
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fournisseur {supplier_id} introuvable",
        )
    return s


@router.get("", response_model=PaginatedResponse[SupplierRead])
async def list_suppliers(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_READ)),
) -> PaginatedResponse[SupplierRead]:
    """Liste les fournisseurs actifs du tenant."""
    repo = AsyncSupplierRepository(db)
    all_items = await repo.list_active(current_user.tenant_id)
    total = len(all_items)
    page = all_items[pagination.skip : pagination.skip + pagination.limit]
    return PaginatedResponse[SupplierRead](
        items=[SupplierRead.model_validate(s) for s in page],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_WRITE)),
) -> SupplierRead:
    """Crée un fournisseur."""
    repo = AsyncSupplierRepository(db)
    if await repo.name_exists(data.name, current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorMessages.SUPPLIER_NAME_EXISTS,
        )
    supplier = await repo.create({"tenant_id": current_user.tenant_id, **data.model_dump()})
    await db.commit()
    await db.refresh(supplier)
    return SupplierRead.model_validate(supplier)


@router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_READ)),
) -> SupplierRead:
    """Récupère un fournisseur par ID."""
    supplier = await _get_or_404(supplier_id, current_user.tenant_id, db)
    return SupplierRead.model_validate(supplier)


@router.patch("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_WRITE)),
) -> SupplierRead:
    """Met à jour un fournisseur (PATCH partiel)."""
    supplier = await _get_or_404(supplier_id, current_user.tenant_id, db)
    repo = AsyncSupplierRepository(db)

    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] != supplier.name:
        if await repo.name_exists(update_data["name"], current_user.tenant_id, exclude_id=supplier_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorMessages.SUPPLIER_NAME_EXISTS,
            )

    supplier = await repo.update(supplier, update_data)
    await db.commit()
    await db.refresh(supplier)
    return SupplierRead.model_validate(supplier)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SUPPLIERS_WRITE)),
) -> None:
    """Supprime (soft delete) un fournisseur."""
    supplier = await _get_or_404(supplier_id, current_user.tenant_id, db)
    repo = AsyncSupplierRepository(db)
    await repo.soft_delete(supplier)
    await db.commit()
