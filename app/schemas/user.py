"""Schemas Pydantic pour la gestion des utilisateurs."""
from typing import Optional
from pydantic import EmailStr, Field, field_validator
from app.schemas.base import BaseSchema
from app.constants import Limits, UserRole
from app.core.validators import validate_text_safe


# ── Admin CRUD schemas ────────────────────────────────────────────────


class UserCreate(BaseSchema):
    """Schema pour création d'utilisateur par un admin.

    Security:
        - Email normalisé en lowercase
        - Password doit respecter la password policy
        - Role limité aux valeurs valides (staff, manager, admin)
        - Validation XSS/SQL injection sur noms
    """

    email: EmailStr = Field(..., description="Email de l'utilisateur")
    password: str = Field(
        ...,
        min_length=Limits.PASSWORD_MIN_LENGTH,
        max_length=100,
        description="Mot de passe initial",
    )
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Prénom",
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nom de famille",
    )
    role: UserRole = Field(
        default=UserRole.STAFF,
        description="Rôle RBAC (staff, manager, admin)",
    )
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Adresse postale",
    )
    postal_code: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Code postal",
    )

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: str) -> str:
        """Valide les noms contre XSS/SQL injection."""
        return validate_text_safe(value)


class UserUpdate(BaseSchema):
    """Schema pour mise à jour d'utilisateur par un admin (PATCH partiel).

    Security:
        - Tous les champs optionnels
        - Role modification soumise à vérification (pas d'auto-promotion)
        - Validation XSS/SQL injection sur noms
    """

    email: Optional[EmailStr] = Field(
        default=None,
        description="Nouvel email (unique par tenant)",
    )
    first_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nouveau prénom",
    )
    last_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nouveau nom de famille",
    )
    role: Optional[UserRole] = Field(
        default=None,
        description="Nouveau rôle RBAC",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Activer/désactiver le compte",
    )
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Adresse postale",
    )
    postal_code: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Code postal",
    )

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: Optional[str]) -> Optional[str]:
        """Valide les noms contre XSS/SQL injection."""
        if value is None:
            return value
        return validate_text_safe(value)


class UserListResponse(BaseSchema):
    """Schema pour liste paginée d'utilisateurs."""

    items: list["UserProfileResponse"] = Field(
        ..., description="Liste des utilisateurs"
    )
    total: int = Field(..., ge=0, description="Nombre total d'utilisateurs")
    skip: int = Field(..., ge=0, description="Offset de pagination")
    limit: int = Field(..., gt=0, description="Limite de pagination")


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
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Adresse postale"
    )
    postal_code: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Code postal"
    )

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: Optional[str]) -> Optional[str]:
        """Valide les noms contre XSS/SQL injection."""
        if value is None:
            return value
        return validate_text_safe(value)


class UserInviteRequest(BaseSchema):
    """Schema pour invitation d'un utilisateur par email."""

    email: EmailStr = Field(..., description="Email de l'utilisateur invité")
    role: UserRole = Field(
        default=UserRole.STAFF,
        description="Rôle RBAC attribué à l'invitation",
    )
    first_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Prénom (optionnel)",
    )
    last_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nom de famille (optionnel)",
    )


class UserInviteResponse(BaseSchema):
    """Schema pour réponse d'invitation utilisateur."""

    id: int = Field(..., gt=0, description="ID de l'utilisateur créé")
    email: EmailStr = Field(..., description="Email de l'utilisateur")
    role: UserRole = Field(..., description="Rôle attribué")
    invite_sent: bool = Field(..., description="Email d'invitation envoyé")


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
    address: Optional[str] = Field(default=None, description="Adresse postale")
    postal_code: Optional[str] = Field(default=None, description="Code postal")
    created_at: str = Field(..., description="Date création")
    updated_at: str = Field(..., description="Date dernière mise à jour")
