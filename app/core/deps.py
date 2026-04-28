"""Dependencies FastAPI pour injection dans les endpoints."""
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Annotated, Any, Optional, Protocol, Union, runtime_checkable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_async_db
from app.core.security import decode_token, decode_access_token
from app.core.exceptions import TokenExpired, TokenInvalid
from app.services.token import token_service
from app.constants import AuthEndpoints, ErrorMessages, PASSWORD_CHANGE_ALLOWED, SecurityHeaders, TokenType
from app.core.permissions import Permission, Scope, get_effective_permissions_cached
from app.services.rbac import get_role_scopes, ROLE_SCOPES_FALLBACK

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


class UserCompat:
    """Agrégat Account + TenantMembership — drop-in replacement pour User (IAM v2, Lot 8A).

    Expose les mêmes attributs que l'ancien modèle User pour que les endpoints
    v1 continuent de fonctionner sans modification jusqu'au Lot 8C.
    Satisfait le Protocol Principal (tenant_id, principal_type, principal_id, permissions).
    """

    __slots__ = ("_account", "_membership")

    def __init__(self, account: Any, membership: Any) -> None:
        self._account = account
        self._membership = membership

    @property
    def id(self) -> int:
        return self._account.id

    @property
    def tenant_id(self) -> int:
        return self._membership.tenant_id

    @property
    def role(self) -> str:
        return self._membership.role_name

    @role.setter
    def role(self, value: str) -> None:
        self._membership.role_name = value

    @property
    def membership_status(self) -> str:
        return self._membership.status

    @membership_status.setter
    def membership_status(self, value: str) -> None:
        self._membership.status = value

    @property
    def email(self) -> str:
        return self._account.email

    @email.setter
    def email(self, value: str) -> None:
        self._account.email = value

    @property
    def first_name(self) -> str:
        return self._account.first_name

    @first_name.setter
    def first_name(self, value: str) -> None:
        self._account.first_name = value

    @property
    def last_name(self) -> str:
        return self._account.last_name

    @last_name.setter
    def last_name(self, value: str) -> None:
        self._account.last_name = value

    @property
    def full_name(self) -> str:
        return f"{self._account.first_name} {self._account.last_name}".strip()

    @property
    def is_active(self) -> bool:
        return self._account.is_active

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self._account.is_active = value

    @property
    def password_change_required(self) -> bool:
        return self._account.password_change_required

    @password_change_required.setter
    def password_change_required(self, value: bool) -> None:
        self._account.password_change_required = value

    @property
    def hashed_password(self) -> str:
        return self._account.hashed_password

    @hashed_password.setter
    def hashed_password(self, value: str) -> None:
        self._account.hashed_password = value

    @property
    def created_at(self) -> Any:
        return self._account.created_at

    @property
    def updated_at(self) -> Any:
        return self._account.updated_at

    # ── Principal Protocol ────────────────────────────────────────────

    @property
    def principal_type(self) -> str:
        return "user"

    @property
    def principal_id(self) -> str:
        return str(self._account.id)

    @property
    def permissions(self) -> set[str]:
        return set()

    def __repr__(self) -> str:
        return f"<UserCompat(account_id={self._account.id}, tenant_id={self._membership.tenant_id}, role={self._membership.role_name})>"


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    token: str | None = Depends(oauth2_scheme),
) -> UserCompat:
    """Dependency — retourne l'utilisateur connecté (IAM v2) sous forme de UserCompat.

    Extrait Account + TenantMembership depuis les claims JWT (sub=account_id, tid, mid).
    Drop-in replacement pour l'ancien get_current_user() qui lisait la table users (droppée).

    Raises:
        HTTPException 401: Token invalide, expiré, révoqué, compte absent.
        HTTPException 403: Compte inactif, membership suspendu, password_change_required.
    """
    from app.repositories.account import AsyncAccountRepository
    from app.repositories.tenant_membership import AsyncTenantMembershipRepository

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ErrorMessages.INVALID_TOKEN,
        headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
    )

    if token is None:
        raise credentials_exception

    try:
        payload = decode_access_token(token)
    except TokenExpired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.TOKEN_EXPIRED,
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )
    except TokenInvalid:
        raise credentials_exception

    if payload.get("type") != TokenType.ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.INVALID_TOKEN_TYPE,
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )

    # M-02 : token binding verification (IP /24 + User-Agent)
    cbh_token = payload.get("cbh")
    if cbh_token:
        from app.core.security import compute_client_binding_hash
        cbh_expected = compute_client_binding_hash(
            request.client.host if request.client else "",
            request.headers.get("user-agent", ""),
        )
        if cbh_token != cbh_expected:
            logger.warning(
                "Token binding mismatch: sub=%s expected=%s got=%s ip=%s",
                payload.get("sub"), cbh_expected, cbh_token,
                request.client.host if request.client else "?",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="CLIENT_BINDING_MISMATCH",
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )

    sub = payload.get("sub")
    tid = payload.get("tid")
    if sub is None or tid is None:
        raise credentials_exception  # claims sub + tid obligatoires — FAIL-CLOSED

    try:
        account_id = int(sub)
        tenant_id = int(tid)
    except (ValueError, TypeError):
        raise credentials_exception

    access_jti = payload.get("jti")
    if access_jti and await token_service.is_access_blacklisted(access_jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.ACCESS_TOKEN_REVOKED,
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )

    device_id = payload.get("did", "")
    if device_id and (await _handle_revoked_device(device_id)) is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorMessages.DEVICE_REVOKED,
        )

    account = await AsyncAccountRepository(db).get_active_by_id(account_id)
    if account is None:
        raise credentials_exception

    membership_repo = AsyncTenantMembershipRepository(db)
    mid = payload.get("mid")
    if mid is not None:
        try:
            membership = await membership_repo.get_by_id(int(mid))
        except (ValueError, TypeError):
            raise credentials_exception
        if not membership or membership.account_id != account_id or membership.tenant_id != tenant_id:
            raise credentials_exception
    else:
        membership = await membership_repo.get_active(account_id, tenant_id)
        if not membership:
            raise credentials_exception

    if membership.revoked_at is not None or membership.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorMessages.ACCESS_DENIED,
        )

    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorMessages.ACCOUNT_INACTIVE,
        )

    if account.password_change_required and request.url.path not in PASSWORD_CHANGE_ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PASSWORD_CHANGE_REQUIRED",
        )

    # Hardening tenant : si X-Tenant-ID header diffère du JWT tid,
    # vérifier que le compte a un membership actif sur le tenant demandé.
    header_tid = request.headers.get("X-Tenant-ID")
    if header_tid is not None:
        try:
            header_tenant_id = int(header_tid)
        except (ValueError, TypeError):
            header_tenant_id = None

        if header_tenant_id is not None and header_tenant_id != tenant_id:
            cross_membership = await membership_repo.get_active(account_id, header_tenant_id)
            if not cross_membership or cross_membership.revoked_at is not None or cross_membership.status != "active":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="TENANT_MISMATCH: aucun accès au tenant demandé via X-Tenant-ID.",
                )

    user = UserCompat(account=account, membership=membership)

    # P1-01 RLS : injecter tenant_id dans le contexte PostgreSQL
    from app.core.database import set_tenant_context
    set_tenant_context(user.tenant_id)

    return user



