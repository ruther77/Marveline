"""Endpoints pour gestion des utilisateurs."""
import logging
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import (
    get_current_user_async,
    require_stepup,
    UserCompat,
    UserReaderScope,
    UserWriterScope,
    UserManagerScope,
    UserDeleterScope,
)
from app.core.redis import redis_client
from app.services.audit import AuditService
from app.services.user import UserService
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.user import (
    UserProfileUpdate,
    UserProfileResponse,
    UserCreate,
    UserUpdate,
    UserInviteRequest,
    UserInviteResponse,
)
from app.constants import ErrorMessages, RedisKeys

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/users", tags=["Users"])


def _user_to_response(user: UserCompat) -> UserProfileResponse:
    """Convertit un User ORM en UserProfileResponse."""
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        role=user.role,
        tenant_id=user.tenant_id,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


# ── Self-service endpoints (/me) ──────────────────────────────────────
# IMPORTANT: /me routes AVANT /{user_id} pour éviter collision path


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: UserCompat = Depends(get_current_user_async),
) -> UserProfileResponse:
    """Récupère le profil de l'utilisateur authentifié."""
    return _user_to_response(current_user)


@router.patch("/me", response_model=UserProfileResponse)
async def update_my_profile(
    data: UserProfileUpdate,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> UserProfileResponse:
    """Met à jour le profil de l'utilisateur authentifié.

    Raises:
        HTTPException 400: Si email déjà utilisé ou password invalide
    """
    user_service = UserService(db)
    updated_user = await user_service.update_profile(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        data=data,
    )
    return _user_to_response(updated_user)


# ── Admin CRUD endpoints ──────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[UserProfileResponse])
async def list_users(
    current_user: UserReaderScope,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    include_inactive: bool = Query(default=False, description="Inclure les comptes désactivés"),
) -> PaginatedResponse[UserProfileResponse]:
    """Liste les utilisateurs du tenant (admin: USERS_READ)."""
    user_service = UserService(db)
    items, total = await user_service.list_users(
        tenant_id=current_user.tenant_id,
        skip=pagination.skip,
        limit=pagination.limit,
        include_inactive=include_inactive,
    )
    return PaginatedResponse[UserProfileResponse](
        items=[_user_to_response(u) for u in items],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.post("/invite", response_model=UserInviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    data: UserInviteRequest,
    current_user: UserManagerScope,
    db: AsyncSession = Depends(get_async_db),
) -> UserInviteResponse:
    """Invite un utilisateur par email (admin: USERS_ADMIN).

    Crée le compte avec un mot de passe temporaire et envoie un email
    d'invitation contenant un lien de réinitialisation de mot de passe.

    Raises:
        HTTPException 409: Si email déjà utilisé dans le tenant
    """
    user_service = UserService(db)
    user, invite_sent = await user_service.invite_user(
        admin_user=current_user,
        data=data,
    )
    return UserInviteResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        invite_sent=invite_sent,
    )


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user(
    user_id: int,
    current_user: UserReaderScope,
    db: AsyncSession = Depends(get_async_db),
) -> UserProfileResponse:
    """Récupère un utilisateur par ID (admin: USERS_READ).

    Raises:
        HTTPException 404: Si utilisateur inexistant ou autre tenant
    """
    user_service = UserService(db)
    user = await user_service.get_user(
        tenant_id=current_user.tenant_id,
        user_id=user_id,
    )
    return _user_to_response(user)


@router.post("", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    current_user: UserWriterScope,
    db: AsyncSession = Depends(get_async_db),
) -> UserProfileResponse:
    """Crée un utilisateur dans le tenant (admin: USERS_ADMIN).

    Raises:
        HTTPException 400: Si email déjà utilisé ou password faible
    """
    user_service = UserService(db)
    user = await user_service.create_user(
        admin_user=current_user,
        data=data,
    )
    return _user_to_response(user)


@router.patch("/{user_id}", response_model=UserProfileResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: UserWriterScope,
    db: AsyncSession = Depends(get_async_db),
) -> UserProfileResponse:
    """Met à jour un utilisateur (manager+: USERS_WRITE).

    Raises:
        HTTPException 400: Si email déjà utilisé
        HTTPException 403: Si auto-promotion admin
        HTTPException 404: Si utilisateur inexistant
    """
    user_service = UserService(db)
    user = await user_service.update_user(
        admin_user=current_user,
        user_id=user_id,
        data=data,
    )
    return _user_to_response(user)


@router.delete("/{user_id}", response_model=UserProfileResponse)
async def delete_user(
    user_id: int,
    current_user: UserDeleterScope,
    db: AsyncSession = Depends(get_async_db),
) -> UserProfileResponse:
    """Désactive un utilisateur — soft delete (admin: USERS_ADMIN).

    Raises:
        HTTPException 403: Si tentative d'auto-suppression
        HTTPException 404: Si utilisateur inexistant
    """
    user_service = UserService(db)
    user = await user_service.deactivate_user(
        admin_user=current_user,
        user_id=user_id,
    )
    return _user_to_response(user)


@router.post("/{user_id}/unlock", status_code=status.HTTP_200_OK)
async def unlock_user(
    user_id: int,
    request: Request,
    current_user: UserManagerScope,
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_stepup),
):
    """Débloque un compte verrouillé par brute force (users:manage + step-up §4.6 S-09.4).

    Supprime le compteur brute force `brute:{uid}` dans Redis-SEC.
    Isolation tenant : seuls les utilisateurs du même tenant sont accessibles.

    Raises:
        HTTPException 403: Si step-up MFA non valide
        HTTPException 404: Si utilisateur inexistant ou autre tenant
    """
    # Vérifie existence + isolation tenant (lève 404 si autre tenant)
    user_service = UserService(db)
    target_user = await user_service.get_user(
        tenant_id=current_user.tenant_id,
        user_id=user_id,
    )

    # Supprimer compteur brute force utilisateur (§4.6)
    brute_key = RedisKeys.brute_force_user(user_id)
    redis_client.reset_brute_force(brute_key)

    # Audit log ADMIN_ACCOUNT_UNLOCK
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    audit_service = AuditService(db)
    await audit_service.log_action(
        action="ADMIN_ACCOUNT_UNLOCK",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="User",
        entity_id=target_user.id,
        description=f"Brute force counter cleared for user {user_id}",
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
    await db.commit()

    return {"status": "unlocked", "user_id": user_id}
