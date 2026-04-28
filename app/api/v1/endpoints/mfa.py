"""Endpoints MFA TOTP — setup, verify, disable."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_db
from app.core.deps import get_current_user_async, UserCompat
from app.core.redis import redis_sec
from app.core.security import decode_token

# P1-18 : rate limiting TOTP verification
TOTP_MAX_ATTEMPTS = 5
TOTP_LOCKOUT_SECONDS = 300
from app.schemas.auth import TokenResponse
from app.schemas.mfa import (
    MFADisableResponse,
    MFARegenerateCodesRequest,
    MFARegenerateCodesResponse,
    MFASetupResponse,
    MFAStatusResponse,
    MFAVerifyRequest,
    MFAVerifySetupRequest,
    MFAVerifySetupResponse,
    StepUpVerifyRequest,
    StepUpVerifyResponse,
)
from app.services.audit import AuditService
from app.services.mfa import mfa_service
from app.services.session import session_service, generate_device_id
from app.services.token import token_service
from app.constants import ErrorMessages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mfa", tags=["MFA"])


@router.post("/setup", response_model=MFASetupResponse, status_code=status.HTTP_200_OK)
async def setup_mfa(
    current_user: UserCompat = Depends(get_current_user_async),
    async_db: AsyncSession = Depends(get_async_db),
) -> MFASetupResponse:
    """Initialise le setup MFA TOTP pour l'utilisateur.

    Génère un secret TOTP, une URI de provisioning (QR code) et des codes de récupération.
    Le MFA n'est pas encore activé — il faut appeler POST /mfa/verify-setup avec un code valide.

    Returns:
        MFASetupResponse avec secret, provisioning_uri, recovery_codes
    """
    try:
        secret, provisioning_uri, recovery_codes = await mfa_service.setup_totp(
            db=async_db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            email=current_user.email,
        )
        await async_db.commit()
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
async def verify_setup(
    body: MFAVerifySetupRequest,
    current_user: UserCompat = Depends(get_current_user_async),
    async_db: AsyncSession = Depends(get_async_db),
) -> MFAVerifySetupResponse:
    """Valide le setup MFA avec un premier code TOTP.

    Active définitivement le MFA pour l'utilisateur après vérification du code.

    Returns:
        MFAVerifySetupResponse avec confirmation
    """
    try:
        await mfa_service.verify_setup(
            db=async_db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            totp_code=body.totp_code,
        )
        await async_db.commit()
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


_REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 jours en secondes


@router.post("/verify", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def verify_mfa(
    body: MFAVerifyRequest,
    request: Request,
    response: Response,
    async_db: AsyncSession = Depends(get_async_db),
) -> TokenResponse:
    """Vérifie le code MFA et complète l'authentification (step 2 du login).

    Cet endpoint n'utilise PAS de JWT — il consomme le mfa_session_token
    obtenu lors du login (step 1). Après vérification TOTP ou recovery code,
    émet les tokens JWT (access + refresh) et crée la session.

    Returns:
        TokenResponse avec access_token, refresh_token, expires_in
    """
    # P1-18 : rate limit TOTP par IP
    client_ip = request.client.host if request.client else "unknown"
    totp_lockout_key = f"totp_lockout:{client_ip}"
    totp_attempts_raw = await redis_sec.client.get(totp_lockout_key)
    if totp_attempts_raw and int(totp_attempts_raw) >= TOTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "TOTP_RATE_LIMITED", "retry_after": TOTP_LOCKOUT_SECONDS},
        )

    # Valider le mfa_session_token (single-use Redis — méthode synchrone)
    session_data = await mfa_service.validate_mfa_session(body.mfa_session_token)
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
            await mfa_service.verify_totp(
                db=async_db,
                user_id=user_id,
                tenant_id=tenant_id,
                totp_code=body.totp_code,
            )
        else:
            await mfa_service.verify_recovery_code(
                db=async_db,
                user_id=user_id,
                tenant_id=tenant_id,
                recovery_code=body.recovery_code,
            )
    except ValueError as e:
        # P1-18 : incrementer compteur echec TOTP
        await redis_sec.client.incr(totp_lockout_key)
        await redis_sec.client.expire(totp_lockout_key, TOTP_LOCKOUT_SECONDS)

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

    # P1-18 : reset compteur apres succes
    await redis_sec.client.delete(totp_lockout_key)

    # ── MFA vérifié — audit + session + tokens ──

    ip_address = request.client.host if request.client else mfa_ip
    user_agent = request.headers.get("User-Agent", "unknown")
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

    audit_service = AuditService(async_db)
    await audit_service.log_login(
        user_id=user_id,
        tenant_id=tenant_id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        success=True,
        email=email,
    )
    await async_db.commit()

    # 1. Générer device_id (fingerprint User-Agent + IP /24)
    device_id = generate_device_id(user_agent, ip_address)

    # 2. Créer session DB+Redis AVANT d'émettre les tokens (session_id requis dans JWT)
    session_id = await session_service.create_session(
        db=async_db,
        user_id=user_id,
        tenant_id=tenant_id,
        device_id=device_id,
        ip_address=ip_address,
        user_agent=user_agent,
        mfa_verified=True,
    )
    await async_db.commit()

    # 3. Émettre tokens JWT avec did + sid v3
    access_token, refresh_token, expires_in = await token_service.issue_tokens(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        device_id=device_id,
        session_id=session_id,
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=_REFRESH_COOKIE_MAX_AGE,
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.get("/status", response_model=MFAStatusResponse, status_code=status.HTTP_200_OK)
async def mfa_status(
    current_user: UserCompat = Depends(get_current_user_async),
    async_db: AsyncSession = Depends(get_async_db),
) -> MFAStatusResponse:
    """Retourne le statut MFA de l'utilisateur connecté.

    Returns:
        MFAStatusResponse avec mfa_enabled et recovery_codes_remaining
    """
    enabled = await mfa_service.is_mfa_enabled(async_db, current_user.id, current_user.tenant_id)
    remaining = await mfa_service.get_recovery_codes_count(
        async_db, current_user.id, current_user.tenant_id
    )

    return MFAStatusResponse(
        mfa_enabled=enabled,
        recovery_codes_remaining=remaining,
    )


@router.delete("", response_model=MFADisableResponse, status_code=status.HTTP_200_OK)
async def disable_mfa(
    current_user: UserCompat = Depends(get_current_user_async),
    async_db: AsyncSession = Depends(get_async_db),
) -> MFADisableResponse:
    """Désactive le MFA pour l'utilisateur connecté.

    Supprime le device MFA et tous les codes de récupération.

    Returns:
        MFADisableResponse avec confirmation
    """
    try:
        await mfa_service.disable_mfa(
            db=async_db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
        await async_db.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.MFA_NOT_ENABLED if "not enabled" in str(e) else str(e),
        )

    return MFADisableResponse(disabled=True, message="MFA disabled successfully")


@router.post(
    "/backup-codes/regenerate",
    response_model=MFARegenerateCodesResponse,
    status_code=status.HTTP_200_OK,
)
async def regenerate_backup_codes(
    body: MFARegenerateCodesRequest,
    request: Request,
    current_user: UserCompat = Depends(get_current_user_async),
    async_db: AsyncSession = Depends(get_async_db),
) -> MFARegenerateCodesResponse:
    """Régénère les codes de récupération MFA.

    Exige un code TOTP valide pour prouver l'identité avant régénération.
    Les anciens codes sont remplacés et ne fonctionnent plus.

    Returns:
        MFARegenerateCodesResponse avec les nouveaux codes
    """
    # Vérifier le code TOTP d'abord (preuve d'identité)
    try:
        await mfa_service.verify_totp(
            db=async_db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            totp_code=body.totp_code,
        )
    except ValueError as e:
        error_msg = str(e)
        if "already used" in error_msg:
            detail = ErrorMessages.MFA_CODE_ALREADY_USED
        elif "Invalid TOTP" in error_msg:
            detail = ErrorMessages.MFA_INVALID_TOTP_CODE
        elif "not enabled" in error_msg:
            detail = ErrorMessages.MFA_NOT_ENABLED
        else:
            detail = error_msg
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    # Régénérer les codes
    try:
        new_codes = await mfa_service.regenerate_recovery_codes(
            db=async_db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Audit log
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    audit_service = AuditService(async_db)
    await audit_service.log_action(
        action="RECOVERY_CODES_REGENERATED",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="MFADevice",
        entity_id=current_user.id,
        description="MFA recovery codes regenerated",
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
    await async_db.commit()

    return MFARegenerateCodesResponse(recovery_codes=new_codes)


@router.post("/stepup/verify", response_model=StepUpVerifyResponse, status_code=status.HTTP_200_OK)
async def verify_mfa_stepup(
    payload: StepUpVerifyRequest,
    request: Request,
    current_user: UserCompat = Depends(get_current_user_async),
    async_db: AsyncSession = Depends(get_async_db),
) -> StepUpVerifyResponse:
    """Valide le MFA step-up pour accéder à une action sensible (spec §05.3).

    Vérifie le code TOTP et enregistre le step-up valide pour 15 minutes.
    À appeler avant un endpoint protégé par require_stepup().

    Returns:
        StepUpVerifyResponse avec statut et durée de validité
    """
    device_id = ""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            tok = decode_token(auth_header[len("Bearer "):])
            device_id = tok.get("did", "")
        except Exception:
            pass

    try:
        await mfa_service.verify_stepup(
            async_db, current_user.id, device_id, payload.totp_code
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    return StepUpVerifyResponse()
