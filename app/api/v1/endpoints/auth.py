"""Endpoints d'authentification pour login et refresh tokens."""
import logging
import secrets

import redis.exceptions as redis_exc
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, Header, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_db
from app.core.deps import UserCompat, get_current_user_async
from app.core.exceptions import AppException
from app.services.rbac import get_role_scopes
from app.core.redis import redis_client
from app.core.security import decode_token
from app.services.auth_v2 import AuthV2Service, MFARequiredResult
from app.services.account import AccountService
from app.services.audit import AuditService
from app.repositories.account_session import AsyncAccountSessionRepository
from app.schemas.auth import (
    TokenResponse, RefreshTokenRequest, LogoutRequest, LogoutResponse,
    CSRFTokenResponse, UserInfo, ChangePasswordRequest,
    ForgotPasswordRequest, ForgotPasswordResponse,
    ResetPasswordRequest, ResetPasswordResponse,
)
from app.schemas.mfa import MFALoginResponse
from app.models.account_session import AccountSession
from app.constants import ErrorMessages
from app.constants.security import SessionConfig

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/auth", tags=["Authentication"])


_REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 jours en secondes


async def _resolve_tenant_id_for_email(
    db: AsyncSession,
    email: str,
) -> Optional[int]:
    """Fallback : résout le premier tenant actif d'un account par email.

    Utilisé quand le champ tenant_id est absent du login form.
    Retourne None si l'email n'existe pas ou n'a aucun membership actif.
    """
    from app.repositories.account import AsyncAccountRepository
    from app.repositories.tenant_membership import AsyncTenantMembershipRepository

    repo_account = AsyncAccountRepository(db)
    account = await repo_account.get_active_by_email(email.lower().strip())
    if not account:
        return None

    repo_membership = AsyncTenantMembershipRepository(db)
    memberships = await repo_membership.list_by_account(account.id)
    if not memberships:
        return None

    return memberships[0].tenant_id


