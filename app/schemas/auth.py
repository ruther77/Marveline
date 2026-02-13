"""Schemas Pydantic pour l'authentification JWT."""
from typing import Literal
from pydantic import EmailStr, Field
from app.schemas.base import BaseSchema
from app.constants import Limits, UserRole


class LoginRequest(BaseSchema):
    """Schema pour requête de login.

    Note:
        - Utilise OAuth2PasswordRequestForm côté endpoint
        - Ce schema est pour documentation uniquement

    Example:
        POST /auth/login
        Content-Type: application/x-www-form-urlencoded

        username=user@example.com&password=secretpass123
    """

    username: EmailStr = Field(
        ...,
        description="Email de l'utilisateur (OAuth2 appelle ça username)"
    )

    password: str = Field(
        ...,
        min_length=Limits.PASSWORD_MIN_LENGTH,
        max_length=100,
        description="Mot de passe en clair"
    )


class TokenResponse(BaseSchema):
    """Schema pour réponse de login avec tokens JWT.

    Example:
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "expires_in": 1800
        }
    """

    access_token: str = Field(
        ...,
        description="JWT access token (courte durée: 30 min)"
    )

    refresh_token: str = Field(
        ...,
        description="JWT refresh token (longue durée: 7 jours)"
    )

    token_type: Literal["bearer"] = Field(
        default="bearer",
        description="Type de token (toujours 'bearer')"
    )

    expires_in: int = Field(
        ...,
        description="Durée de validité de l'access token en secondes"
    )


class RefreshTokenRequest(BaseSchema):
    """Schema pour requête de refresh token.

    Example:
        POST /auth/refresh
        {
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }
    """

    refresh_token: str = Field(
        ...,
        min_length=20,
        description="Refresh token JWT reçu lors du login"
    )


class UserInfo(BaseSchema):
    """Schema pour informations utilisateur (dans claims JWT).

    Example:
        {
            "id": 1,
            "email": "user@example.com",
            "full_name": "Jean Dupont",
            "role": "manager",
            "tenant_id": 1
        }
    """

    id: int = Field(
        ...,
        gt=0,
        description="ID de l'utilisateur"
    )

    email: EmailStr = Field(
        ...,
        description="Email de l'utilisateur"
    )

    full_name: str = Field(
        ...,
        description="Nom complet de l'utilisateur"
    )

    role: UserRole = Field(
        ...,
        description="Rôle RBAC de l'utilisateur"
    )

    tenant_id: int = Field(
        ...,
        gt=0,
        description="ID du tenant de l'utilisateur"
    )

    is_active: bool = Field(
        default=True,
        description="Compte actif"
    )


class ChangePasswordRequest(BaseSchema):
    """Schema pour changement de mot de passe.

    Example:
        POST /auth/change-password
        {
            "current_password": "oldpass123",
            "new_password": "newpass456"
        }
    """

    current_password: str = Field(
        ...,
        min_length=Limits.PASSWORD_MIN_LENGTH,
        max_length=100,
        description="Mot de passe actuel"
    )

    new_password: str = Field(
        ...,
        min_length=Limits.PASSWORD_MIN_LENGTH,
        max_length=100,
        description="Nouveau mot de passe"
    )


class CSRFTokenResponse(BaseSchema):
    """Schema pour réponse de génération de token CSRF.

    Example:
        GET /auth/csrf
        Response:
        {
            "csrf_token": "abc123xyz789...",
            "expires_in": 900
        }
    """

    csrf_token: str = Field(
        ...,
        min_length=32,
        description="Token CSRF unique pour cet utilisateur"
    )

    expires_in: int = Field(
        default=900,
        description="Durée de validité en secondes (15 minutes)"
    )
