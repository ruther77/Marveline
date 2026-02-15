"""Schemas Pydantic pour la gestion des utilisateurs."""
from typing import Optional
from pydantic import EmailStr, Field, field_validator
from app.schemas.base import BaseSchema
from app.constants import Limits, UserRole
from app.core.validators import validate_text_safe


class UserProfileUpdate(BaseSchema):
    """Schema pour mise à jour du profil utilisateur.

    Permet de modifier email, first_name, last_name, et optionnellement le password.
    Tous les champs sont optionnels (PATCH partiel).

    Example:
        PATCH /api/v1/users/me
        {
            "email": "newemail@example.com",
            "first_name": "Jean",
            "last_name": "Dupont"
        }

    Security:
        - Email doit être unique par tenant
        - Password doit respecter la password policy si fourni
        - Validation XSS/SQL injection sur first_name/last_name
    """

    email: Optional[EmailStr] = Field(
        default=None,
        description="Nouvel email (doit être unique dans le tenant)"
    )

    first_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nouveau prénom"
    )

    last_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nouveau nom de famille"
    )

    password: Optional[str] = Field(
        default=None,
        min_length=Limits.PASSWORD_MIN_LENGTH,
        max_length=100,
        description="Nouveau mot de passe (optionnel, doit respecter password policy)"
    )

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: Optional[str]) -> Optional[str]:
        """Valide les noms contre XSS/SQL injection."""
        if value is None:
            return value
        return validate_text_safe(value)


class UserProfileResponse(BaseSchema):
    """Schema pour réponse profil utilisateur.

    Example:
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

    id: int = Field(..., gt=0, description="ID utilisateur")
    email: EmailStr = Field(..., description="Email utilisateur")
    first_name: str = Field(..., description="Prénom")
    last_name: str = Field(..., description="Nom de famille")
    full_name: str = Field(..., description="Nom complet (computed)")
    role: UserRole = Field(..., description="Rôle RBAC")
    tenant_id: int = Field(..., gt=0, description="ID tenant")
    is_active: bool = Field(default=True, description="Compte actif")
    created_at: str = Field(..., description="Date création")
    updated_at: str = Field(..., description="Date dernière mise à jour")
