"""Endpoints pour gestion des utilisateurs."""
import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.user import UserService
from app.schemas.user import UserProfileUpdate, UserProfileResponse

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """Récupère le profil de l'utilisateur authentifié.

    Returns:
        Profil complet de l'utilisateur

    Security:
        - Authentification JWT requise
        - Retourne uniquement les données de l'utilisateur authentifié

    Example:
        GET /api/v1/users/me

        Response:
        {
            "id": 1,
            "email": "user@example.com",
            "first_name": "Jean",
            "last_name": "Dupont",
            "full_name": "Jean Dupont",
            "role": "manager",
            "tenant_id": 1,
            "is_active": true,
            "created_at": "2026-01-15T10:00:00Z",
            "updated_at": "2026-02-15T14:30:00Z"
        }
    """
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        full_name=current_user.full_name,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
        updated_at=current_user.updated_at.isoformat(),
    )


@router.patch("/me", response_model=UserProfileResponse)
def update_my_profile(
    data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """Met à jour le profil de l'utilisateur authentifié.

    Args:
        data: Données de mise à jour (tous champs optionnels)
        current_user: Utilisateur authentifié
        db: Session de base de données

    Returns:
        Profil mis à jour

    Raises:
        HTTPException 400: Si email déjà utilisé ou password invalide

    Security:
        - Authentification JWT requise
        - Email doit être unique par tenant
        - Password doit respecter la password policy
        - Validation XSS/SQL injection sur first_name/last_name

    Example:
        PATCH /api/v1/users/me
        {
            "email": "newemail@example.com",
            "first_name": "Jean",
            "last_name": "Dupont"
        }

        Response:
        {
            "id": 1,
            "email": "newemail@example.com",
            "first_name": "Jean",
            "last_name": "Dupont",
            "full_name": "Jean Dupont",
            "role": "manager",
            "tenant_id": 1,
            "is_active": true,
            "created_at": "2026-01-15T10:00:00Z",
            "updated_at": "2026-02-15T15:00:00Z"
        }
    """
    user_service = UserService(db)

    # Mettre à jour le profil
    updated_user = user_service.update_profile(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        data=data
    )

    return UserProfileResponse(
        id=updated_user.id,
        email=updated_user.email,
        first_name=updated_user.first_name,
        last_name=updated_user.last_name,
        full_name=updated_user.full_name,
        role=updated_user.role,
        tenant_id=updated_user.tenant_id,
        is_active=updated_user.is_active,
        created_at=updated_user.created_at.isoformat(),
        updated_at=updated_user.updated_at.isoformat(),
    )
