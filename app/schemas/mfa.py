"""Schemas Pydantic pour les endpoints MFA TOTP."""
from typing import Optional
from pydantic import Field
from app.schemas.base import BaseSchema


class MFASetupResponse(BaseSchema):
    """Réponse du setup MFA — contient le secret et l'URI QR code."""

    secret: str = Field(
        ...,
        description="Secret TOTP en base32 (à afficher en texte pour saisie manuelle)"
    )

    provisioning_uri: str = Field(
        ...,
        description="URI otpauth:// pour QR code (apps authenticator)"
    )

    recovery_codes: list[str] = Field(
        ...,
        description="Codes de récupération à stocker en sécurité (usage unique)"
    )


class MFAVerifySetupRequest(BaseSchema):
    """Requête pour valider le setup MFA (premier code TOTP)."""

    totp_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="Code TOTP à 6 chiffres depuis l'app authenticator"
    )


class MFAVerifyRequest(BaseSchema):
    """Requête pour vérifier un code MFA lors du login (step 2)."""

    mfa_session_token: str = Field(
        ...,
        min_length=10,
        description="Token de session MFA reçu après le login password"
    )

    totp_code: Optional[str] = Field(
        default=None,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="Code TOTP à 6 chiffres (mutuellement exclusif avec recovery_code)"
    )

    recovery_code: Optional[str] = Field(
        default=None,
        min_length=4,
        description="Code de récupération (mutuellement exclusif avec totp_code)"
    )


class MFAVerifySetupResponse(BaseSchema):
    """Réponse après validation du setup MFA."""

    enabled: bool = Field(
        default=True,
        description="MFA activé avec succès"
    )

    message: str = Field(
        default="MFA enabled successfully",
        description="Message de confirmation"
    )


class MFAStatusResponse(BaseSchema):
    """Réponse pour le statut MFA d'un utilisateur."""

    mfa_enabled: bool = Field(
        ...,
        description="True si MFA est activé"
    )

    recovery_codes_remaining: int = Field(
        default=0,
        description="Nombre de codes de récupération restants"
    )


class MFADisableResponse(BaseSchema):
    """Réponse après désactivation du MFA."""

    disabled: bool = Field(
        default=True,
        description="MFA désactivé avec succès"
    )

    message: str = Field(
        default="MFA disabled successfully",
        description="Message de confirmation"
    )


class MFARegenerateCodesRequest(BaseSchema):
    """Requête pour régénérer les codes de récupération MFA."""

    totp_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="Code TOTP à 6 chiffres pour prouver l'identité"
    )


class MFARegenerateCodesResponse(BaseSchema):
    """Réponse avec les nouveaux codes de récupération."""

    recovery_codes: list[str] = Field(
        ...,
        description="Nouveaux codes de récupération (usage unique)"
    )

    message: str = Field(
        default="Recovery codes regenerated successfully",
        description="Message de confirmation"
    )


class MFALoginResponse(BaseSchema):
    """Réponse login quand MFA est requis (step 1 → step 2).

    Retourné à la place de TokenResponse quand l'utilisateur a MFA activé.
    Le client doit ensuite appeler POST /mfa/verify avec le mfa_session_token.
    """

    mfa_required: bool = Field(
        default=True,
        description="Indique que MFA est requis pour compléter le login"
    )

    mfa_session_token: str = Field(
        ...,
        description="Token temporaire (5 min) pour /mfa/verify"
    )

    token_type: str = Field(
        default="mfa_session",
        description="Type de token (toujours 'mfa_session')"
    )
