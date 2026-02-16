"""Dependencies FastAPI pour injection dans les endpoints."""
import logging
from dataclasses import dataclass, field
from typing import Annotated, Protocol, Union, runtime_checkable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import TokenExpired, TokenInvalid
from app.models.user import User
from app.services.token import token_service
from app.constants import AuthEndpoints, ErrorMessages, SecurityHeaders, TokenType, UserRole
from app.core.permissions import Permission, get_effective_permissions_cached

logger = logging.getLogger(__name__)

# Header pour API keys
X_API_KEY_HEADER = "X-API-Key"

# OAuth2 scheme pour extraction du token Bearer (auto_error=False pour dual-mode)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=AuthEndpoints.LOGIN, auto_error=False)


# ── Principal Protocol ───────────────────────────────────────────────────

@runtime_checkable
class Principal(Protocol):
    """Interface commune User / ApiKeyClient pour auth dual-mode.

    Tout principal (user ou API key) expose ces attributs pour que
    require_permission() fonctionne de maniere transparente.
    """

    @property
    def tenant_id(self) -> int: ...

    @property
    def principal_type(self) -> str: ...

    @property
    def principal_id(self) -> str: ...

    @property
    def permissions(self) -> set[str]: ...


@dataclass
class ApiKeyClient:
    """Principal representant une API key authentifiee.

    Attributes:
        _tenant_id: ID du tenant de l'API key
        _api_key_id: ID de la cle en base
        api_key_name: Nom descriptif de la cle
        scopes: Permissions accordees (resource:action)
    """

    _tenant_id: int
    _api_key_id: int
    api_key_name: str
    scopes: set[str] = field(default_factory=set)

    @property
    def tenant_id(self) -> int:
        return self._tenant_id

    @property
    def principal_type(self) -> str:
        return "api_key"

    @property
    def principal_id(self) -> str:
        return str(self._api_key_id)

    @property
    def permissions(self) -> set[str]:
        return self.scopes


def get_current_user(
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme)
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

    # auto_error=False → token peut être None si pas de header Authorization
    if token is None:
        raise credentials_exception

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


def get_current_principal(
    request: Request,
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme),
) -> Union[User, ApiKeyClient]:
    """Dependency dual-mode : extrait le principal depuis JWT ou API key.

    Ordre de resolution:
        1. Header Authorization: Bearer <jwt> -> User
        2. Header X-API-Key: mk_live_xxx -> ApiKeyClient
        3. Aucun -> 401

    Args:
        request: FastAPI Request (pour header X-API-Key)
        db: Session DB
        token: JWT token (optionnel via auto_error=False)

    Returns:
        User ou ApiKeyClient

    Raises:
        HTTPException 401: Si aucune auth valide
    """
    # 1. Essayer JWT (Bearer token)
    if token:
        return get_current_user(db=db, token=token)

    # 2. Essayer API key (X-API-Key header)
    api_key_value = request.headers.get(X_API_KEY_HEADER)
    if api_key_value:
        return _resolve_api_key(api_key_value, db, request)

    # 3. Aucune auth
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ErrorMessages.INVALID_TOKEN,
        headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
    )


def _resolve_api_key(
    full_key: str,
    db: Session,
    request: Request,
) -> ApiKeyClient:
    """Resout une API key en ApiKeyClient.

    Args:
        full_key: Valeur du header X-API-Key
        db: Session DB
        request: FastAPI Request (pour IP)

    Returns:
        ApiKeyClient authentifie

    Raises:
        HTTPException 401: Si cle invalide, expiree, ou revoquee
    """
    from app.services.api_key import ApiKeyService

    service = ApiKeyService(db)
    api_key = service.validate_key(full_key)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key invalide ou expiree",
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )

    # Mettre a jour les stats d'utilisation
    ip_address = request.client.host if request.client else None
    from app.repositories.api_key import ApiKeyRepository
    repo = ApiKeyRepository(db)
    repo.update_last_used(api_key, ip_address)
    db.commit()

    return ApiKeyClient(
        _tenant_id=api_key.tenant_id,
        _api_key_id=api_key.id,
        api_key_name=api_key.name,
        scopes=set(api_key.scopes),
    )


def require_permission(*permissions: Permission):
    """Dependency factory : verifie que le principal a TOUTES les permissions requises.

    Fonctionne avec User (role RBAC) et ApiKeyClient (scopes).

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


def require_principal_permission(*permissions: Permission):
    """Dependency factory dual-mode : verifie permissions pour User OU ApiKeyClient.

    Contrairement a require_permission() qui n'accepte que les JWT,
    cette version fonctionne avec get_current_principal (JWT + API key).

    Args:
        permissions: Permissions requises

    Returns:
        Dependency FastAPI retournant User ou ApiKeyClient
    """
    def permission_checker(
        principal: Union[User, ApiKeyClient] = Depends(get_current_principal),
    ) -> Union[User, ApiKeyClient]:
        if isinstance(principal, ApiKeyClient):
            # ApiKeyClient : verifier scopes directement
            required = {p.value for p in permissions}
            missing = required - principal.permissions
        else:
            # User : verifier via role RBAC
            user_perms = get_effective_permissions_cached(principal.role)
            missing = set(permissions) - user_perms

        if missing:
            missing_str = ", ".join(sorted(missing)) if isinstance(missing, set) and all(isinstance(m, str) for m in missing) else ", ".join(p.value if hasattr(p, 'value') else str(p) for p in missing)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissions manquantes: {missing_str}"
            )
        return principal

    return permission_checker


# ── Type aliases pour annotations ────────────────────────────────────────

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentPrincipal = Annotated[Union[User, ApiKeyClient], Depends(get_current_principal)]

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
UserReader = Annotated[User, Depends(require_permission(Permission.USERS_READ))]
UserWriter = Annotated[User, Depends(require_permission(Permission.USERS_WRITE))]
UserAdmin = Annotated[User, Depends(require_permission(Permission.USERS_ADMIN))]
SessionAdmin = Annotated[User, Depends(require_permission(Permission.SESSIONS_ADMIN))]
AuditReader = Annotated[User, Depends(require_permission(Permission.AUDIT_READ))]

# API Keys aliases
ApiKeyAdmin = Annotated[User, Depends(require_permission(Permission.API_KEYS_WRITE))]
FeatureAdmin = Annotated[User, Depends(require_permission(Permission.FEATURES_WRITE))]

# VPN aliases
VpnReader = Annotated[User, Depends(require_permission(Permission.VPN_READ))]
VpnWriter = Annotated[User, Depends(require_permission(Permission.VPN_WRITE))]
VpnAdmin = Annotated[User, Depends(require_permission(Permission.VPN_ADMIN))]
