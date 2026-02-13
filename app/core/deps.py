"""Dependencies FastAPI pour injection dans les endpoints.

Includes:
    - Database session management (get_db)
    - Current user authentication (get_current_user)
    - Role-based authorization (require_role)
"""
from typing import Generator, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db  # Import depuis database.py (source unique)
from app.core.security import decode_token
from app.models.user import User
from app.constants import AuthEndpoints, ErrorMessages, SecurityHeaders, TokenType, UserRole


# OAuth2 scheme pour extraction du token Bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=AuthEndpoints.LOGIN)


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """Dependency pour obtenir l'utilisateur connecté depuis le JWT.

    Args:
        db: Session DB (injectée)
        token: JWT token (extrait du header Authorization)

    Returns:
        Utilisateur connecté (modèle User)

    Raises:
        HTTPException 401: Si token invalide ou user non trouvé

    Security:
        - Valide signature JWT
        - Vérifie expiration
        - Charge user depuis DB
        - Vérifie que user.is_active == True

    Example:
        @router.get("/me")
        def get_me(current_user: User = Depends(get_current_user)):
            return {"email": current_user.email}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ErrorMessages.INVALID_TOKEN,
        headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
    )

    # Décoder le token
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    # Vérifier type de token
    token_type = payload.get("type")
    if token_type != TokenType.ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.INVALID_TOKEN_TYPE,
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )

    # Extraire user_id (sub est une string selon JWT spec)
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    # Convertir sub (string) en int pour query DB
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    # Charger user depuis DB
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    # Vérifier que le compte est actif
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorMessages.ACCOUNT_INACTIVE
        )

    return user


def require_role(*allowed_roles: str):
    """Dependency factory pour vérifier le rôle de l'utilisateur.

    Args:
        *allowed_roles: Rôles autorisés (admin, manager, staff)

    Returns:
        Dependency function qui vérifie le rôle

    Raises:
        HTTPException 403: Si rôle insuffisant

    Example:
        # Endpoint réservé aux admins
        @router.delete("/users/{id}")
        def delete_user(
            id: int,
            current_user: User = Depends(require_role("admin"))
        ):
            ...

        # Endpoint pour admins et managers
        @router.post("/products")
        def create_product(
            product: ProductCreate,
            current_user: User = Depends(require_role("admin", "manager"))
        ):
            ...
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {', '.join(allowed_roles)}"
            )
        return current_user

    return role_checker


# Type aliases pour annotations
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
ManagerUser = Annotated[User, Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))]
