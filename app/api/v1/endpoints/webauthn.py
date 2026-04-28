"""Endpoints WebAuthn/FIDO2 — registration + authentication (M-03)."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user_async, UserCompat
from app.schemas.webauthn import (
    WebAuthnRegisterRequest,
    WebAuthnRegisterResponse,
    WebAuthnAuthenticateResponse,
    WebAuthnCredentialInfo,
)
from app.services.webauthn import WebAuthnService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webauthn", tags=["WebAuthn"])


@router.post("/register/options")
async def get_register_options(
    body: WebAuthnRegisterRequest,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Genere les options pour enregistrer un nouveau credential WebAuthn."""
    svc = WebAuthnService(db)
    return await svc.generate_registration_options(
        account_id=current_user.id,
        email=current_user.email,
        device_name=body.device_name,
    )


@router.post("/register/verify")
async def verify_register(
    body: WebAuthnRegisterResponse,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Verifie l'attestation et enregistre le credential."""
    svc = WebAuthnService(db)
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
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Genere les options pour authentification WebAuthn (step-up MFA)."""
    svc = WebAuthnService(db)
    return await svc.generate_authentication_options(current_user.id)


@router.post("/authenticate/verify")
async def verify_authenticate(
    body: WebAuthnAuthenticateResponse,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Verifie l'assertion WebAuthn (step-up MFA)."""
    svc = WebAuthnService(db)
    await svc.verify_authentication(
        account_id=current_user.id,
        credential_id_b64=body.credential_id,
        client_data_json_b64=body.client_data_json,
        authenticator_data_b64=body.authenticator_data,
        signature_b64=body.signature,
    )
    await db.commit()

    # Ecrire step-up token (meme pattern que TOTP)
    from app.core.redis import redis_sec
    from app.constants.security import MFAConfig
    device_id = getattr(current_user, '_device_id', '') or ''
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
