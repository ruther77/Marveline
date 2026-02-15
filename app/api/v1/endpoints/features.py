"""Endpoints CRUD pour les Feature Flags (admin uniquement)."""
import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.permissions import Permission
from app.models.user import User
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
def create_feature_flag(
    data: FeatureFlagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.FEATURES_WRITE)),
) -> FeatureFlagResponse:
    """Cree un nouveau feature flag (admin only)."""
    service = FeatureFlagService(db)
    flag = service.create_flag(data)
    db.commit()
    db.refresh(flag)
    return FeatureFlagResponse.model_validate(flag)


@router.get("", response_model=PaginatedResponse[FeatureFlagList])
def list_feature_flags(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.FEATURES_READ)),
) -> PaginatedResponse[FeatureFlagList]:
    """Liste tous les feature flags avec pagination (admin only)."""
    service = FeatureFlagService(db)
    flags, total = service.list_flags(
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
def check_feature_flag(
    flag_name: str,
    tenant_id: int = Query(..., gt=0, description="ID du tenant a evaluer"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.FEATURES_READ)),
) -> FeatureFlagEvaluated:
    """Evalue si un feature flag est actif pour un tenant donne (admin only).

    Logique d'evaluation:
        1. is_enabled=False -> kill_switch
        2. target_tenants whitelist
        3. rollout_pct avec hash deterministe
    """
    service = FeatureFlagService(db)
    enabled, reason = service.is_feature_enabled(flag_name, tenant_id)
    return FeatureFlagEvaluated(
        name=flag_name,
        enabled=enabled,
        reason=reason,
    )


@router.get("/{flag_id}", response_model=FeatureFlagResponse)
def get_feature_flag(
    flag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.FEATURES_READ)),
) -> FeatureFlagResponse:
    """Recupere les details d'un feature flag (admin only)."""
    service = FeatureFlagService(db)
    flag = service.get_flag(flag_id)
    return FeatureFlagResponse.model_validate(flag)


@router.patch("/{flag_id}", response_model=FeatureFlagResponse)
def update_feature_flag(
    flag_id: int,
    data: FeatureFlagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.FEATURES_WRITE)),
) -> FeatureFlagResponse:
    """Met a jour un feature flag (admin only)."""
    service = FeatureFlagService(db)
    flag = service.update_flag(flag_id, data)
    db.commit()
    db.refresh(flag)
    return FeatureFlagResponse.model_validate(flag)


@router.delete("/{flag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feature_flag(
    flag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.FEATURES_DELETE)),
) -> None:
    """Supprime un feature flag (hard delete, admin only)."""
    service = FeatureFlagService(db)
    service.delete_flag(flag_id)
    db.commit()