async def get_current_principal(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    token: str | None = Depends(oauth2_scheme),
) -> Union[UserCompat, ApiKeyClient]:
    """Dependency dual-mode : extrait le principal depuis JWT ou API key.

    Ordre de resolution:
        1. Header Authorization: Bearer <jwt> -> UserCompat
        2. Header X-API-Key: mk_live_xxx -> ApiKeyClient
        3. Aucun -> 401
    """
    if token:
        return await get_current_user(request=request, db=db, token=token)

    api_key_value = request.headers.get(X_API_KEY_HEADER)
    if api_key_value:
        return await _resolve_api_key_async(api_key_value, db, request)

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

    # Mettre a jour les stats d'utilisation (flush uniquement — commit géré par l'endpoint)
    ip_address = request.client.host if request.client else None
    from app.repositories.api_key import ApiKeyRepository
    repo = ApiKeyRepository(db)
    repo.update_last_used(api_key, ip_address)
    db.flush()

    # F02 fix (B1.S1.T2) : RLS context (chemin sync, parité avec _resolve_api_key_async).
    from app.core.database import set_tenant_context
    set_tenant_context(api_key.tenant_id)
    request.state.api_key_id = api_key.id
    request.state.tenant_id = api_key.tenant_id

    return ApiKeyClient(
        _tenant_id=api_key.tenant_id,
        _api_key_id=api_key.id,
        api_key_name=api_key.name,
        scopes=set(api_key.scopes),
    )


