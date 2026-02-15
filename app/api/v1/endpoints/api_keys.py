"""Endpoints CRUD pour les API Keys (authentification M2M)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.permissions import Permission
from app.models.user import User
from app.services.api_key import ApiKeyService
from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyList,
    ApiKeyResponse,
    ApiKeyUpdate,
)
from app.schemas.common import PaginatedResponse, PaginationParams

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    data: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.API_KEYS_WRITE)),
) -> ApiKeyCreated:
    """Cree une nouvelle API key pour le tenant.

    Le full_key n'est retourne QU'UNE SEULE FOIS dans cette reponse.
    """
    service = ApiKeyService(db)
    api_key, full_key = service.create_key(
        data=data,
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
    )
    db.commit()
    db.refresh(api_key)

    response_data = ApiKeyResponse.model_validate(api_key).model_dump()
    response_data["full_key"] = full_key
    return ApiKeyCreated(**response_data)


@router.get("", response_model=PaginatedResponse[ApiKeyList])
def list_api_keys(
    pagination: PaginationParams = Depends(),
    include_inactive: bool = Query(False, description="Inclure les cles revoquees"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.API_KEYS_READ)),
) -> PaginatedResponse[ApiKeyList]:
    """Liste les API keys du tenant avec pagination."""
    service = ApiKeyService(db)
    keys, total = service.list_keys(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        include_inactive=include_inactive,
    )

    return PaginatedResponse(
        items=[ApiKeyList.model_validate(k) for k in keys],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{api_key_id}", response_model=ApiKeyResponse)
def get_api_key(
    api_key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.API_KEYS_READ)),
) -> ApiKeyResponse:
    """Recupere les details d'une API key."""
    service = ApiKeyService(db)
    api_key = service.get_key(api_key_id, current_user.tenant_id)
    return ApiKeyResponse.model_validate(api_key)


@router.patch("/{api_key_id}", response_model=ApiKeyResponse)
def update_api_key(
    api_key_id: int,
    data: ApiKeyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.API_KEYS_WRITE)),
) -> ApiKeyResponse:
    """Met a jour une API key (name, scopes, rate_limit, is_active)."""
    service = ApiKeyService(db)
    api_key = service.update_key(api_key_id, data, current_user.tenant_id)
    db.commit()
    db.refresh(api_key)
    return ApiKeyResponse.model_validate(api_key)


@router.delete("/{api_key_id}", response_model=ApiKeyResponse)
def revoke_api_key(
    api_key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.API_KEYS_DELETE)),
) -> ApiKeyResponse:
    """Revoque (soft delete) une API key."""
    service = ApiKeyService(db)
    api_key = service.revoke_key(api_key_id, current_user.tenant_id)
    db.commit()
    db.refresh(api_key)
    return ApiKeyResponse.model_validate(api_key)


@router.post("/{api_key_id}/rotate", response_model=ApiKeyCreated)
def rotate_api_key(
    api_key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.API_KEYS_WRITE)),
) -> ApiKeyCreated:
    """Rotation : genere une nouvelle cle, revoque l'ancienne.

    Le nouveau full_key n'est retourne QU'UNE SEULE FOIS dans cette reponse.
    """
    service = ApiKeyService(db)
    new_key, full_key = service.rotate_key(api_key_id, current_user.tenant_id)
    db.commit()
    db.refresh(new_key)

    response_data = ApiKeyResponse.model_validate(new_key).model_dump()
    response_data["full_key"] = full_key
    return ApiKeyCreated(**response_data)
