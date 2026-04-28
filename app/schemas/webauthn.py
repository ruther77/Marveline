"""Schemas Pydantic pour WebAuthn/FIDO2 (M-03)."""
import base64
from datetime import datetime
from pydantic import BaseModel, Field


class WebAuthnRegisterRequest(BaseModel):
    """Donnees d'enregistrement d'un credential WebAuthn."""
    device_name: str = Field(default="Security Key", max_length=100)


class WebAuthnRegisterOptions(BaseModel):
    """Options pour le ceremony d'enregistrement (envoyees au client)."""
    challenge: str
    rp_id: str
    rp_name: str
    user_id: str
    user_name: str
    user_display_name: str
    timeout: int = 60000
    attestation: str = "none"
    authenticator_selection: dict = Field(default_factory=lambda: {
        "authenticatorAttachment": "cross-platform",
        "residentKey": "preferred",
        "userVerification": "preferred",
    })


class WebAuthnRegisterResponse(BaseModel):
    """Reponse du client apres enregistrement (attestation)."""
    credential_id: str  # base64url
    client_data_json: str  # base64url
    attestation_object: str  # base64url
    device_name: str = "Security Key"


class WebAuthnAuthenticateOptions(BaseModel):
    """Options pour le ceremony d'authentification."""
    challenge: str
    rp_id: str
    timeout: int = 60000
    user_verification: str = "preferred"
    allow_credentials: list[dict] = Field(default_factory=list)


class WebAuthnAuthenticateResponse(BaseModel):
    """Reponse du client apres authentification (assertion)."""
    credential_id: str  # base64url
    client_data_json: str  # base64url
    authenticator_data: str  # base64url
    signature: str  # base64url


class WebAuthnCredentialInfo(BaseModel):
    """Info publique d'un credential (pour listing)."""
    id: int
    device_name: str
    created_at: datetime
    last_used_at: datetime | None
    aaguid: str | None