def require_permission(*permissions: Permission):
    """Dependency factory : verifie que le principal a TOUTES les permissions requises.

    Fonctionne en dual-mode : User (role RBAC) ET ApiKeyClient (scopes).

    Args:
        permissions: une ou plusieurs Permission requises (toutes doivent etre satisfaites).

    Returns:
        Un dependency FastAPI qui retourne le principal authentifie si autorise.

    Raises:
        HTTPException 401: si aucune auth valide.
        HTTPException 403: si au moins une permission manque.
    """
    def permission_checker(
        principal: Union[UserCompat, ApiKeyClient] = Depends(get_current_principal),
    ) -> Union[UserCompat, ApiKeyClient]:
        if isinstance(principal, ApiKeyClient):
            required = {p.value for p in permissions}
            missing = required - principal.permissions
        else:
            user_perms = get_effective_permissions_cached(principal.role)
            missing = set(permissions) - user_perms

        if missing:
            missing_str = ", ".join(
                p if isinstance(p, str) else p.value for p in sorted(missing, key=str)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissions manquantes: {missing_str}",
            )
        return principal

    return permission_checker



# ── Type aliases pour annotations ────────────────────────────────────────

CurrentUser = Annotated[UserCompat, Depends(get_current_user)]
CurrentPrincipal = Annotated[Union[UserCompat, ApiKeyClient], Depends(get_current_principal)]

# Permission-based aliases
ProductWriter = Annotated[UserCompat, Depends(require_permission(Permission.PRODUCTS_WRITE))]
ProductDeleter = Annotated[UserCompat, Depends(require_permission(Permission.PRODUCTS_DELETE))]
CategoryWriter = Annotated[UserCompat, Depends(require_permission(Permission.CATEGORIES_WRITE))]
BundleWriter = Annotated[UserCompat, Depends(require_permission(Permission.BUNDLES_WRITE))]
ReservationWriter = Annotated[UserCompat, Depends(require_permission(Permission.RESERVATIONS_WRITE))]
InvoiceWriter = Annotated[UserCompat, Depends(require_permission(Permission.INVOICES_WRITE))]
CustomerWriter = Annotated[UserCompat, Depends(require_permission(Permission.CUSTOMERS_WRITE))]
InventoryWriter = Annotated[UserCompat, Depends(require_permission(Permission.INVENTORY_WRITE))]
UserReader = Annotated[UserCompat, Depends(require_permission(Permission.USERS_READ))]
UserWriter = Annotated[UserCompat, Depends(require_permission(Permission.USERS_WRITE))]
UserAdmin = Annotated[UserCompat, Depends(require_permission(Permission.USERS_ADMIN))]
SessionAdmin = Annotated[UserCompat, Depends(require_permission(Permission.SESSIONS_ADMIN))]
AuditReader = Annotated[UserCompat, Depends(require_permission(Permission.AUDIT_READ))]

# API Keys aliases
ApiKeyAdmin = Annotated[UserCompat, Depends(require_permission(Permission.API_KEYS_WRITE))]
FeatureAdmin = Annotated[UserCompat, Depends(require_permission(Permission.FEATURES_WRITE))]

# VPN aliases
VpnReader = Annotated[UserCompat, Depends(require_permission(Permission.VPN_READ))]
VpnWriter = Annotated[UserCompat, Depends(require_permission(Permission.VPN_WRITE))]
VpnAdmin = Annotated[UserCompat, Depends(require_permission(Permission.VPN_ADMIN))]


# ── Async dependencies (migration en cours — FastAPI async handlers) ──────────

# Seuils d'escalation pour devices révoqués (§7.1 S-08.1)
_REVOKED_DEVICE_WARN     = 5
_REVOKED_DEVICE_CRITICAL = 10


