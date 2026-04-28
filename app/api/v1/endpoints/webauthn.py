"""Endpoints WebAuthn/FIDO2 — registration + authentication (M-03).

S1.T11 (F368) — RP_ID + expected_origin lus per-tenant via `request.state.tenant`
(injecte par `RequestContextMiddleware`). Fallback settings.* si tenant inconnu.

S1.T8 (F370) — device_id pour la cle stepup extrait du claim `did` du JWT
(meme pattern que `app/core/deps.py:require_stepup` et
`app/api/v1/endpoints/mfa.py:verify_mfa_stepup`).
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user_async, UserCompat
from app.core.security import decode_token
from app.schemas.webauthn import (
    WebAuthnRegisterRequest,
    WebAuthnRegisterResponse,
    WebAuthnAuthenticateResponse,
    WebAuthnCredentialInfo,
)
from app.services.webauthn import WebAuthnService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webauthn", tags=["WebAuthn"])


def _extract_did_from_request(request: Request) -> str:
    """Extrait le claim `did` du JWT Bearer pour la cle stepup Redis (S1.T8).

    Doit matcher exactement la logique du guard `require_stepup` (deps.py)
    et de `verify_mfa_stepup` (mfa.py) : meme write, meme read.

    Returns:
        device_id (claim `did`) ou "" si pas de JWT / token invalide.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return ""
    try:
        tok = decode_token(auth_header[len("Bearer "):])
        return tok.get("did", "") if tok else ""
    except Exception:
        return ""


@router.post("/register/options")
async def get_register_options(
    body: WebAuthnRegisterRequest,
    request: Request,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Genere les options pour enregistrer un nouveau credential WebAuthn."""
    tenant = getattr(request.state, "tenant", None)
    svc = WebAuthnService(db, tenant)
    return await svc.generate_registration_options(
        account_id=current_user.id,
        email=current_user.email,
        device_name=body.device_name,
    )


@router.post("/register/verify")
async def verify_register(
    body: WebAuthnRegisterResponse,
    request: Request,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Verifie l'attestation et enregistre le credential."""
    tenant = getattr(request.state, "tenant", None)
    svc = WebAuthnService(db, tenant)
    cred = await svc.verify_registration(
        account_id=current_user.id,
        credential_id_b64=body.credential_id,
        client_data_json_b64=body.client_data_json,
        attestation_object_b64=body.attestation_object,
        device_name=body.device_name,
    )
    await db.commit()
    return {"id": cred.id, "device_name": cred.device_name, "status": "registered"}


@router.post("/authenticate/options")
async def get_authenticate_options(
    request: Request,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Genere les options pour authentification WebAuthn (step-up MFA)."""
    tenant = getattr(request.state, "tenant", None)
    svc = WebAuthnService(db, tenant)
    return await svc.generate_authentication_options(current_user.id)


@router.post("/authenticate/verify")
async def verify_authenticate(
    body: WebAuthnAuthenticateResponse,
    request: Request,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Verifie l'assertion WebAuthn (step-up MFA)."""
    tenant = getattr(request.state, "tenant", None)
    svc = WebAuthnService(db, tenant)
    await svc.verify_authentication(
        account_id=current_user.id,
        credential_id_b64=body.credential_id,
        client_data_json_b64=body.client_data_json,
        authenticator_data_b64=body.authenticator_data,
        signature_b64=body.signature,
    )
    await db.commit()

    # S1.T8 (F370) — Ecrire step-up token avec device_id = claim 'did' du JWT.
    # Meme cle que celle lue par require_stepup (deps.py) -> matching garanti.
    from app.core.redis import redis_sec
    from app.constants.security import MFAConfig

    device_id = _extract_did_from_request(request)
    stepup_key = f"stepup:{current_user.id}:{device_id}"
    await redis_sec.client.setex(stepup_key, MFAConfig.STEPUP_TTL, "1")

    return {"verified": True, "stepup_valid_seconds": MFAConfig.STEPUP_TTL}


@router.get("/credentials", response_model=list[WebAuthnCredentialInfo])
async def list_credentials(
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> list:
    """Liste les credentials WebAuthn enregistres."""
    svc = WebAuthnService(db)
    return await svc.list_credentials(current_user.id)


@router.delete("/credentials/{credential_id}")
async def delete_credential(
    credential_id: int,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Supprime un credential WebAuthn."""
    svc = WebAuthnService(db)
    await svc.delete_credential(current_user.id, credential_id)
    await db.commit()
    return {"deleted": True}
