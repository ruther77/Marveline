"""add_business_scopes_m5

Revision ID: z9a0b1c2d3e4
Revises: (merge 16 heads)
Create Date: 2026-02-28 00:00:00.000000

Phase M5-A — Ajout de 37 scopes metier dans auth_scopes + auth_role_scopes.
Additive, non-destructive. Inserts avec ON CONFLICT DO NOTHING (idempotent).

Matrice finale role → scopes (infrastructure v3 + metier M5) :
  super_admin  : 25 infra + 37 business = 62 scopes
  platform_ops : 5 infra (inchange)
  tenant_admin : 24 infra + 36 business (sans vpn:admin) = 60 scopes
  manager      : 14 infra + 22 business = 36 scopes
  staff        : 6 infra + 15 business = 21 scopes
  viewer       : 4 infra + 8 business = 12 scopes
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "z9a0b1c2d3e4"
down_revision: Union[str, None, tuple] = (
    "c9d0e1f2a3b4", "cc33dd44ee55", "dd55ee66ff77",
    "n0p1q2r3s4t5", "o1p2q3r4s5t6", "p2q3r4s5t6u7",
    "q3r4s5t6u7v8", "r4s5t6u7v8w9", "s5t6u7v8w9x0",
    "t1u2v3w4x5y6", "u2v3w4x5y6z7", "v3w4x5y6z7a8",
    "w4x5y6z7a8b9", "x5y6z7a8b9c0", "y6z7a8b9c0d1",
    "z7a8b9c0d1e2",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 37 scopes metier (M5)
NEW_SCOPES = [
    ("products:read",     "products",    "read",    "Lire le catalogue produits"),
    ("products:write",    "products",    "write",   "Creer/modifier les produits"),
    ("products:delete",   "products",    "delete",  "Supprimer des produits (soft-delete)"),
    ("categories:read",   "categories",  "read",    "Lire les categories"),
    ("categories:write",  "categories",  "write",   "Creer/modifier les categories"),
    ("categories:delete", "categories",  "delete",  "Supprimer des categories"),
    ("bundles:read",      "bundles",     "read",    "Lire les bundles/lots"),
    ("bundles:write",     "bundles",     "write",   "Creer/modifier les bundles"),
    ("bundles:delete",    "bundles",     "delete",  "Supprimer des bundles"),
    ("customers:read",    "customers",   "read",    "Lire les clients"),
    ("customers:write",   "customers",   "write",   "Creer/modifier les clients"),
    ("customers:delete",  "customers",   "delete",  "Supprimer des clients (soft-delete)"),
    ("invoices:read",     "invoices",    "read",    "Lire les factures"),
    ("invoices:write",    "invoices",    "write",   "Creer/modifier/emettre des factures"),
    ("devis:read",        "devis",       "read",    "Lire les devis"),
    ("devis:write",       "devis",       "write",   "Creer/modifier/envoyer des devis"),
    ("ventes:read",       "ventes",      "read",    "Lire les ventes directes"),
    ("ventes:write",      "ventes",      "write",   "Creer/modifier/annuler des ventes"),
    ("evenements:read",   "evenements",  "read",    "Lire les evenements/incidents"),
    ("evenements:write",  "evenements",  "write",   "Creer/modifier des evenements"),
    ("relances:read",     "relances",    "read",    "Lire les relances clients"),
    ("relances:write",    "relances",    "write",   "Creer/envoyer des relances"),
    ("pricing:read",      "pricing",     "read",    "Lire les regles tarifaires"),
    ("pricing:write",     "pricing",     "write",   "Creer/modifier les regles tarifaires"),
    ("suppliers:read",    "suppliers",   "read",    "Lire les fournisseurs"),
    ("suppliers:write",   "suppliers",   "write",   "Creer/modifier les fournisseurs"),
    ("vpn:read",          "vpn",         "read",    "Consulter la configuration VPN"),
    ("vpn:write",         "vpn",         "write",   "Modifier la configuration VPN"),
    ("vpn:admin",         "vpn",         "admin",   "Administration complete VPN WireGuard"),
    ("settings:read",     "settings",    "read",    "Lire la configuration tenant (metier)"),
    ("settings:write",    "settings",    "write",   "Modifier la configuration tenant (metier)"),
    ("api_keys:read",     "api_keys",    "read",    "Lire les cles API"),
    ("api_keys:write",    "api_keys",    "write",   "Creer/modifier des cles API"),
    ("api_keys:delete",   "api_keys",    "delete",  "Revoquer/supprimer des cles API"),
    ("features:read",     "features",    "read",    "Lire les feature flags"),
    ("features:write",    "features",    "write",   "Activer/desactiver des feature flags"),
    ("features:delete",   "features",    "delete",  "Supprimer des feature flags"),
]

# Matrice role → nouveaux scopes metier
ROLE_SCOPES_NEW: dict[str, list[str]] = {
    "super_admin": [s[0] for s in NEW_SCOPES],  # 37 scopes (tous)
    "platform_ops": [],                           # 0 (monitoring infra uniquement)
    "tenant_admin": [
        # Tous sauf vpn:admin
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
    ],
    "manager": [
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
    ],
    "staff": [
        "products:read", "categories:read", "bundles:read",
        "customers:read", "customers:write",
        "invoices:read", "invoices:write",
        "devis:read",
        "ventes:read", "ventes:write",
        "evenements:read", "evenements:write",
        "relances:read",
        "pricing:read",
        "suppliers:read",
    ],
    "viewer": [
        "products:read", "categories:read", "bundles:read",
        "customers:read",
        "invoices:read",
        "devis:read",
        "ventes:read",
        "evenements:read",
    ],
}

# Noms des 37 scopes metier (pour downgrade)
NEW_SCOPE_NAMES = [s[0] for s in NEW_SCOPES]


def upgrade() -> None:
    # 1. Inserer les 37 scopes metier dans auth_scopes (idempotent)
    for name, resource, action, description in NEW_SCOPES:
        op.execute(
            f"INSERT INTO auth_scopes (name, resource, action, description) "
            f"VALUES ('{name}', '{resource}', '{action}', '{description}') "
            f"ON CONFLICT (name) DO NOTHING"
        )

    # 2. Inserer les paires role → scope dans auth_role_scopes (idempotent)
    for role_name, scope_names in ROLE_SCOPES_NEW.items():
        for scope_name in scope_names:
            op.execute(
                f"INSERT INTO auth_role_scopes (role_name, scope_name) "
                f"VALUES ('{role_name}', '{scope_name}') "
                f"ON CONFLICT (role_name, scope_name) DO NOTHING"
            )


def downgrade() -> None:
    # Supprimer les paires role → scope pour les nouveaux scopes
    scope_list = ", ".join(f"'{s}'" for s in NEW_SCOPE_NAMES)
    op.execute(
        f"DELETE FROM auth_role_scopes WHERE scope_name IN ({scope_list})"
    )

    # Supprimer les nouveaux scopes
    op.execute(
        f"DELETE FROM auth_scopes WHERE name IN ({scope_list})"
    )