async def _handle_revoked_device(device_id: str) -> Optional[int]:
    """Vérifie si le device est révoqué ; si oui, INCR compteur et log.

    Import local de redis_sec pour éviter la circularité au boot.

    Returns:
        Compteur de tentatives si révoqué, None si non révoqué.
    """
    from app.core.redis import redis_sec  # noqa: PLC0415
    if not await redis_sec.is_device_revoked(device_id):
        return None
    count = await redis_sec.incr_revoked_device_attempt(device_id)
    if count >= _REVOKED_DEVICE_CRITICAL:
        logger.critical(
            "SECURITY ALERT: revoked device attempt #%d did=%.8s — investigate immediately",
            count, device_id,
        )
    elif count >= _REVOKED_DEVICE_WARN:
        logger.warning("Revoked device attempt #%d did=%.8s", count, device_id)
    else:
        logger.info("Revoked device attempt #%d did=%.8s", count, device_id)
    return count


# get_current_user est désormais async — alias pour compatibilité des imports existants
get_current_user_async = get_current_user


async def _resolve_api_key_async(
    full_key: str,
    db: AsyncSession,
    request: Request,
) -> ApiKeyClient:
    """Résout une API key en ApiKeyClient (version async)."""
    from app.models.api_key import ApiKey

    key_hash = hashlib.sha256(full_key.encode()).hexdigest()

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active.is_(True),
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.API_KEY_INVALID,
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )

    # Vérifier expiration
    if api_key.expires_at is not None:
        now = datetime.now(timezone.utc)
        expires = api_key.expires_at
        if expires.tzinfo is None:
            from datetime import timezone as tz
            expires = expires.replace(tzinfo=tz.utc)
        if now > expires:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.API_KEY_EXPIRED,
                headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
            )

    # Mettre à jour stats d'utilisation
    ip_address = request.client.host if request.client else None
    api_key.last_used_at = datetime.now(timezone.utc)
    api_key.last_used_ip = ip_address
    api_key.usage_count = (api_key.usage_count or 0) + 1
    await db.flush()

    # F02 fix (B1.S1.T2) : RLS context — sinon les requêtes via ApiKey
    # contournent les policies tenant_id côté DB une fois RLS activée (B1.S2).
    # Symétrie avec get_current_user (chemin JWT, ligne 349-350).
    from app.core.database import set_tenant_context
    set_tenant_context(api_key.tenant_id)
    request.state.api_key_id = api_key.id
    request.state.tenant_id = api_key.tenant_id

    return ApiKeyClient(
        _tenant_id=api_key.tenant_id,
        _api_key_id=api_key.id,
        api_key_name=api_key.name,
        scopes=set(api_key.scopes),
    )


# get_current_principal est désormais async — alias pour compatibilité des imports existants
get_current_principal_async = get_current_principal


def require_permission_async(*permissions: Permission):
    """Dependency factory async : vérifie que le principal a toutes les permissions."""
    async def permission_checker_async(
        principal: Union[UserCompat, ApiKeyClient] = Depends(get_current_principal_async),
    ) -> Union[UserCompat, ApiKeyClient]:
        if isinstance(principal, ApiKeyClient):
            required = {p.value for p in permissions}
            missing = required - principal.permissions
        else:
            user_perms = get_effective_permissions_cached(principal.role)
            missing = set(permissions) - user_perms

        if missing:
            missing_str = ", ".join(
                p if isinstance(p, str) else p.value for p in sorted(missing, key=str)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissions manquantes: {missing_str}",
            )
        return principal

    return permission_checker_async


# ═══════════════════════════════════════════════════════════════════════
# NOUVEAU SYSTEME v3 — require_scope() (CaroCorp §6.4, §6.6)
# Utilise les 62 scopes de Scope + ROLE_SCOPES_FALLBACK / get_role_scopes()
# ═══════════════════════════════════════════════════════════════════════

def _get_principal_scopes(principal: Union[UserCompat, ApiKeyClient], jwt_scopes: list[str]) -> set[str]:
    """Resout les scopes effectifs d'un principal.

    Ordre de priorite :
        1. Scopes embarques dans le JWT (claim "scopes") si presents
        2. Fallback statique ROLE_SCOPES_FALLBACK (dict memoire, O(1))
           — utilise uniquement si le JWT ne contient pas de scopes
           (cas rare : anciens tokens pre-v3 ou tokens de test)
    """
    if isinstance(principal, ApiKeyClient):
        return set(principal.scopes)

    # Scopes JWT (embeds au login depuis auth_role_scopes)
    if jwt_scopes:
        return set(jwt_scopes)

    # P1-04 : fallback avec alerte — JWT scopes absents
    logger.warning(
        "RBAC fallback: JWT scopes absents user=%s role=%s — utilisation ROLE_SCOPES_FALLBACK",
        getattr(principal, 'id', '?'), principal.role,
    )
    return set(ROLE_SCOPES_FALLBACK.get(principal.role, []))


