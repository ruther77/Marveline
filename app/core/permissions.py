"""
Systeme de permissions RBAC hierarchique.

Permissions granulaires au format resource:action.
Les roles heritent des permissions des roles inferieurs :
  staff < manager < admin

Usage:
    from app.core.permissions import Permission, has_permission, get_effective_permissions

    # Verifier une permission
    has_permission("manager", Permission.PRODUCTS_READ)  # True (herite de staff)
    has_permission("staff", Permission.PRODUCTS_WRITE)    # False (admin only)

    # Obtenir toutes les permissions d'un role
    perms = get_effective_permissions("admin")  # set de toutes les permissions
"""

from enum import Enum


class Permission(str, Enum):
    """Permissions granulaires format resource:action."""

    # Products
    PRODUCTS_READ = "products:read"
    PRODUCTS_WRITE = "products:write"
    PRODUCTS_DELETE = "products:delete"

    # Categories
    CATEGORIES_READ = "categories:read"
    CATEGORIES_WRITE = "categories:write"
    CATEGORIES_DELETE = "categories:delete"

    # Bundles
    BUNDLES_READ = "bundles:read"
    BUNDLES_WRITE = "bundles:write"
    BUNDLES_DELETE = "bundles:delete"

    # Reservations
    RESERVATIONS_READ = "reservations:read"
    RESERVATIONS_WRITE = "reservations:write"
    RESERVATIONS_DELETE = "reservations:delete"

    # Invoices
    INVOICES_READ = "invoices:read"
    INVOICES_WRITE = "invoices:write"

    # Customers
    CUSTOMERS_READ = "customers:read"
    CUSTOMERS_WRITE = "customers:write"
    CUSTOMERS_DELETE = "customers:delete"

    # Inventory
    INVENTORY_READ = "inventory:read"
    INVENTORY_WRITE = "inventory:write"

    # Users
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"
    USERS_ADMIN = "users:admin"

    # Sessions
    SESSIONS_READ = "sessions:read"
    SESSIONS_ADMIN = "sessions:admin"

    # Audit
    AUDIT_READ = "audit:read"

    # API Keys
    API_KEYS_READ = "api_keys:read"
    API_KEYS_WRITE = "api_keys:write"
    API_KEYS_DELETE = "api_keys:delete"

    # Feature Flags
    FEATURES_READ = "features:read"
    FEATURES_WRITE = "features:write"
    FEATURES_DELETE = "features:delete"

    # VPN (WireGuard)
    VPN_READ = "vpn:read"
    VPN_WRITE = "vpn:write"
    VPN_ADMIN = "vpn:admin"

    # Health
    HEALTH_READ = "health:read"


# Ordre hierarchique : index croissant = plus de privileges
ROLE_HIERARCHY: list[str] = ["staff", "manager", "admin"]

# Permissions DELTA par role (chaque role ajoute ses permissions propres)
ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "staff": {
        Permission.PRODUCTS_READ,
        Permission.CATEGORIES_READ,
        Permission.BUNDLES_READ,
        Permission.RESERVATIONS_READ,
        Permission.INVOICES_READ,
        Permission.CUSTOMERS_READ,
        Permission.INVENTORY_READ,
        Permission.HEALTH_READ,
    },
    "manager": {
        # Herite de staff + ajout write/delete metier
        Permission.RESERVATIONS_WRITE,
        Permission.RESERVATIONS_DELETE,
        Permission.INVOICES_WRITE,
        Permission.CUSTOMERS_WRITE,
        Permission.CUSTOMERS_DELETE,
        Permission.INVENTORY_WRITE,
        Permission.VPN_READ,
    },
    "admin": {
        # Herite de manager + catalogue + administration
        Permission.PRODUCTS_WRITE,
        Permission.PRODUCTS_DELETE,
        Permission.CATEGORIES_WRITE,
        Permission.CATEGORIES_DELETE,
        Permission.BUNDLES_WRITE,
        Permission.BUNDLES_DELETE,
        Permission.USERS_READ,
        Permission.USERS_WRITE,
        Permission.USERS_ADMIN,
        Permission.SESSIONS_READ,
        Permission.SESSIONS_ADMIN,
        Permission.AUDIT_READ,
        Permission.API_KEYS_READ,
        Permission.API_KEYS_WRITE,
        Permission.API_KEYS_DELETE,
        Permission.FEATURES_READ,
        Permission.FEATURES_WRITE,
        Permission.FEATURES_DELETE,
        Permission.VPN_WRITE,
        Permission.VPN_ADMIN,
    },
}


def get_effective_permissions(role: str) -> set[Permission]:
    """Resout les permissions effectives en incluant l'heritage hierarchique.

    Raises:
        ValueError: si le role n'existe pas dans ROLE_HIERARCHY.
    """
    if role not in ROLE_HIERARCHY:
        raise ValueError(
            f"Role inconnu: '{role}'. Roles valides: {ROLE_HIERARCHY}"
        )
    role_index = ROLE_HIERARCHY.index(role)
    permissions: set[Permission] = set()
    for i in range(role_index + 1):
        permissions |= ROLE_PERMISSIONS.get(ROLE_HIERARCHY[i], set())
    return permissions


def has_permission(role: str, permission: Permission) -> bool:
    """Verifie si un role possede une permission (avec heritage)."""
    return permission in get_effective_permissions(role)


# Cache pre-calcule au chargement du module (3 roles = O(1) memoire)
_EFFECTIVE_CACHE: dict[str, set[Permission]] = {
    role: get_effective_permissions(role) for role in ROLE_HIERARCHY
}


def get_effective_permissions_cached(role: str) -> set[Permission]:
    """Version cached de get_effective_permissions pour les hot paths.

    Raises:
        ValueError: si le role n'existe pas.
    """
    result = _EFFECTIVE_CACHE.get(role)
    if result is None:
        raise ValueError(
            f"Role inconnu: '{role}'. Roles valides: {ROLE_HIERARCHY}"
        )
    return result
