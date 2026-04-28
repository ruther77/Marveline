"""Endpoints CRUD pour les API Keys (authentification M2M)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
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
async def create_api_key(
    data: ApiKeyCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.API_KEYS_WRITE)),
) -> ApiKeyCreated:
    """Cree une nouvelle API key pour le tenant.

    Le full_key n'est retourne QU'UNE SEULE FOIS dans cette reponse.
    """
    service = ApiKeyService(db)
    api_key, full_key = await service.create_key(
        data=data,
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
    )
    await db.commit()
    await db.refresh(api_key)

    response_data = ApiKeyResponse.model_validate(api_key).model_dump()
    response_data["full_key"] = full_key
    return ApiKeyCreated(**response_data)


@router.get("", response_model=PaginatedResponse[ApiKeyList])
async def list_api_keys(
    pagination: PaginationParams = Depends(),
    include_inactive: bool = Query(False, description="Inclure les cles revoquees"),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.API_KEYS_READ)),
) -> PaginatedResponse[ApiKeyList]:
    """Liste les API keys du tenant avec pagination."""
    service = ApiKeyService(db)
    keys, total = await service.list_keys(
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
async def get_api_key(
    api_key_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.API_KEYS_READ)),
) -> ApiKeyResponse:
    """Recupere les details d'une API key."""
    service = ApiKeyService(db)
    api_key = await service.get_key(api_key_id, current_user.tenant_id)
    return ApiKeyResponse.model_validate(api_key)


@router.patch("/{api_key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    api_key_id: int,
    data: ApiKeyUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.API_KEYS_WRITE)),
) -> ApiKeyResponse:
    """Met a jour une API key (name, scopes, rate_limit, is_active)."""
    service = ApiKeyService(db)
    api_key = await service.update_key(api_key_id, data, current_user.tenant_id)
    await db.commit()
    await db.refresh(api_key)
    return ApiKeyResponse.model_validate(api_key)


@router.delete("/{api_key_id}", response_model=ApiKeyResponse)
async def revoke_api_key(
    api_key_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.API_KEYS_DELETE)),
) -> ApiKeyResponse:
    """Revoque (soft delete) une API key."""
    service = ApiKeyService(db)
    api_key = await service.revoke_key(api_key_id, current_user.tenant_id)
    await db.commit()
    await db.refresh(api_key)
    return ApiKeyResponse.model_validate(api_key)


@router.post("/{api_key_id}/rotate", response_model=ApiKeyCreated)
async def rotate_api_key(
    api_key_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.API_KEYS_WRITE)),
) -> ApiKeyCreated:
    """Rotation : genere une nouvelle cle, revoque l'ancienne.

    Le nouveau full_key n'est retourne QU'UNE SEULE FOIS dans cette reponse.
    """
    service = ApiKeyService(db)
    new_key, full_key = await service.rotate_key(api_key_id, current_user.tenant_id)
    await db.commit()
    await db.refresh(new_key)

    response_data = ApiKeyResponse.model_validate(new_key).model_dump()
    response_data["full_key"] = full_key
    return ApiKeyCreated(**response_data)