def require_scope(*scopes):
    """Dependency factory v3 : verifie que le principal a TOUS les scopes requis.

    Compatible JWT-scopes (claim "scopes") ET fallback role-based.
    Fonctionne en dual-mode : User ET ApiKeyClient.

    Args:
        scopes: un ou plusieurs Scope enum (pas de string — P1-05 typo protection)

    Usage :
        from app.core.deps import require_scope
        from app.core.permissions import Scope

        @router.get("/reservations")
        def list_reservations(
            principal = Depends(require_scope(Scope.RESERVATIONS_READ))
        ): ...
    """
    # P1-05 : valider que chaque scope est un Scope enum (pas de string typo)
    for s in scopes:
        if not isinstance(s, Scope):
            raise TypeError(
                f"require_scope attend Scope enum, recu {type(s).__name__}: {s!r}. "
                f"Utiliser Scope.XXXX au lieu d'une string."
            )
    required = set(s.value if isinstance(s, Scope) else s for s in scopes)

    def scope_checker(
        request: Request,
        principal: Union[UserCompat, ApiKeyClient] = Depends(get_current_principal),
    ) -> Union[UserCompat, ApiKeyClient]:
        # Extraire les scopes JWT si disponibles (claim "scopes" dans request.state)
        jwt_scopes: list[str] = []
        if hasattr(request.state, "jwt_scopes"):
            jwt_scopes = request.state.jwt_scopes or []

        user_scopes = _get_principal_scopes(principal, jwt_scopes)
        missing = required - user_scopes

        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "INSUFFICIENT_SCOPES",
                    "required": sorted(required),
                    "missing": sorted(missing),
                },
            )
        return principal

    return scope_checker


def require_scope_async(*scopes: str):
    """Dependency factory v3 async : verifie que le principal a TOUS les scopes requis."""
    required = set(scopes)

    async def scope_checker_async(
        request: Request,
        principal: Union[UserCompat, ApiKeyClient] = Depends(get_current_principal_async),
    ) -> Union[UserCompat, ApiKeyClient]:
        jwt_scopes: list[str] = []
        if hasattr(request.state, "jwt_scopes"):
            jwt_scopes = request.state.jwt_scopes or []

        user_scopes = _get_principal_scopes(principal, jwt_scopes)
        missing = required - user_scopes

        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "INSUFFICIENT_SCOPES",
                    "required": sorted(required),
                    "missing": sorted(missing),
                },
            )
        return principal

    return scope_checker_async


def require_scope_user(*scopes: str):
    """Dependency factory v3 User-only : vérifie les scopes ET garantit un User humain.

    Contrairement à require_scope_async (qui accepte User ET ApiKeyClient),
    cette variante n'accepte que les Users authentifiés par JWT.
    Nécessaire pour les services qui utilisent admin_user.id (ex: UserService).

    Args:
        scopes: un ou plusieurs scopes requis (format "resource:action")
    """
    required = set(scopes)

    async def checker(
        request: Request,
        user: UserCompat = Depends(get_current_user_async),
    ) -> UserCompat:
        jwt_scopes: list[str] = getattr(request.state, "jwt_scopes", None) or []
        user_scopes = set(jwt_scopes) if jwt_scopes else set(await get_role_scopes(user.role, None))
        missing = required - user_scopes
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "INSUFFICIENT_SCOPES",
                    "required": sorted(required),
                    "missing": sorted(missing),
                },
            )
        return user

    return checker


async def require_stepup(
    request: Request,
    current_user: UserCompat = Depends(get_current_user_async),
) -> None:
    """Dependency FastAPI — vérifie qu'un MFA step-up valide existe pour cette session.

    Extrait le device_id (claim 'did') depuis le JWT Bearer et valide
    que l'utilisateur a réalisé un step-up MFA récent (fenêtre 15 min).

    Raises:
        HTTPException 403: STEP_UP_REQUIRED si step-up absent ou expiré.
    """
    from app.services.mfa import mfa_service

    device_id = ""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = decode_access_token(auth_header[len("Bearer "):])
            device_id = payload.get("did", "")
        except Exception:
            pass

    if not await mfa_service.is_stepup_valid(current_user.id, device_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "STEP_UP_REQUIRED",
                "message": "MFA step-up required for this action",
            },
        )


