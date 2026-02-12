"""Endpoints d'authentification pour login et refresh tokens."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.auth import AuthService
from app.schemas.auth import TokenResponse, RefreshTokenRequest


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
) -> TokenResponse:
    """Authentifie un utilisateur et retourne les JWT tokens.

    Args:
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
    """
    auth_service = AuthService(db)

    try:
        access_token, refresh_token, expires_in = auth_service.login(
            email=form_data.username,  # OAuth2 spec uses 'username' field
            password=form_data.password
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
