"""Service RBAC — resolution des scopes par role (CaroCorp §6.1-6.7).

Architecture :
    - Source de verite : table auth_role_scopes en DB
    - Cache Redis-CACHE (rbac:scopes:{role_name}) TTL 5 min
    - Fallback statique si Redis + DB indisponibles (FAIL-OPEN)

Scopes dans le JWT (§6.7) :
    Calcules au login, embarques dans le claim "scopes".
    Pas de requete DB par requete API — O(1) via JWT.
"""
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_cache

logger = logging.getLogger(__name__)

# Hierarchie des roles (level 0 = plus eleve, §6.5)
ROLE_LEVELS: dict[str, int] = {
    "super_admin":  0,
    "platform_ops": 1,
    "tenant_admin": 2,
    "manager":      3,
    "staff":        4,
    "viewer":       5,
}

# Matrice role → scopes — CaroCorp §6.3
# Source de verite = auth_role_scopes en DB.
# Ce fallback est utilise si DB et Redis sont simultanement indisponibles.
ROLE_SCOPES_FALLBACK: dict[str, list[str]] = {
    "super_admin": [
        # Infrastructure v3 (25 scopes)
        "reservations:read", "reservations:write", "reservations:delete",
        "stock:read", "stock:write", "stock:adjust",
        "deposits:read", "deposits:write", "deposits:manage",
        "users:read", "users:write", "users:manage", "users:delete",
        "sessions:read", "sessions:revoke",
        "devices:read", "devices:revoke",
        "audit:read", "audit:verify",
        "billing:read", "billing:manage",
        "config:read", "config:write",
        "reports:read", "reports:export",
        # Metier M5 (37 scopes)
        "products:read", "products:write", "products:delete",
        "categories:read", "categories:write", "categories:delete",
        "bundles:read", "bundles:write", "bundles:delete",
        "customers:read", "customers:write", "customers:delete",
        "invoices:read", "invoices:write",
        "devis:read", "devis:write",
        "ventes:read", "ventes:write",
        "evenements:read", "evenements:write",
        "relances:read", "relances:write",
        "pricing:read", "pricing:write",
        "suppliers:read", "suppliers:write",
        "vpn:read", "vpn:write", "vpn:admin",
        "settings:read", "settings:write",
        "api_keys:read", "api_keys:write", "api_keys:delete",
        "features:read", "features:write", "features:delete",
        # Restaurant V2
        "restaurant:read", "restaurant:write",
        # Épicerie V2
        "epicerie:read", "epicerie:write",
    ],
    "platform_ops": [
        # Infrastructure uniquement — monitoring cross-tenant (§6.3)
        "sessions:read",
        "devices:read",
        "audit:read", "audit:verify",
        "config:read",
    ],
    "tenant_admin": [
        # Infrastructure v3 (24 scopes — audit:verify exclu)
        "reservations:read", "reservations:write", "reservations:delete",
        "stock:read", "stock:write", "stock:adjust",
        "deposits:read", "deposits:write", "deposits:manage",
        "users:read", "users:write", "users:manage", "users:delete",
        "sessions:read", "sessions:revoke",
        "devices:read", "devices:revoke",
        "audit:read",
        "billing:read", "billing:manage",
        "config:read", "config:write",
        "reports:read", "reports:export",
        # Metier M5 (36 scopes — vpn:admin exclu)
        "products:read", "products:write", "products:delete",
        "categories:read", "categories:write", "categories:delete",
        "bundles:read", "bundles:write", "bundles:delete",
        "customers:read", "customers:write", "customers:delete",
        "invoices:read", "invoices:write",
        "devis:read", "devis:write",
        "ventes:read", "ventes:write",
        "evenements:read", "evenements:write",
        "relances:read", "relances:write",
        "pricing:read", "pricing:write",
        "suppliers:read", "suppliers:write",
        "vpn:read", "vpn:write",
        "settings:read", "settings:write",
        "api_keys:read", "api_keys:write", "api_keys:delete",
        "features:read", "features:write", "features:delete",
        # Restaurant V2
        "restaurant:read", "restaurant:write",
        # Épicerie V2
        "epicerie:read", "epicerie:write",
        # Fidélité
        "loyalty:read", "loyalty:write", "loyalty:manage",
    ],
    "manager": [
        # Infrastructure v3 (14 scopes)
        "reservations:read", "reservations:write", "reservations:delete",
        "stock:read", "stock:write", "stock:adjust",
        "deposits:read", "deposits:write",
        "users:read",
        "sessions:read",
        "devices:read",
        "config:read",
        "reports:read", "reports:export",
        # Metier M5 (22 scopes)
        "products:read", "categories:read", "bundles:read",
        "customers:read", "customers:write", "customers:delete",
        "invoices:read", "invoices:write",
        "devis:read", "devis:write",
        "ventes:read", "ventes:write",
        "evenements:read", "evenements:write",
        "relances:read", "relances:write",
        "pricing:read", "pricing:write",
        "suppliers:read", "suppliers:write",
        "vpn:read",
        "features:read",
        # Restaurant V2
        "restaurant:read", "restaurant:write",
        # Épicerie V2
        "epicerie:read", "epicerie:write",
        # Fidélité
        "loyalty:read", "loyalty:write",
    ],
    "staff": [
        # Infrastructure v3 (6 scopes)
        "reservations:read", "reservations:write",
        "stock:read", "stock:write",
        "deposits:read",
        "reports:read",
        # Metier M5 (15 scopes)
        "products:read", "categories:read", "bundles:read",
        "customers:read", "customers:write",
        "invoices:read", "invoices:write",
        "devis:read",
        "ventes:read", "ventes:write",
        "evenements:read", "evenements:write",
        "relances:read",
        "pricing:read",
        "suppliers:read",
        # Restaurant V2
        "restaurant:read",
        # Épicerie V2
        "epicerie:read",
        # Fidélité
        "loyalty:read", "loyalty:write",
    ],
    "viewer": [
        # Infrastructure v3 (4 scopes)
        "reservations:read",
        "stock:read",
        "deposits:read",
        "reports:read",
        # Metier M5 (8 scopes)
        "products:read", "categories:read", "bundles:read",
        "customers:read",
        "invoices:read",
        "devis:read",
        "ventes:read",
        "evenements:read",
    ],
}