# ── Type aliases v3 (scope-based) ────────────────────────────────────────

# Reservations
ReservationReader = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.RESERVATIONS_READ))]
ReservationWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.RESERVATIONS_WRITE))]
ReservationDeleterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.RESERVATIONS_DELETE))]

# Stock
StockReader = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.STOCK_READ))]
StockWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.STOCK_WRITE))]
StockAdjuster = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.STOCK_ADJUST))]

# Utilisateurs — Union (principal quelconque)
UserReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.USERS_READ))]
UserWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.USERS_WRITE))]
UserManager = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.USERS_MANAGE))]
UserDeleter = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.USERS_DELETE))]

# Utilisateurs — User-only (endpoints dont le service utilise admin_user.id)
UserReaderScope  = Annotated[UserCompat, Depends(require_scope_user(Scope.USERS_READ))]
UserWriterScope  = Annotated[UserCompat, Depends(require_scope_user(Scope.USERS_WRITE))]
UserManagerScope = Annotated[UserCompat, Depends(require_scope_user(Scope.USERS_MANAGE))]
UserDeleterScope = Annotated[UserCompat, Depends(require_scope_user(Scope.USERS_DELETE))]

# Sessions & Devices
SessionReader = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.SESSIONS_READ))]
SessionRevoker = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.SESSIONS_REVOKE))]
DeviceReader = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.DEVICES_READ))]
DeviceRevoker = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.DEVICES_REVOKE))]

# Audit
AuditReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.AUDIT_READ))]
AuditVerifier = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.AUDIT_VERIFY))]

# Facturation & Config
BillingReader = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.BILLING_READ))]
BillingManager = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.BILLING_MANAGE))]
ConfigReader = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.CONFIG_READ))]
ConfigWriter = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.CONFIG_WRITE))]

# Rapports
ReportReader = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.REPORTS_READ))]
ReportExporter = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.REPORTS_EXPORT))]

# ── Aliases v3 metier (M5) ────────────────────────────────────────────────

# Produits
ProductReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.PRODUCTS_READ))]
ProductWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.PRODUCTS_WRITE))]
ProductDeleterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.PRODUCTS_DELETE))]

# Categories
CategoryReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.CATEGORIES_READ))]
CategoryWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.CATEGORIES_WRITE))]
CategoryDeleterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.CATEGORIES_DELETE))]

# Bundles
BundleReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.BUNDLES_READ))]
BundleWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.BUNDLES_WRITE))]
BundleDeleterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.BUNDLES_DELETE))]

# Clients
CustomerReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.CUSTOMERS_READ))]
CustomerWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.CUSTOMERS_WRITE))]
CustomerDeleterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.CUSTOMERS_DELETE))]

# Factures
InvoiceReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.INVOICES_READ))]
InvoiceWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.INVOICES_WRITE))]

# Devis
DevisReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.DEVIS_READ))]
DevisWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.DEVIS_WRITE))]

# Ventes directes
VenteReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.VENTES_READ))]
VenteWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.VENTES_WRITE))]

# Evenements
EvenementReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.EVENEMENTS_READ))]
EvenementWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.EVENEMENTS_WRITE))]

# Relances
RelanceReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.RELANCES_READ))]
RelanceWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.RELANCES_WRITE))]

# Tarification
PricingReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.PRICING_READ))]
PricingWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.PRICING_WRITE))]

# Fournisseurs
SupplierReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.SUPPLIERS_READ))]
SupplierWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.SUPPLIERS_WRITE))]

# VPN WireGuard
VpnReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.VPN_READ))]
VpnWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.VPN_WRITE))]
VpnAdminV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.VPN_ADMIN))]

# Parametres tenant
SettingsReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.SETTINGS_READ))]
SettingsWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.SETTINGS_WRITE))]

# Cles API
ApiKeyReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.API_KEYS_READ))]
ApiKeyWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.API_KEYS_WRITE))]
ApiKeyDeleterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.API_KEYS_DELETE))]