@router.post("/login", status_code=status.HTTP_200_OK)
async def login(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_async_db),
    captcha_token_header: Optional[str] = Header(default=None, alias="X-Captcha-Token"),
    captcha_token_form: Optional[str] = Form(default=None, alias="captcha_token"),
    tenant_id: Optional[int] = Form(default=None, alias="tenant_id"),
):
    """Authentifie un utilisateur et retourne les JWT tokens (ou MFA session token).

    Args:
        request: FastAPI Request (pour extraction IP, User-Agent, request_id)
        form_data: Formulaire OAuth2 avec username (email) et password
        db: Session de base de données
        tenant_id: ID du tenant cible (optionnel — fallback: premier membership actif)

    Returns:
        - TokenResponse si pas de MFA
        - MFALoginResponse si MFA activé (client doit appeler POST /mfa/verify)

    Raises:
        HTTPException 401: Si credentials invalides
        HTTPException 403: Si compte inactif ou verrouillé (brute force)
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    # Résoudre tenant_id si absent (fallback single-tenant / migration)
    effective_tenant_id = tenant_id
    if effective_tenant_id is None:
        effective_tenant_id = await _resolve_tenant_id_for_email(db, form_data.username)
    if effective_tenant_id is None:
        # Anti-énumération : passer un sentinel qui sera rejeté par AuthV2Service
        effective_tenant_id = 0

    auth_service = AuthV2Service(db)

    try:
        result = await auth_service.login(
            email=form_data.username,
            password=form_data.password,
            tenant_id=effective_tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            captcha_token=captcha_token_header or captcha_token_form,
        )

        if isinstance(result, MFARequiredResult):
            return MFALoginResponse(
                mfa_required=True,
                mfa_session_token=result.mfa_session_token,
                token_type="mfa_session",
            )

        access_token, refresh_token, expires_in, password_change_required = result
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
            password_change_required=password_change_required,
        )

    except (HTTPException, AppException) as exc:
        # S1.T6 (F1002 / AUDIT-LOGIN-EXCL-01) — RGPD Art.30 tracabilite.
        # /auth/login est exclu d'AuditMiddleware (EXCLUDED_PATHS), donc on log
        # ici manuellement avant propagation 401/403. Session separee :
        # robustesse meme si la session principale est rollback par AuthV2Service.
        try:
            from app.core.database import get_async_db_context
            async with get_async_db_context() as audit_db:
                await AuditService(audit_db).log_action(
                    action="LOGIN_FAILED",
                    tenant_id=effective_tenant_id if effective_tenant_id else 0,
                    user_id=None,
                    description=f"Login failed for {form_data.username}",
                    changes={
                        "reason": exc.__class__.__name__,
                        "actor_email": form_data.username,
                    },
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_id=request_id,
                )
                await audit_db.commit()
        except Exception:
            logger.exception("F1002: failed to write audit_log for login failure")
        raise
    except Exception:
        logger.exception("Unexpected error during login")
        raise


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
) -> TokenResponse:
    """Rotation de refresh token : invalide l'ancien, émet un nouveau.

    Raises:
        HTTPException 401: Si cookie absent, token invalide, expiré, révoqué, ou replay détecté
        HTTPException 403: Si compte inactif
    """
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token manquant"
        )

    auth_service = AuthV2Service(db)

    try:
        new_access_token, new_refresh_token, expires_in = await auth_service.refresh(
            refresh_token=refresh_token_value
        )

        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite="lax",
            max_age=_REFRESH_COOKIE_MAX_AGE,
        )
        return TokenResponse(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=expires_in
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during token refresh")
        raise


@router.post("/logout", response_model=LogoutResponse, status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    body: LogoutRequest = None,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> LogoutResponse:
    """Déconnecte l'utilisateur et révoque ses tokens."""
    auth_header = request.headers.get("Authorization", "")
    access_token = auth_header.removeprefix("Bearer ") if auth_header.startswith("Bearer ") else ""

    # Extraire membership_id du claim mid — UserCompat ne l'expose pas directement
    membership_id = 0
    if access_token:
        try:
            payload = decode_token(access_token)
            mid_raw = payload.get("mid")
            if mid_raw:
                membership_id = int(mid_raw)
        except Exception as e:
            # P2-14 : logger au lieu de silencer
            logger.debug("Token decode au logout (attendu si expire): %s", type(e).__name__)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    auth_service = AuthV2Service(db)
    try:
        await auth_service.logout(
            access_token=access_token,
            account_id=current_user.id,
            membership_id=membership_id,
            tenant_id=current_user.tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        response.delete_cookie(key="refresh_token")
        return LogoutResponse(message="Logged out successfully", tokens_revoked=True)
    except redis_exc.RedisError as exc:
        logger.critical("Redis-SEC down during logout — tokens may be zombie: %s", exc)
        response.delete_cookie(key="refresh_token")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorMessages.REDIS_UNAVAILABLE,
        ) from exc
    except Exception:
        logger.exception("Unexpected error during logout")
        raise


