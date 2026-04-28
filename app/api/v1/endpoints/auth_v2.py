"""Endpoints IAM v2 — login/refresh/logout/me + OAuth (accounts + memberships).

Préfixe : /auth/v2
Tags    : Authentication v2

Différences vs v1 :
  - Login JSON body (LoginV2Request) avec tenant_id explicite (pas de form OAuth2)
  - Dépendances CurrentAccount / CurrentMembership (pas get_current_user)
  - GET /me retourne AccountInfo (account_id, membership_id, role_name, scopes)
  - OAuth : liaison via AccountOAuthIdentity (pas User.oauth_provider legacy)
  - Aucun import User / UserSession / session_service (legacy)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_db
from app.core.deps import CurrentAccount, CurrentMembership
from app.core.exceptions import AppException
from app.core.security import decode_token
from app.constants import ErrorMessages
from app.schemas.auth import (
    AccountInfo,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginV2Request,
    LogoutResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
)
from app.schemas.mfa import MFALoginResponse
from app.services.account_session import AccountSessionService
from app.services.audit import AuditService
from app.services.auth_v2 import AuthV2Service, MFARequiredResult
from app.services.oauth_v2 import OAuthV2Service
from app.services.pin_auth import PinAuthService, validate_pin_format, PIN_MAX_ATTEMPTS, PIN_LOCKOUT_WINDOW_SECONDS
from app.services.rbac import get_role_scopes
from app.services.token import token_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/v2", tags=["Authentication v2"])

_REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 jours en secondes


@router.post("/login", status_code=status.HTTP_200_OK)
async def login_v2(
    request: Request,
    response: Response,
    body: LoginV2Request,
    db: AsyncSession = Depends(get_async_db),
    captcha_token: Optional[str] = Header(default=None, alias="X-Captcha-Token"),
) -> TokenResponse | MFALoginResponse:
    """Login IAM v2 — JSON body avec tenant_id explicite.

    Contrairement à v1 (form OAuth2), accepte JSON.
    Retourne TokenResponse (access token + cookie refresh) ou MFALoginResponse.

    Raises:
        400: CAPTCHA requis manquant.
        401: Credentials invalides.
        403: Compte inactif ou membership révoqué.
        429: IP/email bloqué (brute force).
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    # ISO-APP-01 : si le reverse proxy a injecté X-App-Code, vérifier que
    # le tenant demandé est bien rattaché à cette app. Sinon 403.
    app_code_header = request.headers.get("X-App-Code")
    if app_code_header:
        from sqlalchemy import select
        from app.models.tenant import Tenant
        tenant_app_code = await db.scalar(
            select(Tenant.app_code).where(Tenant.id == body.tenant_id)
        )
        if tenant_app_code and tenant_app_code != app_code_header:
            logger.warning(
                "ISO-APP-01 login reject: tenant=%s (app=%s) on app=%s",
                body.tenant_id, tenant_app_code, app_code_header,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This account belongs to '{tenant_app_code}', not '{app_code_header}'.",
            )

    try:
        result = await AuthV2Service(db).login(
            email=body.email,
            password=body.password,
            tenant_id=body.tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            captcha_token=captcha_token,
        )
    except HTTPException:
        raise
    except AppException:
        raise
    except Exception:
        logger.exception("Unexpected error during IAM v2 login")
        raise

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


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh_v2(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
) -> TokenResponse:
    """Rotation atomique du refresh token — IAM v2.

    Lit le refresh_token depuis le cookie httpOnly.
    Émet nouveau access_token + nouveau refresh_token (même famille).

    Raises:
        401: Cookie absent, token invalide/expiré/révoqué ou replay détecté.
    """
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.INVALID_REFRESH_TOKEN,
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        new_access, new_refresh, expires_in = await AuthV2Service(db).refresh(
            refresh_token=refresh_token_value,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during IAM v2 refresh")
        raise

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=_REFRESH_COOKIE_MAX_AGE,
    )
    return TokenResponse(
        access_token=new_access,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post("/logout", response_model=LogoutResponse, status_code=status.HTTP_200_OK)
async def logout_v2(
    request: Request,
    response: Response,
    account: CurrentAccount,
    membership: CurrentMembership,
    db: AsyncSession = Depends(get_async_db),
) -> LogoutResponse:
    """Logout IAM v2 — révoque access token, refresh token et AccountSession.

    Raises:
        401: Access token invalide (déjà intercepté par CurrentAccount dep).
    """
    auth_header = request.headers.get("Authorization", "")
    access_token = auth_header[len("Bearer "):] if auth_header.startswith("Bearer ") else ""
    refresh_token = request.cookies.get("refresh_token")
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    try:
        payload = decode_token(access_token) if access_token else {}
        device_id = payload.get("did", "")
        session_id = payload.get("sid", "")

        await token_service.revoke_on_logout(
            access_token=access_token,
            user_id=account.id,
            device_id=device_id,
            session_id=session_id,
            refresh_token=refresh_token,
        )

        if session_id:
            await AccountSessionService(db).revoke(
                session_id=session_id,
                requesting_membership_id=membership.id,
                reason="logout",
            )

        await AuditService(db).log_logout(
            user_id=account.id,
            tenant_id=membership.tenant_id,
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown",
            request_id=request_id or "",
        )
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during IAM v2 logout")
        raise

    response.delete_cookie(key="refresh_token")
    return LogoutResponse(message="Logged out successfully", tokens_revoked=True)


class SwitchMembershipRequest(BaseModel):
    """Body de switch-membership : tenant cible."""

    tenant_id: int


@router.post("/switch-membership", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def switch_membership_v2(
    request: Request,
    body: SwitchMembershipRequest,
    db: AsyncSession = Depends(get_async_db),
) -> TokenResponse:
    """Émet un access token pour un autre tenant sans rotation du refresh cookie.

    Lit le refresh_token depuis le cookie httpOnly.
    Retourne uniquement un nouvel access_token (tid = body.tenant_id).
    Le refresh cookie reste inchangé.

    Cas d'usage : MassaCorp — passer de tenant_id=2 (épicerie) à tenant_id=3 (restaurant)
    sans avoir à se reconnecter.

    Raises:
        401: Cookie absent, token invalide/expiré ou compte inactif.
        403: Pas de membership actif dans le tenant cible.
    """
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.INVALID_REFRESH_TOKEN,
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        access_token, expires_in = await AuthV2Service(db).switch_membership(
            refresh_token=refresh_token_value,
            target_tenant_id=body.tenant_id,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during switch-membership")
        raise

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )


class OAuthCallbackRequest(BaseModel):
    """Body du callback OAuth v2."""

    code: str
    state: str


@router.get("/oauth/{provider}/authorize", status_code=status.HTTP_200_OK)
async def oauth_authorize_v2(
    provider: str,
    tenant_id: int = Query(..., description="Tenant cible — requis pour le flow IAM v2"),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Génère state + auth_url vers le provider OAuth (IAM v2).

    Le tenant_id est encodé dans le state Redis (TTL 300s, single-use).
    Il sera consommé au callback pour valider le membership.

    Raises:
        404 : provider inconnu ou non configuré.
        503 : Redis indisponible.
    """
    return await OAuthV2Service(db).authorize(provider=provider, tenant_id=tenant_id)


@router.post("/oauth/{provider}/callback", status_code=status.HTTP_200_OK)
async def oauth_callback_v2(
    provider: str,
    body: OAuthCallbackRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
) -> TokenResponse:
    """Traite le callback OAuth après retour du provider (IAM v2).

    Security :
        - state validé et consommé atomiquement (FAIL-CLOSED)
        - tenant_id extrait du state Redis (anti-tamper)
        - Membership actif requis dans le tenant du state

    Raises:
        400 : state invalide / email manquant / compte introuvable.
        403 : compte inactif ou sans membership dans le tenant.
        502 : provider OAuth down.
        503 : Redis indisponible.
    """
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    access_token, refresh_token, expires_in, password_change_required = (
        await OAuthV2Service(db).callback(
            provider=provider,
            code=body.code,
            state=body.state,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
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
        password_change_required=password_change_required,
    )


@router.get("/me", response_model=AccountInfo, status_code=status.HTTP_200_OK)
async def me_v2(
    account: CurrentAccount,
    membership: CurrentMembership,
) -> AccountInfo:
    """Informations du compte IAM v2 — account global + membership actif.

    Retourne : account_id, email, prénom, nom, tenant_id, membership_id,
               role_name, is_active, password_change_required, scopes RBAC.
    """
    scopes = await get_role_scopes(membership.role_name, None)
    return AccountInfo(
        account_id=account.id,
        email=account.email,
        first_name=account.first_name,
        last_name=account.last_name,
        tenant_id=membership.tenant_id,
        membership_id=membership.id,
        role_name=membership.role_name,
        is_active=account.is_active,
        password_change_required=account.password_change_required,
        scopes=scopes,
    )


# ═══════════════════════════════════════════════════════════════════════
# Password management — forgot / reset / change
# ═══════════════════════════════════════════════════════════════════════


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
)
async def forgot_password_v2(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_async_db),
) -> ForgotPasswordResponse:
    """Demande de reinitialisation de mot de passe — IAM v2.

    Retourne toujours 200 (anti-enumeration d'emails).
    Rate-limited par email (max 5 / heure).
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
async def reset_password_v2(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_async_db),
) -> ResetPasswordResponse:
    """Reinitialise le mot de passe avec un token recu par email — IAM v2.

    Le token est single-use et expire apres 30 minutes.
    Toutes les sessions sont revoquees apres le reset.

    Raises:
        400: Token invalide, expire ou deja consomme / mot de passe trop faible.
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


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password_v2(
    request: Request,
    body: ChangePasswordRequest,
    account: CurrentAccount,
    membership: CurrentMembership,
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Change le mot de passe du compte authentifie — IAM v2.

    Exige le mot de passe actuel. Revoque toutes les sessions sauf la courante.
    Brute-force protege (5 tentatives / 15 min).

    Raises:
        401: Mot de passe actuel incorrect.
        400: Nouveau mot de passe identique ou trop faible / compromis HIBP.
        429: Trop de tentatives.
    """
    auth_service = AuthV2Service(db)

    # AuthV2Service.change_password gere : brute-force, validation, hash, revocation sessions
    await auth_service.change_password(
        account_id=account.id,
        current_password=body.current_password,
        new_password=body.new_password,
    )

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    await AuditService(db).log_action(
        action="PASSWORD_CHANGE",
        tenant_id=membership.tenant_id,
        user_id=account.id,
        entity_type="Account",
        entity_id=account.id,
        description="Password changed by user (IAM v2)",
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
    await db.commit()

    return {"message": "Password changed successfully"}


# ═══════════════════════════════════════════════════════════════════════
# PIN Authentication — restaurant servers
# ═══════════════════════════════════════════════════════════════════════


class PinLoginRequest(BaseModel):
    pin: str
    device_id: str
    tenant_id: int


class RegisterDeviceRequest(BaseModel):
    device_id: str
    device_name: str | None = None


class SetPinRequest(BaseModel):
    pin: str


@router.post("/pin-login", status_code=status.HTTP_200_OK)
async def pin_login(
    request: Request,
    response: Response,
    body: PinLoginRequest,
    db: AsyncSession = Depends(get_async_db),
) -> TokenResponse:
    """Login par PIN sur device enregistré (restaurant serveurs).

    Prérequis :
        - Le device doit être enregistré (POST /auth/v2/register-device après premier login)
        - Le compte doit avoir un PIN configuré (POST /auth/v2/set-pin)

    Lockout : 3 tentatives / 5 min par device_id (surface 10k combinaisons).
    """
    from app.core.redis import redis_sec

    ip_address = request.client.host if request.client else "unknown"
    lockout_key = f"pin_lockout:{body.device_id}"

    # P2-21 : lockout global cross-device (15 tentatives / 30 min)
    global_key = f"pin_lockout_global:{body.tenant_id}"
    global_attempts = await redis_sec.client.get(global_key)
    if global_attempts and int(global_attempts) >= 15:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": "Trop de tentatives PIN sur ce tenant.", "retry_after": 1800},
        )

    # Verifier lockout device
    attempts = await redis_sec.client.get(lockout_key)
    if attempts and int(attempts) >= PIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Trop de tentatives PIN. Réessayez dans quelques minutes.",
                "retry_after": PIN_LOCKOUT_WINDOW_SECONDS,
            },
        )

    if not validate_pin_format(body.pin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PIN invalide (4-6 chiffres requis).",
        )

    pin_service = PinAuthService(db)
    account = await pin_service.verify_pin_login(
        pin=body.pin,
        device_id=body.device_id,
        tenant_id=body.tenant_id,
    )

    if not account:
        # Incrementer lockout device + lockout global cross-device (P2-21)
        global_key = f"pin_lockout_global:{body.tenant_id}"
        pipe = redis_sec.client.pipeline()
        pipe.incr(lockout_key)
        pipe.expire(lockout_key, PIN_LOCKOUT_WINDOW_SECONDS)
        pipe.incr(global_key)
        pipe.expire(global_key, 1800)  # 30 min lockout global
        await pipe.execute()

        logger.warning("PIN login failed device=%s tenant=%d ip=%s", body.device_id, body.tenant_id, ip_address)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PIN ou device invalide.",
        )

    # Réinitialiser lockout en cas de succès
    await redis_sec.client.delete(lockout_key)

    # Résoudre membership + générer tokens
    from app.repositories.tenant_membership import AsyncTenantMembershipRepository
    membership = await AsyncTenantMembershipRepository(db).get_active(account.id, body.tenant_id)
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Aucun accès à ce tenant.")

    access_token, refresh_token, expires_in = await token_service.issue_tokens(
        user_id=account.id,
        tenant_id=body.tenant_id,
        role=membership.role_name,
        device_id=body.device_id,
        session_id=f"pin:{body.device_id}",
        membership_id=membership.id,
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=_REFRESH_COOKIE_MAX_AGE,
    )

    logger.info("PIN login OK account=%d tenant=%d device=%s", account.id, body.tenant_id, body.device_id)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        password_change_required=False,
    )


