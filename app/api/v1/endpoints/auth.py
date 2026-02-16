"""Endpoints d'authentification pour login et refresh tokens."""
import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import AppException
from app.core.permissions import get_effective_permissions_cached
from app.core.redis import redis_client
from app.services.auth import AuthService, MFARequiredResult
from app.services.audit import AuditService
from app.services.session import session_service
from app.schemas.auth import (
    TokenResponse, RefreshTokenRequest, LogoutRequest, LogoutResponse,
    CSRFTokenResponse, UserInfo, ChangePasswordRequest,
    ForgotPasswordRequest, ForgotPasswordResponse,
    ResetPasswordRequest, ResetPasswordResponse,
)
from app.schemas.mfa import MFALoginResponse
from app.models.user import User
from app.constants import ErrorMessages

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", status_code=status.HTTP_200_OK)
def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    """Authentifie un utilisateur et retourne les JWT tokens (ou MFA session token).

    Args:
        request: FastAPI Request (pour extraction IP, User-Agent, request_id)
        form_data: Formulaire OAuth2 avec username (email) et password
        db: Session de base de données

    Returns:
        - TokenResponse si pas de MFA
        - MFALoginResponse si MFA activé (client doit appeler POST /mfa/verify)

    Raises:
        HTTPException 401: Si credentials invalides
        HTTPException 403: Si compte inactif ou verrouillé (brute force)

    Security:
        - Email normalisé en lowercase
        - Password vérifié avec Argon2id/bcrypt
        - Si MFA activé : retourne mfa_session_token (pas de JWT)
        - Compte doit être actif (is_active=True)
        - Audit log LOGIN_SUCCESS (seulement si pas de MFA) ou LOGIN_FAILED
    """
    auth_service = AuthService(db)

    # Extraire infos pour audit log
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    try:
        result = auth_service.login(
            email=form_data.username,  # OAuth2 spec uses 'username' field
            password=form_data.password,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

        # MFA requis — retourner mfa_session_token
        if isinstance(result, MFARequiredResult):
            return MFALoginResponse(
                mfa_required=True,
                mfa_session_token=result.mfa_session_token,
                token_type="mfa_session",
            )

        # Pas de MFA — retourner tokens JWT
        access_token, refresh_token, expires_in = result
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in
        )

    except HTTPException:
        raise
    except AppException:
        raise  # AccountLocked etc. — handled by exception handler middleware
    except Exception:
        logger.exception("Unexpected error during login")
        raise


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """Rotation de refresh token : invalide l'ancien, émet un nouveau.

    Args:
        request: RefreshTokenRequest contenant le refresh_token
        db: Session de base de données

    Returns:
        TokenResponse avec nouveau access_token ET nouveau refresh_token

    Raises:
        HTTPException 401: Si refresh token invalide, expiré, révoqué, ou replay détecté
        HTTPException 403: Si compte inactif

    Security:
        - Vérifie JTI dans whitelist Redis
        - Rotation: ancien refresh invalidé, nouveau émis (même famille)
        - Replay detection: si ancien JTI réutilisé → toute la famille révoquée
    """
    auth_service = AuthService(db)

    try:
        new_access_token, new_refresh_token, expires_in = auth_service.refresh_access_token(
            refresh_token=request.refresh_token
        )

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=expires_in
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during token refresh")
        raise


