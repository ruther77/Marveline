"""Schemas Pydantic pour l'authentification JWT."""
from typing import Literal
from pydantic import EmailStr, Field
from app.schemas.base import BaseSchema
from app.constants import Limits, SessionConfig, UserRole


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

    Note:
        Le refresh_token N'est PAS inclus dans ce JSON.
        Il est transmis via un cookie httpOnly (Set-Cookie: refresh_token=...).
        Voir POST /auth/login et POST /auth/refresh.

    Example:
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "expires_in": 1800
        }
    """

    access_token: str = Field(
        ...,
        description="JWT access token (courte durée: 30 min)"
    )

    token_type: Literal["bearer"] = Field(
        default="bearer",
        description="Type de token (toujours 'bearer')"
    )

    expires_in: int = Field(
        ...,
        description="Durée de validité de l'access token en secondes"
    )

    password_change_required: bool = Field(
        default=False,
        description="Si True, le client doit rediriger vers /change-password avant toute autre action"
    )


class RefreshTokenRequest(BaseSchema):
    """Schema pour requête de refresh token.

    Note:
        Le refresh_token est lu depuis le cookie httpOnly (pas du body).
        Ce schema est conservé pour compatibilité des imports.

    Example:
        POST /auth/refresh
        Cookie: refresh_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    """


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

    permissions: list[str] = Field(
        default_factory=list,
        description="Liste des permissions effectives (resource:action)"
    )

    created_at: str | None = Field(
        default=None,
        description="Date de création du compte"
    )

    password_change_required: bool = Field(
        default=False,
        description="Si True, le mot de passe doit être changé (HIBP breach ou décision admin)"
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


class ForgotPasswordRequest(BaseSchema):
    """Schema pour demande de réinitialisation de mot de passe.

    Example:
        POST /auth/forgot-password
        {
            "email": "user@example.com"
        }
    """

    email: EmailStr = Field(
        ...,
        description="Email associé au compte"
    )


class ForgotPasswordResponse(BaseSchema):
    """Réponse pour forgot-password (toujours 200 — anti-énumération)."""

    message: str = Field(
        default="If this email is registered, a password reset link has been sent.",
        description="Message de confirmation (identique que l'email existe ou non)"
    )


class ResetPasswordRequest(BaseSchema):
    """Schema pour réinitialisation effective du mot de passe.

    Example:
        POST /auth/reset-password
        {
            "token": "abc123...",
            "new_password": "newSecurePass456"
        }
    """

    token: str = Field(
        ...,
        min_length=20,
        description="Token de réinitialisation reçu par email"
    )

    new_password: str = Field(
        ...,
        min_length=Limits.PASSWORD_MIN_LENGTH,
        max_length=100,
        description="Nouveau mot de passe"
    )


class ResetPasswordResponse(BaseSchema):
    """Réponse après réinitialisation réussie du mot de passe."""

    message: str = Field(
        default="Password has been reset successfully.",
        description="Message de confirmation"
    )


class LogoutRequest(BaseSchema):
    """Schema pour requête de logout.

    Example:
        POST /auth/logout
        {
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }
    """

    refresh_token: str = Field(
        default=None,
        min_length=20,
        description="Refresh token JWT à révoquer (optionnel mais recommandé)"
    )


class LogoutResponse(BaseSchema):
    """Schema pour réponse de logout.

    Example:
        {
            "message": "Logged out successfully",
            "tokens_revoked": true
        }
    """

    message: str = Field(
        default="Logged out successfully",
        description="Message de confirmation"
    )

    tokens_revoked: bool = Field(
        default=True,
        description="True si les tokens ont été révoqués avec succès"
    )


class LoginBruteForceDetail(BaseSchema):
    """Détails brute force inclus dans la réponse 401 quand l'escalation est active.

    Retourné dans ``detail`` de la réponse 401 à partir de 3 tentatives échouées.
    Sous 3 tentatives, ``detail`` reste une chaîne simple.

    Example (≥ 3 tentatives échouées):
        {
            "detail": {
                "message": "Invalid email or password",
                "captcha_required": true,
                "delay_seconds": 0,
                "attempts": 3
            }
        }
    """

    message: str = Field(description="Message d'erreur")
    captcha_required: bool = Field(default=False, description="True si un CAPTCHA doit être présenté")
    delay_seconds: int = Field(default=0, description="Délai imposé avant la prochaine tentative")
    attempts: int = Field(default=0, description="Nombre de tentatives échouées dans la fenêtre")


class LoginV2Request(BaseSchema):
    """Requête de login IAM v2 (JSON body avec tenant_id explicite).

    Contrairement à v1 (form-encoded OAuth2), v2 accepte JSON.
    tenant_id est obligatoire : multi-tenant, pas d'auto-résolution.
    """

    email: EmailStr = Field(..., description="Email du compte global")
    password: str = Field(..., min_length=Limits.PASSWORD_MIN_LENGTH, max_length=100)
    tenant_id: int = Field(..., gt=0, description="ID du tenant dans lequel se connecter")


class AccountInfo(BaseSchema):
    """Informations du compte IAM v2 pour GET /auth/v2/me.

    Retourne les données de l'Account global + du TenantMembership actif.
    """

    account_id: int = Field(..., gt=0, description="ID global du compte")
    email: EmailStr
    first_name: str
    last_name: str
    tenant_id: int = Field(..., gt=0)
    membership_id: int = Field(..., gt=0)
    role_name: str = Field(..., description="Rôle RBAC dans ce tenant")
    is_active: bool = True
    password_change_required: bool = False
    scopes: list[str] = Field(default_factory=list, description="Scopes RBAC effectifs")


class CSRFTokenResponse(BaseSchema):
    """Schema pour réponse de génération de token CSRF.

    Example:
        GET /auth/csrf
        Response:
        {
            "csrf_token": "abc123xyz789...",
            "expires_in": 604800
        }
    """

    csrf_token: str = Field(
        ...,
        min_length=32,
        description="Token CSRF unique pour cet utilisateur"
    )

    expires_in: int = Field(
        default=SessionConfig.SESSION_TTL_SECONDS,
        description="Durée de validité en secondes (aligné sur la session)"
    )
