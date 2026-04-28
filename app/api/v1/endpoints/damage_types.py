"""Endpoints CRUD pour les types de dommages."""
import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user, require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.damage_type import DamageTypeCreate, DamageTypeRead, DamageTypeUpdate
from app.services.damage_type import DamageTypeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/damage-types", tags=["Damage Types"])


@router.get("", response_model=PaginatedResponse[DamageTypeRead])
async def list_damage_types(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
) -> PaginatedResponse[DamageTypeRead]:
    """Liste les types de dommages actifs du tenant."""
    service = DamageTypeService(db)
    all_items = await service.list_damage_types(current_user.tenant_id)
    total = len(all_items)
    page = all_items[pagination.skip : pagination.skip + pagination.limit]
    return PaginatedResponse[DamageTypeRead](
        items=[DamageTypeRead.model_validate(dt) for dt in page],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{damage_type_id}", response_model=DamageTypeRead)
async def get_damage_type(
    damage_type_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
) -> DamageTypeRead:
    """Récupère un type de dommage par ID."""
    service = DamageTypeService(db)
    dt = await service.get_damage_type(damage_type_id, current_user.tenant_id)
    return DamageTypeRead.model_validate(dt)


@router.post("", response_model=DamageTypeRead, status_code=status.HTTP_201_CREATED)
async def create_damage_type(
    data: DamageTypeCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.INVOICES_WRITE)),
) -> DamageTypeRead:
    """Crée un type de dommage (invoices:write)."""
    service = DamageTypeService(db)
    dt = await service.create_damage_type(data, current_user.tenant_id)
    await db.commit()
    await db.refresh(dt)
    return DamageTypeRead.model_validate(dt)


@router.patch("/{damage_type_id}", response_model=DamageTypeRead)
async def update_damage_type(
    damage_type_id: int,
    data: DamageTypeUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.INVOICES_WRITE)),
) -> DamageTypeRead:
    """Met à jour un type de dommage (PATCH partiel, invoices:write)."""
    service = DamageTypeService(db)
    dt = await service.update_damage_type(damage_type_id, data, current_user.tenant_id)
    await db.commit()
    await db.refresh(dt)
    return DamageTypeRead.model_validate(dt)


@router.delete("/{damage_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_damage_type(
    damage_type_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.INVOICES_WRITE)),
) -> None:
    """Supprime (soft delete) un type de dommage (invoices:write)."""
    service = DamageTypeService(db)
    await service.delete_damage_type(damage_type_id, current_user.tenant_id)
    await db.commit()
