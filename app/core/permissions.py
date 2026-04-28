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

from enum import Enum, StrEnum


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

    # Devis
    DEVIS_READ = "devis:read"
    DEVIS_WRITE = "devis:write"

    # Ventes
    VENTES_READ = "ventes:read"
    VENTES_WRITE = "ventes:write"

    # Evenements
    EVENEMENTS_READ = "evenements:read"
    EVENEMENTS_WRITE = "evenements:write"

    # Relances
    RELANCES_READ = "relances:read"
    RELANCES_WRITE = "relances:write"

    # Pricing
    PRICING_READ = "pricing:read"
    PRICING_WRITE = "pricing:write"

    # Suppliers
    SUPPLIERS_READ = "suppliers:read"
    SUPPLIERS_WRITE = "suppliers:write"

    # VPN (WireGuard)
    VPN_READ = "vpn:read"
    VPN_WRITE = "vpn:write"
    VPN_ADMIN = "vpn:admin"

    # Paramètres tenant
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"

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
        Permission.RESERVATIONS_WRITE,   # operateur terrain : cree/modifie reservations
        Permission.INVOICES_READ,
        Permission.INVOICES_WRITE,        # operateur terrain : cree/modifie factures
        Permission.CUSTOMERS_READ,
        Permission.CUSTOMERS_WRITE,       # operateur terrain : cree/modifie clients
        Permission.INVENTORY_READ,
        Permission.INVENTORY_WRITE,       # operateur terrain : mouvements stock
        Permission.DEVIS_READ,
        Permission.VENTES_READ,
        Permission.VENTES_WRITE,          # operateur terrain : ventes directes
        Permission.EVENEMENTS_READ,
        Permission.EVENEMENTS_WRITE,      # operateur terrain : gestion evenements
        Permission.RELANCES_READ,
        Permission.PRICING_READ,
        Permission.SUPPLIERS_READ,
        Permission.HEALTH_READ,
    },
    "manager": {
        # Herite de staff + suppression + devis/relances/fournisseurs/pricing
        Permission.RESERVATIONS_DELETE,
        Permission.CUSTOMERS_DELETE,
        Permission.DEVIS_WRITE,
        Permission.RELANCES_WRITE,
        Permission.SUPPLIERS_WRITE,
        Permission.PRICING_WRITE,
        Permission.VPN_READ,
    },
    "admin": {
        # Herite de manager + catalogue + administration + pricing
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
        Permission.SETTINGS_READ,
        Permission.SETTINGS_WRITE,
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

    Retourne un set vide pour les roles inconnus (nouveaux roles v3)
    plutot que lever une exception.
    """
    result = _EFFECTIVE_CACHE.get(role)
    if result is None:
        # Role v3 non present dans l'ancien systeme — retourner set vide
        # (sera gere par require_scope() du nouveau systeme)
        return set()
    return result


# ═══════════════════════════════════════════════════════════════════════
# NOUVEAU SYSTEME v3 — Scopes CaroCorp (§6.2)
# Coexiste avec l'ancien Permission enum pendant la migration.
# ═══════════════════════════════════════════════════════════════════════

class Scope(StrEnum):
    """Scopes RBAC CaroCorp v3 — format resource:action (§6.1).

    25 scopes infrastructure + 37 scopes metier = 62 scopes totaux.
    Utilises dans :
        - JWT claim "scopes" (liste embarquee)
        - require_scope() dependency FastAPI
        - auth_role_scopes table DB

    Usage :
        from app.core.permissions import Scope
        require_scope(Scope.RESERVATIONS_READ)
    """

    # Reservations
    RESERVATIONS_READ   = "reservations:read"
    RESERVATIONS_WRITE  = "reservations:write"
    RESERVATIONS_DELETE = "reservations:delete"

    # Stock
    STOCK_READ   = "stock:read"
    STOCK_WRITE  = "stock:write"
    STOCK_ADJUST = "stock:adjust"

    # Depots
    DEPOSITS_READ   = "deposits:read"
    DEPOSITS_WRITE  = "deposits:write"
    DEPOSITS_MANAGE = "deposits:manage"

    # Utilisateurs
    USERS_READ   = "users:read"
    USERS_WRITE  = "users:write"
    USERS_MANAGE = "users:manage"
    USERS_DELETE = "users:delete"

    # Sessions
    SESSIONS_READ   = "sessions:read"
    SESSIONS_REVOKE = "sessions:revoke"

    # Devices
    DEVICES_READ   = "devices:read"
    DEVICES_REVOKE = "devices:revoke"

    # Audit
    AUDIT_READ   = "audit:read"
    AUDIT_VERIFY = "audit:verify"

    # Facturation
    BILLING_READ   = "billing:read"
    BILLING_MANAGE = "billing:manage"

    # Configuration
    CONFIG_READ  = "config:read"
    CONFIG_WRITE = "config:write"

    # Rapports
    REPORTS_READ   = "reports:read"
    REPORTS_EXPORT = "reports:export"

    # ─── Scopes metier (migration M5) ──────────────────────────────────────

    # Produits
    PRODUCTS_READ   = "products:read"
    PRODUCTS_WRITE  = "products:write"
    PRODUCTS_DELETE = "products:delete"

    # Categories
    CATEGORIES_READ   = "categories:read"
    CATEGORIES_WRITE  = "categories:write"
    CATEGORIES_DELETE = "categories:delete"

    # Bundles
    BUNDLES_READ   = "bundles:read"
    BUNDLES_WRITE  = "bundles:write"
    BUNDLES_DELETE = "bundles:delete"

    # Clients
    CUSTOMERS_READ   = "customers:read"
    CUSTOMERS_WRITE  = "customers:write"
    CUSTOMERS_DELETE = "customers:delete"

    # Factures
    INVOICES_READ  = "invoices:read"
    INVOICES_WRITE = "invoices:write"

    # Devis
    DEVIS_READ  = "devis:read"
    DEVIS_WRITE = "devis:write"

    # Ventes directes
    VENTES_READ  = "ventes:read"
    VENTES_WRITE = "ventes:write"

    # Evenements / incidents
    EVENEMENTS_READ  = "evenements:read"
    EVENEMENTS_WRITE = "evenements:write"

    # Relances clients
    RELANCES_READ  = "relances:read"
    RELANCES_WRITE = "relances:write"

    # Tarification
    PRICING_READ  = "pricing:read"
    PRICING_WRITE = "pricing:write"

    # Fournisseurs
    SUPPLIERS_READ  = "suppliers:read"
    SUPPLIERS_WRITE = "suppliers:write"

    # VPN WireGuard
    VPN_READ  = "vpn:read"
    VPN_WRITE = "vpn:write"
    VPN_ADMIN = "vpn:admin"

    # Parametres tenant (metier)
    SETTINGS_READ  = "settings:read"
    SETTINGS_WRITE = "settings:write"

    # Cles API
    API_KEYS_READ   = "api_keys:read"
    API_KEYS_WRITE  = "api_keys:write"
    API_KEYS_DELETE = "api_keys:delete"

    # Feature flags
    FEATURES_READ   = "features:read"
    FEATURES_WRITE  = "features:write"
    FEATURES_DELETE = "features:delete"

    # Restaurant (module V2 alimentaire)
    RESTAURANT_READ  = "restaurant:read"
    RESTAURANT_WRITE = "restaurant:write"

    # Épicerie (module V2 alimentaire)
    EPICERIE_READ  = "epicerie:read"
    EPICERIE_WRITE = "epicerie:write"

    # Fidelite (Loyalty)
    LOYALTY_READ   = "loyalty:read"
    LOYALTY_WRITE  = "loyalty:write"
    LOYALTY_MANAGE = "loyalty:manage"

    # Liste de tous les scopes (pour validation)
    @classmethod
    def all_scopes(cls) -> list[str]:
        return [
            # 25 scopes infrastructure v3
            cls.RESERVATIONS_READ, cls.RESERVATIONS_WRITE, cls.RESERVATIONS_DELETE,
            cls.STOCK_READ, cls.STOCK_WRITE, cls.STOCK_ADJUST,
            cls.DEPOSITS_READ, cls.DEPOSITS_WRITE, cls.DEPOSITS_MANAGE,
            cls.USERS_READ, cls.USERS_WRITE, cls.USERS_MANAGE, cls.USERS_DELETE,
            cls.SESSIONS_READ, cls.SESSIONS_REVOKE,
            cls.DEVICES_READ, cls.DEVICES_REVOKE,
            cls.AUDIT_READ, cls.AUDIT_VERIFY,
            cls.BILLING_READ, cls.BILLING_MANAGE,
            cls.CONFIG_READ, cls.CONFIG_WRITE,
            cls.REPORTS_READ, cls.REPORTS_EXPORT,
            # 37 scopes metier (M5)
            cls.PRODUCTS_READ, cls.PRODUCTS_WRITE, cls.PRODUCTS_DELETE,
            cls.CATEGORIES_READ, cls.CATEGORIES_WRITE, cls.CATEGORIES_DELETE,
            cls.BUNDLES_READ, cls.BUNDLES_WRITE, cls.BUNDLES_DELETE,
            cls.CUSTOMERS_READ, cls.CUSTOMERS_WRITE, cls.CUSTOMERS_DELETE,
            cls.INVOICES_READ, cls.INVOICES_WRITE,
            cls.DEVIS_READ, cls.DEVIS_WRITE,
            cls.VENTES_READ, cls.VENTES_WRITE,
            cls.EVENEMENTS_READ, cls.EVENEMENTS_WRITE,
            cls.RELANCES_READ, cls.RELANCES_WRITE,
            cls.PRICING_READ, cls.PRICING_WRITE,
            cls.SUPPLIERS_READ, cls.SUPPLIERS_WRITE,
            cls.VPN_READ, cls.VPN_WRITE, cls.VPN_ADMIN,
            cls.SETTINGS_READ, cls.SETTINGS_WRITE,
            cls.API_KEYS_READ, cls.API_KEYS_WRITE, cls.API_KEYS_DELETE,
            cls.FEATURES_READ, cls.FEATURES_WRITE, cls.FEATURES_DELETE,
            # Restaurant V2
            cls.RESTAURANT_READ, cls.RESTAURANT_WRITE,
            # Épicerie V2
            cls.EPICERIE_READ, cls.EPICERIE_WRITE,
            # Loyalty
            cls.LOYALTY_READ, cls.LOYALTY_WRITE, cls.LOYALTY_MANAGE,
        ]


def has_scope(user_scopes: list[str] | set[str], scope: str) -> bool:
    """Verifie si un scope est dans les scopes de l'utilisateur."""
    return scope in user_scopes
