"""Dependencies FastAPI pour injection dans les endpoints."""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import TokenExpired, TokenInvalid
from app.models.user import User
from app.services.token import token_service
from app.constants import AuthEndpoints, ErrorMessages, SecurityHeaders, TokenType, UserRole
from app.core.permissions import Permission, get_effective_permissions_cached


# OAuth2 scheme pour extraction du token Bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=AuthEndpoints.LOGIN)


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """Dependency pour obtenir l'utilisateur connecté depuis le JWT.

    Raises:
        HTTPException 401: Si token invalide, expiré, ou user non trouvé
        HTTPException 403: Si compte inactif
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ErrorMessages.INVALID_TOKEN,
        headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
    )

    # Décoder le token — lève TokenExpired ou TokenInvalid
    try:
        payload = decode_token(token)
    except TokenExpired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.TOKEN_EXPIRED,
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )
    except TokenInvalid:
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

    # Vérifier blacklist access token (logout → JTI blacklisté dans Redis)
    access_jti = payload.get("jti")
    if access_jti and token_service.is_access_blacklisted(access_jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.ACCESS_TOKEN_REVOKED,
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )

    # Vérifier cohérence tenant_id JWT vs DB (fix M23 — anti cross-tenant)
    jwt_tenant_id = payload.get("tenant_id")
    if jwt_tenant_id is not None and user.tenant_id != jwt_tenant_id:
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

    DEPRECATED: Utiliser require_permission() pour des controles granulaires.
    Conserve pour retrocompatibilite.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {', '.join(allowed_roles)}"
            )
        return current_user

    return role_checker


def require_permission(*permissions: Permission):
    """Dependency factory : verifie que l'utilisateur a TOUTES les permissions requises.

    Utilise le systeme RBAC hierarchique : les permissions sont resolues
    via l'heritage de role (staff < manager < admin).

    Args:
        permissions: une ou plusieurs Permission requises (toutes doivent etre satisfaites).

    Returns:
        Un dependency FastAPI qui retourne le User authentifie si autorise.

    Raises:
        HTTPException 403: si au moins une permission manque.
    """
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        user_perms = get_effective_permissions_cached(current_user.role)
        missing = set(permissions) - user_perms
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissions manquantes: {', '.join(p.value for p in missing)}"
            )
        return current_user

    return permission_checker


# Type aliases pour annotations
CurrentUser = Annotated[User, Depends(get_current_user)]

# Legacy (role-based) — conserves pour retrocompatibilite
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
ManagerUser = Annotated[User, Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))]

# Permission-based aliases (a privilegier)
ProductWriter = Annotated[User, Depends(require_permission(Permission.PRODUCTS_WRITE))]
ProductDeleter = Annotated[User, Depends(require_permission(Permission.PRODUCTS_DELETE))]
CategoryWriter = Annotated[User, Depends(require_permission(Permission.CATEGORIES_WRITE))]
BundleWriter = Annotated[User, Depends(require_permission(Permission.BUNDLES_WRITE))]
ReservationWriter = Annotated[User, Depends(require_permission(Permission.RESERVATIONS_WRITE))]
InvoiceWriter = Annotated[User, Depends(require_permission(Permission.INVOICES_WRITE))]
CustomerWriter = Annotated[User, Depends(require_permission(Permission.CUSTOMERS_WRITE))]
InventoryWriter = Annotated[User, Depends(require_permission(Permission.INVENTORY_WRITE))]
UserAdmin = Annotated[User, Depends(require_permission(Permission.USERS_ADMIN))]
SessionAdmin = Annotated[User, Depends(require_permission(Permission.SESSIONS_ADMIN))]
AuditReader = Annotated[User, Depends(require_permission(Permission.AUDIT_READ))]