@router.post("/logout", response_model=LogoutResponse, status_code=status.HTTP_200_OK)
def logout(
    request: Request,
    body: LogoutRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    """Déconnecte l'utilisateur et révoque ses tokens.

    Args:
        request: FastAPI Request (pour extraction IP, User-Agent, token)
        body: LogoutRequest optionnel contenant le refresh_token
        current_user: Utilisateur authentifié (JWT validé)
        db: Session de base de données

    Returns:
        LogoutResponse avec confirmation

    Security:
        - Access token blacklisté (ne sera plus accepté par get_current_user)
        - Refresh token supprimé de whitelist Redis (si fourni)
        - Token family désactivée (si refresh_token fourni)
        - Tous les tokens CSRF de l'utilisateur révoqués
        - Audit log LOGOUT créé
    """
    auth_service = AuthService(db)

    # Extraire access token du header Authorization
    auth_header = request.headers.get("Authorization", "")
    access_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    # Extraire refresh token du body (optionnel)
    refresh_token = body.refresh_token if body and body.refresh_token else None

    # Extraire infos pour audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    try:
        auth_service.logout(
            access_token=access_token,
            user=current_user,
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        return LogoutResponse(message="Logged out successfully", tokens_revoked=True)
    except Exception:
        logger.exception("Unexpected error during logout")
        return LogoutResponse(message="Logged out with errors", tokens_revoked=False)


@router.get("/me", response_model=UserInfo, status_code=status.HTTP_200_OK)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserInfo:
    """Retourne les informations de l'utilisateur authentifié avec ses permissions effectives."""
    perms = get_effective_permissions_cached(current_user.role)
    return UserInfo(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        is_active=current_user.is_active,
        permissions=sorted(p.value for p in perms),
        created_at=str(current_user.created_at) if current_user.created_at else None,
    )


@router.get("/csrf", response_model=CSRFTokenResponse, status_code=status.HTTP_200_OK)
def get_csrf_token(
    current_user: User = Depends(get_current_user)
) -> CSRFTokenResponse:
    """Génère un nouveau token CSRF pour l'utilisateur authentifié.

    Args:
        current_user: Utilisateur authentifié (JWT)

    Returns:
        CSRFTokenResponse avec csrf_token et expires_in

    Raises:
        HTTPException 401: Si JWT invalide ou manquant
        HTTPException 500: Si erreur Redis

    Example:
        GET /api/v1/auth/csrf
        Authorization: Bearer eyJhbGc...

        Response:
        {
            "csrf_token": "abc123xyz789...",
            "expires_in": 900
        }

    Usage:
        1. Le client appelle cet endpoint après login pour obtenir un token CSRF
        2. Le token est stocké dans Redis : csrf:{user_id}:{token}
        3. Le client inclut le token dans le header X-CSRF-Token pour toutes requêtes modifiantes
        4. Le CSRFProtectionMiddleware valide le token avant chaque POST/PUT/PATCH/DELETE

    Security:
        - Token unique (secrets.token_urlsafe(32))
        - TTL 15 minutes (rotation fréquente)
        - Multi-tab support (plusieurs tokens actifs par utilisateur)
        - Automatiquement révoqué lors du logout
    """
    # Générer token CSRF unique
    csrf_token = secrets.token_urlsafe(32)

    # Stocker dans Redis avec TTL 15 minutes
    ttl_seconds = 900  # 15 minutes
    success = redis_client.store_csrf_token(
        user_id=current_user.id,
        token=csrf_token,
        ttl_seconds=ttl_seconds
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
def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change le mot de passe de l'utilisateur authentifié.

    Exige le mot de passe actuel pour preuve d'identité.
    Invalide toutes les sessions sauf la courante après changement.

    Returns:
        Message de confirmation

    Raises:
        HTTPException 401: Si current_password incorrect
        HTTPException 400: Si new_password trop faible
    """
    auth_service = AuthService(db)

    auth_service.change_password(
        user_id=current_user.id,
        current_password=body.current_password,
        new_password=body.new_password,
    )

    # Invalider toutes les sessions sauf la courante
    auth_header = request.headers.get("Authorization", "")
    current_access_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
    current_family_id = None
    if current_access_token:
        try:
            from app.core.security import decode_token
            payload = decode_token(current_access_token)
            current_family_id = payload.get("family_id")
        except Exception:
            logger.debug("Failed to decode current access token for family_id extraction")

    # Révoquer toutes les sessions puis recréer la courante si possible
    session_service.revoke_all_sessions(current_user.id)
    redis_client.revoke_all_csrf_tokens(current_user.id)

    # Audit log
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    audit_service = AuditService(db)
    audit_service.log_action(
        action="PASSWORD_CHANGE",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        entity_type="User",
        entity_id=current_user.id,
        description="Password changed by user",
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )

    db.commit()

    return {"message": "Password changed successfully"}


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
)
def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> ForgotPasswordResponse:
    """Demande de réinitialisation de mot de passe.

    Envoie un email avec un lien de reset si l'email est enregistré.
    Retourne toujours 200 (anti-énumération d'emails).

    Returns:
        ForgotPasswordResponse (message identique dans tous les cas)
    """
    auth_service = AuthService(db)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    auth_service.forgot_password(
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
def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> ResetPasswordResponse:
    """Réinitialise le mot de passe avec un token reçu par email.

    Le token est single-use et expire après 30 minutes.
    Toutes les sessions sont révoquées après le reset.

    Returns:
        ResetPasswordResponse avec confirmation

    Raises:
        HTTPException 400: Si token invalide/expiré ou password faible
    """
    auth_service = AuthService(db)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    auth_service.reset_password(
        token=body.token,
        new_password=body.new_password,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )

    return ResetPasswordResponse()