@router.get("/me", response_model=UserInfo, status_code=status.HTTP_200_OK)
async def get_current_user_info(
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> UserInfo:
    """Retourne les informations de l'utilisateur authentifié avec ses permissions effectives."""
    scopes = await get_role_scopes(current_user.role, db)
    return UserInfo(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        is_active=current_user.is_active,
        permissions=sorted(scopes),
        created_at=str(current_user.created_at) if current_user.created_at else None,
        password_change_required=current_user.password_change_required,
    )


@router.get("/csrf", response_model=CSRFTokenResponse, status_code=status.HTTP_200_OK)
async def get_csrf_token(
    request: Request,
    current_user: UserCompat = Depends(get_current_user_async),
) -> CSRFTokenResponse:
    """Génère un nouveau token CSRF pour la session courante (§04 §4.3)."""
    auth_header = request.headers.get("Authorization", "")
    session_id = None
    if auth_header.startswith("Bearer "):
        try:
            payload = decode_token(auth_header.replace("Bearer ", "", 1))
            session_id = payload.get("sid")
        except Exception:
            pass

    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session ID manquant dans le token"
        )

    csrf_token = secrets.token_urlsafe(32)
    ttl_seconds = SessionConfig.SESSION_TTL_SECONDS  # aligné sur la session (7j) — P2-01
    success = await redis_client.store_csrf_token(
        session_id=session_id,
        token=csrf_token,
        ttl_seconds=ttl_seconds,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorMessages.CSRF_TOKEN_GENERATION_FAILED
        )

    return CSRFTokenResponse(
        csrf_token=csrf_token,
        expires_in=ttl_seconds
    )


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
):
    """Change le mot de passe de l'utilisateur authentifié.

    Exige le mot de passe actuel pour preuve d'identité.
    Invalide toutes les sessions sauf la courante après changement.
    """
    account_service = AccountService(db)

    await account_service.change_password(
        account_id=current_user.id,
        current_password=body.current_password,
        new_password=body.new_password,
    )

    current_did = ""
    current_sid = ""
    auth_header = request.headers.get("Authorization", "")
    raw_token = auth_header.removeprefix("Bearer ") if auth_header.startswith("Bearer ") else None
    if raw_token:
        try:
            payload = decode_token(raw_token)
            current_did = payload.get("did", "")
            current_sid = payload.get("sid", "")
        except Exception:
            logger.error(
                "Impossible d'extraire did/sid depuis le JWT pour account=%s — révocation annulée",
                current_user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session ID missing — cannot target revocation",
            )

    await redis_client.logout_other_sessions(current_user.id, current_did, current_sid)
    await AsyncAccountSessionRepository(db).revoke_all_by_account(
        current_user.id, reason="password_change", except_device_id=current_did or None
    )

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    audit_service = AuditService(db)
    await audit_service.log_action(
        action="PASSWORD_CHANGE",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="Account",
        entity_id=current_user.id,
        description="Password changed by user",
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )

    await db.commit()

    return {"message": "Password changed successfully"}


@router.post("/logout/device/{device_id}", status_code=status.HTTP_200_OK)
async def logout_device(
    device_id: str,
    request: Request,
    current_user: UserCompat = Depends(get_current_user_async),
    db: AsyncSession = Depends(get_async_db),
):
    """Révoque toutes les sessions d'un device spécifique (§4.3 S-09.1)."""
    # Vérifier que le device appartient bien à l'utilisateur courant
    device_exists = (
        await db.execute(
            select(AccountSession.id)
            .where(
                AccountSession.account_id == current_user.id,
                AccountSession.device_id == device_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if device_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.DEVICE_REVOKED,
        )

    # Révocation Redis via Lua (atomique — §4.3)
    sessions_revoked_redis = await redis_client.logout_device(current_user.id, device_id)

    # Révocation DB — toutes les sessions actives du device
    revoke_time = datetime.now(timezone.utc)
    result = await db.execute(
        update(AccountSession)
        .where(
            AccountSession.account_id == current_user.id,
            AccountSession.device_id == device_id,
            AccountSession.revoked_at.is_(None),
        )
        .values(revoked_at=revoke_time, revoke_reason="device_logout")
    )
    sessions_revoked_db = result.rowcount

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    audit_service = AuditService(db)
    await audit_service.log_action(
        action="USER_LOGOUT_DEVICE",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="Device",
        entity_id=current_user.id,
        description=f"Device logout: device_id={device_id}",
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )

    await db.commit()

    return {
        "status": "logged_out",
        "device_id": device_id,
        "sessions_revoked": max(sessions_revoked_redis, sessions_revoked_db),
    }


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
)
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_async_db),
) -> ForgotPasswordResponse:
    """Demande de réinitialisation de mot de passe.

    Retourne toujours 200 (anti-énumération d'emails).
    """
    auth_service = AuthV2Service(db)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    await auth_service.forgot_password(
        email=body.email,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )

    return ForgotPasswordResponse()


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
)
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_async_db),
) -> ResetPasswordResponse:
    """Réinitialise le mot de passe avec un token reçu par email.

    Le token est single-use et expire après 30 minutes.
    Toutes les sessions sont révoquées après le reset.
    """
    auth_service = AuthV2Service(db)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    await auth_service.reset_password(
        token=body.token,
        new_password=body.new_password,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )

    return ResetPasswordResponse()
