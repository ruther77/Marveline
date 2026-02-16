"""Endpoints pour gestion des utilisateurs."""
import logging
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, UserReader, UserWriter, UserAdmin
from app.models.user import User
from app.services.user import UserService
from app.schemas.user import (
    UserProfileUpdate,
    UserProfileResponse,
    UserCreate,
    UserUpdate,
    UserListResponse,
)

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/users", tags=["Users"])


def _user_to_response(user: User) -> UserProfileResponse:
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
def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """Récupère le profil de l'utilisateur authentifié."""
    return _user_to_response(current_user)


@router.patch("/me", response_model=UserProfileResponse)
def update_my_profile(
    data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """Met à jour le profil de l'utilisateur authentifié.

    Raises:
        HTTPException 400: Si email déjà utilisé ou password invalide
    """
    user_service = UserService(db)
    updated_user = user_service.update_profile(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        data=data,
    )
    return _user_to_response(updated_user)


# ── Admin CRUD endpoints ──────────────────────────────────────────────


@router.get("", response_model=UserListResponse)
def list_users(
    current_user: UserReader,
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0, description="Offset de pagination"),
    limit: int = Query(default=50, ge=1, le=200, description="Limite de pagination"),
    include_inactive: bool = Query(default=False, description="Inclure les comptes désactivés"),
) -> UserListResponse:
    """Liste les utilisateurs du tenant (admin: USERS_READ).

    Returns:
        Liste paginée des utilisateurs
    """
    user_service = UserService(db)
    items, total = user_service.list_users(
        tenant_id=current_user.tenant_id,
        skip=skip,
        limit=limit,
        include_inactive=include_inactive,
    )
    return UserListResponse(
        items=[_user_to_response(u) for u in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{user_id}", response_model=UserProfileResponse)
def get_user(
    user_id: int,
    current_user: UserReader,
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """Récupère un utilisateur par ID (admin: USERS_READ).

    Raises:
        HTTPException 404: Si utilisateur inexistant ou autre tenant
    """
    user_service = UserService(db)
    user = user_service.get_user(
        tenant_id=current_user.tenant_id,
        user_id=user_id,
    )
    return _user_to_response(user)


@router.post("", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    current_user: UserAdmin,
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """Crée un utilisateur dans le tenant (admin: USERS_ADMIN).

    Raises:
        HTTPException 400: Si email déjà utilisé ou password faible
    """
    user_service = UserService(db)
    user = user_service.create_user(
        admin_user=current_user,
        data=data,
    )
    return _user_to_response(user)


@router.patch("/{user_id}", response_model=UserProfileResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: UserWriter,
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """Met à jour un utilisateur (manager+: USERS_WRITE).

    Raises:
        HTTPException 400: Si email déjà utilisé
        HTTPException 403: Si auto-promotion admin
        HTTPException 404: Si utilisateur inexistant
    """
    user_service = UserService(db)
    user = user_service.update_user(
        admin_user=current_user,
        user_id=user_id,
        data=data,
    )
    return _user_to_response(user)


@router.delete("/{user_id}", response_model=UserProfileResponse)
def delete_user(
    user_id: int,
    current_user: UserAdmin,
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """Désactive un utilisateur — soft delete (admin: USERS_ADMIN).

    Raises:
        HTTPException 403: Si tentative d'auto-suppression
        HTTPException 404: Si utilisateur inexistant
    """
    user_service = UserService(db)
    user = user_service.deactivate_user(
        admin_user=current_user,
        user_id=user_id,
    )
    return _user_to_response(user)
