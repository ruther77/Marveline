"""Endpoints MFA TOTP — setup, verify, disable."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import decode_token
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.mfa import (
    MFADisableResponse,
    MFASetupResponse,
    MFAStatusResponse,
    MFAVerifyRequest,
    MFAVerifySetupRequest,
    MFAVerifySetupResponse,
)
from app.services.audit import AuditService
from app.services.mfa import mfa_service
from app.services.session import session_service
from app.services.token import token_service
from app.constants import ErrorMessages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mfa", tags=["MFA"])


@router.post("/setup", response_model=MFASetupResponse, status_code=status.HTTP_200_OK)
def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MFASetupResponse:
    """Initialise le setup MFA TOTP pour l'utilisateur.

    Génère un secret TOTP, une URI de provisioning (QR code) et des codes de récupération.
    Le MFA n'est pas encore activé — il faut appeler POST /mfa/verify-setup avec un code valide.

    Returns:
        MFASetupResponse avec secret, provisioning_uri, recovery_codes
    """
    try:
        secret, provisioning_uri, recovery_codes = mfa_service.setup_totp(
            db=db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            email=current_user.email,
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.MFA_ALREADY_ENABLED if "already enabled" in str(e) else str(e),
        )

    return MFASetupResponse(
        secret=secret,
        provisioning_uri=provisioning_uri,
        recovery_codes=recovery_codes,
    )


@router.post("/verify-setup", response_model=MFAVerifySetupResponse, status_code=status.HTTP_200_OK)
def verify_setup(
    body: MFAVerifySetupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MFAVerifySetupResponse:
    """Valide le setup MFA avec un premier code TOTP.

    Active définitivement le MFA pour l'utilisateur après vérification du code.

    Returns:
        MFAVerifySetupResponse avec confirmation
    """
    try:
        mfa_service.verify_setup(
            db=db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            totp_code=body.totp_code,
        )
        db.commit()
    except ValueError as e:
        error_msg = str(e)
        if "No pending" in error_msg:
            detail = ErrorMessages.MFA_NO_PENDING_SETUP
        elif "Invalid TOTP" in error_msg:
            detail = ErrorMessages.MFA_INVALID_TOTP_CODE
        else:
            detail = error_msg
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    return MFAVerifySetupResponse(enabled=True, message="MFA enabled successfully")


@router.post("/verify", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def verify_mfa(
    body: MFAVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Vérifie le code MFA et complète l'authentification (step 2 du login).

    Cet endpoint n'utilise PAS de JWT — il consomme le mfa_session_token
    obtenu lors du login (step 1). Après vérification TOTP ou recovery code,
    émet les tokens JWT (access + refresh) et crée la session.

    Returns:
        TokenResponse avec access_token, refresh_token, expires_in
    """
    # Valider le mfa_session_token (single-use, supprimé après lecture)
    session_data = mfa_service.validate_mfa_session(body.mfa_session_token)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.MFA_SESSION_INVALID,
        )

    user_id = session_data["user_id"]
    tenant_id = session_data["tenant_id"]
    email = session_data["email"]
    role = session_data["role"]
    mfa_ip = session_data.get("ip_address", "unknown")

    # Vérifier qu'au moins un code est fourni (mais pas les deux)
    if body.totp_code and body.recovery_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.MFA_BOTH_CODES_PROVIDED,
        )

    if not body.totp_code and not body.recovery_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.MFA_MUST_PROVIDE_CODE,
        )

    # Vérifier le code TOTP ou recovery
    try:
        if body.totp_code:
            mfa_service.verify_totp(
                db=db,
                user_id=user_id,
                tenant_id=tenant_id,
                totp_code=body.totp_code,
            )
        else:
            mfa_service.verify_recovery_code(
                db=db,
                user_id=user_id,
                tenant_id=tenant_id,
                recovery_code=body.recovery_code,
            )
    except ValueError as e:
        error_msg = str(e)
        if "already used" in error_msg:
            detail = ErrorMessages.MFA_CODE_ALREADY_USED
        elif "Invalid TOTP" in error_msg:
            detail = ErrorMessages.MFA_INVALID_TOTP_CODE
        elif "Invalid recovery" in error_msg:
            detail = ErrorMessages.MFA_INVALID_RECOVERY_CODE
        elif "No recovery" in error_msg:
            detail = ErrorMessages.MFA_NO_RECOVERY_CODES
        elif "not enabled" in error_msg:
            detail = ErrorMessages.MFA_NOT_ENABLED
        else:
            detail = error_msg

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

    # ── MFA vérifié — émettre tokens JWT et créer session ──

    # Audit log LOGIN_SUCCESS (maintenant que l'authentification est complète)
    ip_address = request.client.host if request.client else mfa_ip
    user_agent = request.headers.get("User-Agent", "unknown")
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

    audit_service = AuditService(db)
    audit_service.log_login(
        user_id=user_id,
        tenant_id=tenant_id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        success=True,
        email=email,
    )
    db.commit()

    # Émettre tokens JWT
    access_token, refresh_token, expires_in = token_service.issue_tokens(
        user_id=user_id,
        tenant_id=tenant_id,
        email=email,
        role=role,
    )

    # Créer session Redis
    refresh_payload = decode_token(refresh_token)
    family_id = refresh_payload.get("family_id", "")
    session_service.create_session(
        user_id=user_id,
        tenant_id=tenant_id,
        family_id=family_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.get("/status", response_model=MFAStatusResponse, status_code=status.HTTP_200_OK)
def mfa_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MFAStatusResponse:
    """Retourne le statut MFA de l'utilisateur connecté.

    Returns:
        MFAStatusResponse avec mfa_enabled et recovery_codes_remaining
    """
    enabled = mfa_service.is_mfa_enabled(db, current_user.id, current_user.tenant_id)
    remaining = mfa_service.get_recovery_codes_count(db, current_user.id, current_user.tenant_id)

    return MFAStatusResponse(
        mfa_enabled=enabled,
        recovery_codes_remaining=remaining,
    )


@router.delete("", response_model=MFADisableResponse, status_code=status.HTTP_200_OK)
def disable_mfa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MFADisableResponse:
    """Désactive le MFA pour l'utilisateur connecté.

    Supprime le device MFA et tous les codes de récupération.

    Returns:
        MFADisableResponse avec confirmation
    """
    try:
        mfa_service.disable_mfa(
            db=db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.MFA_NOT_ENABLED if "not enabled" in str(e) else str(e),
        )

    return MFADisableResponse(disabled=True, message="MFA disabled successfully")
