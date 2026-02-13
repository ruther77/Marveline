"""Endpoints d'authentification pour login et refresh tokens."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.redis import redis_client
from app.services.auth import AuthService
from app.schemas.auth import TokenResponse, RefreshTokenRequest, CSRFTokenResponse
from app.models.user import User
from app.constants import ErrorMessages
import secrets


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
) -> TokenResponse:
    """Authentifie un utilisateur et retourne les JWT tokens.

    Args:
        request: FastAPI Request (pour extraction IP, User-Agent, request_id)
        form_data: Formulaire OAuth2 avec username (email) et password
        db: Session de base de données

    Returns:
        TokenResponse avec access_token, refresh_token, expires_in

    Raises:
        HTTPException 401: Si credentials invalides
        HTTPException 403: Si compte inactif

    Example:
        POST /api/v1/auth/login
        Content-Type: application/x-www-form-urlencoded

        username=user@example.com&password=securepass123

        Response:
        {
            "access_token": "eyJhbGc...",
            "refresh_token": "eyJhbGc...",
            "token_type": "bearer",
            "expires_in": 1800
        }

    Security:
        - Email normalisé en lowercase
        - Password vérifié avec bcrypt
        - Compte doit être actif (is_active=True)
        - Access token expire en 30 minutes
        - Refresh token expire en 7 jours
        - Audit log LOGIN_SUCCESS ou LOGIN_FAILED (conformité RGPD/SOC2)
    """
    auth_service = AuthService(db)

    # Extraire infos pour audit log
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)

    try:
        access_token, refresh_token, expires_in = auth_service.login(
            email=form_data.username,  # OAuth2 spec uses 'username' field
            password=form_data.password,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in
        )

    except HTTPException:
        # Re-raise HTTPExceptions from service
        raise
    except Exception as e:
        # Catch unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during login: {str(e)}"
        )


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """Génère un nouveau access token depuis un refresh token valide.

    Args:
        request: RefreshTokenRequest contenant le refresh_token
        db: Session de base de données

    Returns:
        TokenResponse avec nouveau access_token et même refresh_token

    Raises:
        HTTPException 401: Si refresh token invalide ou expiré
        HTTPException 403: Si compte inactif

    Example:
        POST /api/v1/auth/refresh
        Content-Type: application/json

        {
            "refresh_token": "eyJhbGc..."
        }

        Response:
        {
            "access_token": "eyJhbGc...",  // Nouveau token
            "refresh_token": "eyJhbGc...",  // Même token
            "token_type": "bearer",
            "expires_in": 1800
        }

    Security:
        - Valide signature + expiration du refresh token
        - Charge user depuis DB (vérifie existence + is_active)
        - Génère nouveau access token avec claims à jour
        - Refresh token n'est pas renouvelé (réutilisation jusqu'à expiration)
    """
    auth_service = AuthService(db)

    try:
        new_access_token, expires_in = auth_service.refresh_access_token(
            refresh_token=request.refresh_token
        )

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=request.refresh_token,  # Retourne même refresh token
            token_type="bearer",
            expires_in=expires_in
        )

    except HTTPException:
        # Re-raise HTTPExceptions from service
        raise
    except Exception as e:
        # Catch unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during token refresh: {str(e)}"
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
