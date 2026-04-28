"""Add restaurant and epicerie scopes to auth_scopes + auth_role_scopes.

Revision ID: t2u3v4w5x6y7
Revises: s1t2u3v4w5x6
Create Date: 2026-03-11

V2 alimentaire — 4 nouveaux scopes restaurant + épicerie.
Matrice après migration :
  super_admin  : 62 + 4 = 66 scopes
  tenant_admin : 60 + 4 = 64 scopes
  manager      : 36 + 4 = 40 scopes
  staff        : 21 + 2 = 23 scopes
  platform_ops : 5 (inchangé)
  viewer       : 12 (inchangé)
"""
from alembic import op

revision = 't2u3v4w5x6y7'
down_revision = 's1t2u3v4w5x6'
branch_labels = None
depends_on = None

# 4 scopes V2 alimentaire
NEW_SCOPES = [
    ("restaurant:read",  "restaurant", "read",  "Lire les données restaurant V2"),
    ("restaurant:write", "restaurant", "write", "Créer/modifier les données restaurant V2"),
    ("epicerie:read",    "epicerie",   "read",  "Lire les données épicerie V2"),
    ("epicerie:write",   "epicerie",   "write", "Créer/modifier les données épicerie V2"),
]

NEW_SCOPE_NAMES = [s[0] for s in NEW_SCOPES]

# Matrice role → scopes V2 alimentaire
ROLE_SCOPES_NEW = {
    "super_admin":  ["restaurant:read", "restaurant:write", "epicerie:read", "epicerie:write"],
    "tenant_admin": ["restaurant:read", "restaurant:write", "epicerie:read", "epicerie:write"],
    "manager":      ["restaurant:read", "restaurant:write", "epicerie:read", "epicerie:write"],
    "staff":        ["restaurant:read", "epicerie:read"],
}


def upgrade() -> None:
    # 1. Insérer les scopes dans auth_scopes (idempotent)
    for name, resource, action, description in NEW_SCOPES:
        op.execute(
            f"INSERT INTO auth_scopes (name, resource, action, description) "
            f"VALUES ('{name}', '{resource}', '{action}', '{description}') "
            f"ON CONFLICT (name) DO NOTHING"
        )

    # 2. Insérer les paires role → scope dans auth_role_scopes (idempotent)
    for role_name, scope_names in ROLE_SCOPES_NEW.items():
        for scope_name in scope_names:
            op.execute(
                f"INSERT INTO auth_role_scopes (role_name, scope_name) "
                f"VALUES ('{role_name}', '{scope_name}') "
                f"ON CONFLICT (role_name, scope_name) DO NOTHING"
            )


def downgrade() -> None:
    scope_list = ", ".join(f"'{s}'" for s in NEW_SCOPE_NAMES)
    op.execute(f"DELETE FROM auth_role_scopes WHERE scope_name IN ({scope_list})")
    op.execute(f"DELETE FROM auth_scopes WHERE name IN ({scope_list})")