@router.post("/register-device", status_code=status.HTTP_201_CREATED)
async def register_device(
    body: RegisterDeviceRequest,
    account: CurrentAccount,
    membership: CurrentMembership,
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Enregistre un device pour login PIN (nécessite auth email+password préalable)."""
    pin_service = PinAuthService(db)
    device = await pin_service.register_device(
        account_id=account.id,
        tenant_id=membership.tenant_id,
        device_id=body.device_id,
        device_name=body.device_name,
    )
    await db.commit()

    logger.info("Device registered account=%d device=%s name=%s", account.id, body.device_id, body.device_name)
    return {
        "id": device.id,
        "device_id": device.device_id,
        "device_name": device.device_name,
        "registered_at": device.registered_at.isoformat() if device.registered_at else None,
    }


@router.post("/set-pin", status_code=status.HTTP_200_OK)
async def set_pin(
    body: SetPinRequest,
    account: CurrentAccount,
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Définit ou met à jour le PIN du compte (nécessite auth email+password)."""
    if not validate_pin_format(body.pin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PIN invalide. Doit contenir 4 à 6 chiffres.",
        )

    pin_service = PinAuthService(db)
    await pin_service.set_pin(account.id, body.pin)
    await db.commit()

    logger.info("PIN set for account=%d", account.id)
    return {"message": "PIN configuré avec succès."}
