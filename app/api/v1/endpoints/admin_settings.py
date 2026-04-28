"""Endpoints Admin Settings — GET/PATCH /admin/settings."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.repositories.tenant_settings import AsyncTenantSettingsRepository
from app.schemas.tenant_settings import TenantSettingsRead, TenantSettingsUpdate

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])


@router.get("", response_model=TenantSettingsRead)
async def get_settings(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Retourne les paramètres métier du tenant."""
    repo = AsyncTenantSettingsRepository(db)
    obj = await repo.get(current_user.tenant_id)
    await db.commit()
    return TenantSettingsRead.model_validate(obj)


@router.patch("", response_model=TenantSettingsRead)
async def update_settings(
    data: TenantSettingsUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Met à jour les paramètres métier du tenant."""
    repo = AsyncTenantSettingsRepository(db)
    obj = await repo.update(current_user.tenant_id, data)
    await db.commit()
    return TenantSettingsRead.model_validate(obj)
