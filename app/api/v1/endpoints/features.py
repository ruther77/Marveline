"""Endpoints CRUD pour les Feature Flags (admin uniquement)."""
import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.services.feature_flag import FeatureFlagService
from app.schemas.feature_flag import (
    FeatureFlagCreate,
    FeatureFlagUpdate,
    FeatureFlagResponse,
    FeatureFlagEvaluated,
    FeatureFlagList,
)
from app.schemas.common import PaginatedResponse, PaginationParams

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/features", tags=["Feature Flags"])


@router.post("", response_model=FeatureFlagResponse, status_code=status.HTTP_201_CREATED)
async def create_feature_flag(
    data: FeatureFlagCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.FEATURES_WRITE)),
) -> FeatureFlagResponse:
    """Cree un nouveau feature flag (admin only)."""
    service = FeatureFlagService(db)
    flag = await service.create_flag(data)
    await db.commit()
    await db.refresh(flag)
    return FeatureFlagResponse.model_validate(flag)


@router.get("", response_model=PaginatedResponse[FeatureFlagList])
async def list_feature_flags(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.FEATURES_READ)),
) -> PaginatedResponse[FeatureFlagList]:
    """Liste tous les feature flags avec pagination (admin only)."""
    service = FeatureFlagService(db)
    flags, total = await service.list_flags(
        skip=pagination.skip,
        limit=pagination.limit,
    )

    return PaginatedResponse(
        items=[FeatureFlagList.model_validate(f) for f in flags],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/check/{flag_name}", response_model=FeatureFlagEvaluated)
async def check_feature_flag(
    flag_name: str,
    tenant_id: int = Query(..., gt=0, description="ID du tenant a evaluer"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.FEATURES_READ)),
) -> FeatureFlagEvaluated:
    """Evalue si un feature flag est actif pour un tenant donne (admin only).

    Logique d'evaluation:
        1. is_enabled=False -> kill_switch
        2. target_tenants whitelist
        3. rollout_pct avec hash deterministe
    """
    service = FeatureFlagService(db)
    enabled, reason = await service.is_feature_enabled(flag_name, tenant_id)
    return FeatureFlagEvaluated(
        name=flag_name,
        enabled=enabled,
        reason=reason,
    )


@router.get("/{flag_id}", response_model=FeatureFlagResponse)
async def get_feature_flag(
    flag_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.FEATURES_READ)),
) -> FeatureFlagResponse:
    """Recupere les details d'un feature flag (admin only)."""
    service = FeatureFlagService(db)
    flag = await service.get_flag(flag_id)
    return FeatureFlagResponse.model_validate(flag)


@router.patch("/{flag_id}", response_model=FeatureFlagResponse)
async def update_feature_flag(
    flag_id: int,
    data: FeatureFlagUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.FEATURES_WRITE)),
) -> FeatureFlagResponse:
    """Met a jour un feature flag (admin only)."""
    service = FeatureFlagService(db)
    flag = await service.update_flag(flag_id, data)
    await db.commit()
    await db.refresh(flag)
    return FeatureFlagResponse.model_validate(flag)


@router.delete("/{flag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature_flag(
    flag_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.FEATURES_DELETE)),
) -> None:
    """Supprime un feature flag (hard delete, admin only)."""
    service = FeatureFlagService(db)
    await service.delete_flag(flag_id)
    await db.commit()