# Backward-compat: role "admin" (ancien systeme 3 niveaux) = tenant_admin v3
ROLE_SCOPES_FALLBACK["admin"] = list(ROLE_SCOPES_FALLBACK["tenant_admin"])

RBAC_CACHE_TTL = 300  # 5 minutes (§6.7)


async def get_role_scopes(
    role_name: str,
    db: Optional[AsyncSession] = None,
) -> list[str]:
    """Recupere les scopes d'un role : Redis-CACHE → DB → fallback statique.

    Args:
        role_name: Nom du role (ex: "manager")
        db: Session async SQLAlchemy (optionnel — fallback si absent)

    Returns:
        Liste de scopes triee (ex: ["reservations:read", "stock:read"])
    """
    # 1. Cache Redis-CACHE (FAIL-OPEN : Redis down → continuer)
    cached = await redis_cache.get_cached_scopes(role_name)
    if cached is not None:
        return cached

    # 2. DB (source de verite)
    if db is not None:
        try:
            result = await db.execute(
                text(
                    "SELECT scope_name FROM auth_role_scopes "
                    "WHERE role_name = :role_name ORDER BY scope_name"
                ),
                {"role_name": role_name},
            )
            rows = result.fetchall()
            if rows:
                scopes = [row[0] for row in rows]
                await redis_cache.set_cached_scopes(role_name, scopes, RBAC_CACHE_TTL)
                return scopes
        except Exception:
            logger.warning("DB query failed for role scopes: role=%s", role_name)

    # 3. Fallback statique (DB + Redis down — FAIL-OPEN)
    scopes = list(ROLE_SCOPES_FALLBACK.get(role_name, []))
    if scopes:
        await redis_cache.set_cached_scopes(role_name, scopes, RBAC_CACHE_TTL)
    return scopes



def has_scope(user_scopes: list[str] | set[str], scope: str) -> bool:
    """Verifie si un scope est dans les scopes de l'utilisateur."""
    return scope in user_scopes


def can_manage_role(executor_role: str, target_role: str) -> bool:
    """Verifie si executor peut gerer target (anti-escalade §6.4).

    Regle : un user ne peut gerer que des roles de level > le sien.
    (level plus bas = plus de privileges, donc on verifie executor.level < target.level)
    """
    executor_level = ROLE_LEVELS.get(executor_role, 99)
    target_level = ROLE_LEVELS.get(target_role, 99)
    return executor_level < target_level


async def invalidate_role_cache(role_name: str) -> None:
    """Invalide le cache Redis d'un role (apres modification en DB)."""
    await redis_cache.invalidate_cached_scopes(role_name)
    logger.info("RBAC cache invalidated for role: %s", role_name)