# Feature flags
FeatureReaderV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.FEATURES_READ))]
FeatureWriterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.FEATURES_WRITE))]
FeatureDeleterV3 = Annotated[Union[UserCompat, ApiKeyClient], Depends(require_scope(Scope.FEATURES_DELETE))]


# ═══════════════════════════════════════════════════════════════════════
# IAM v2 — get_current_account / get_current_membership
# Nouvelles dépendances pour les endpoints IAM v2.
# Les endpoints v1 continuent d'utiliser get_current_user jusqu'au Lot 8.
# ═══════════════════════════════════════════════════════════════════════

async def get_current_account(
    db: AsyncSession = Depends(get_async_db),
    token: str | None = Depends(oauth2_scheme),
):
    """Dependency IAM v2 — retourne l'Account actif depuis le JWT.

    Vérifie : signature, type, expiration, blacklist JTI, device révoqué,
    compte actif, password_change_required.

    Raises:
        HTTPException 401: Token invalide, expiré, révoqué, compte absent.
        HTTPException 403: Compte inactif ou changement de mot de passe requis.
    """
    from app.models.account import Account
    from app.repositories.account import AsyncAccountRepository

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ErrorMessages.INVALID_TOKEN,
        headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
    )

    if token is None:
        raise credentials_exception

    try:
        payload = decode_access_token(token)
    except TokenExpired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.TOKEN_EXPIRED,
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )
    except TokenInvalid:
        raise credentials_exception

    if payload.get("type") != TokenType.ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.INVALID_TOKEN_TYPE,
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )

    sub = payload.get("sub")
    if sub is None:
        raise credentials_exception

    try:
        account_id = int(sub)
    except (ValueError, TypeError):
        raise credentials_exception

    access_jti = payload.get("jti")
    if access_jti and await token_service.is_access_blacklisted(access_jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.ACCESS_TOKEN_REVOKED,
            headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
        )

    device_id = payload.get("did", "")
    if device_id and (await _handle_revoked_device(device_id)) is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorMessages.DEVICE_REVOKED,
        )

    account = await AsyncAccountRepository(db).get_active_by_id(account_id)
    if account is None:
        raise credentials_exception

    return account


async def get_current_membership(
    db: AsyncSession = Depends(get_async_db),
    token: str | None = Depends(oauth2_scheme),
):
    """Dependency IAM v2 — retourne le TenantMembership actif depuis le JWT.

    Utilise le claim 'mid' (membership_id) pour un lookup direct.
    Valide que le membership est actif et que tenant_id correspond au claim 'tid'.

    Raises:
        HTTPException 401: Token invalide ou membership absent/révoqué.
        HTTPException 403: Membership suspendu ou révoqué.
    """
    from app.models.account import Account
    from app.repositories.account import AsyncAccountRepository
    from app.repositories.tenant_membership import AsyncTenantMembershipRepository

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ErrorMessages.INVALID_TOKEN,
        headers={SecurityHeaders.WWW_AUTHENTICATE: SecurityHeaders.BEARER_SCHEME},
    )

    if token is None:
        raise credentials_exception

    try:
        payload = decode_access_token(token)
    except (TokenExpired, TokenInvalid):
        raise credentials_exception

    if payload.get("type") != TokenType.ACCESS:
        raise credentials_exception

    sub = payload.get("sub")
    tid = payload.get("tid")
    mid = payload.get("mid")

    if not sub or not tid:
        raise credentials_exception

    try:
        account_id = int(sub)
        tenant_id = int(tid)
    except (ValueError, TypeError):
        raise credentials_exception

    membership_repo = AsyncTenantMembershipRepository(db)

    if mid is not None:
        try:
            membership_id = int(mid)
        except (ValueError, TypeError):
            raise credentials_exception
        membership = await membership_repo.get_by_id(membership_id)
        if not membership or membership.account_id != account_id or membership.tenant_id != tenant_id:
            raise credentials_exception
    else:
        # Fallback : résolution par (account_id, tenant_id) — tokens sans claim mid
        membership = await membership_repo.get_active(account_id, tenant_id)
        if not membership:
            raise credentials_exception

    if membership.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorMessages.ACCESS_DENIED,
        )

    if membership.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorMessages.ACCESS_DENIED,
        )

    return membership


# Type aliases IAM v2
CurrentAccount = Annotated[object, Depends(get_current_account)]
CurrentMembership = Annotated[object, Depends(get_current_membership)]
