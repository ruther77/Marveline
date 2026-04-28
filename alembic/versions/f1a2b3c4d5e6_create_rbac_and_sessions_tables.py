"""create_rbac_and_sessions_tables

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-02-27 14:00:00.000000

Phase 2 — CaroCorp §6.5 : Tables RBAC (auth_roles, auth_scopes,
auth_role_scopes, user_roles) + user_sessions.
Seed data : 6 roles, 25 scopes, matrice role→scopes complete.
Note : §6.2 titre "26 scopes" est une erreur documentaire — 25 scopes reels.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Seed data CaroCorp §6.1-6.3 ──────────────────────────────────────────────

ROLES = [
    ("super_admin",  0, True,  True,  "Acces plateforme complete — CaroCorp staff"),
    ("platform_ops", 1, True,  True,  "Monitoring & maintenance cross-tenant"),
    ("tenant_admin", 2, False, True,  "Administrateur du tenant"),
    ("manager",      3, False, False, "Operationnel senior — mutations sensibles"),
    ("staff",        4, False, False, "Operationnel terrain — usage quotidien"),
    ("viewer",       5, False, False, "Consultation seule"),
]

SCOPES = [
    ("reservations:read",   "reservations", "read",   "Lire les reservations du tenant"),
    ("reservations:write",  "reservations", "write",  "Creer/modifier/annuler des reservations"),
    ("reservations:delete", "reservations", "delete", "Supprimer definitivement (soft-delete)"),
    ("stock:read",          "stock",        "read",   "Consulter les niveaux de stock"),
    ("stock:write",         "stock",        "write",  "Modifier les quantites (entrees/sorties)"),
    ("stock:adjust",        "stock",        "adjust", "Ajustements d'inventaire (correction manuelle)"),
    ("deposits:read",       "deposits",     "read",   "Consulter les depots/entrepots"),
    ("deposits:write",      "deposits",     "write",  "Creer/modifier des depots"),
    ("deposits:manage",     "deposits",     "manage", "Activer/desactiver, changer les affectations"),
    ("users:read",          "users",        "read",   "Lister les utilisateurs du tenant"),
    ("users:write",         "users",        "write",  "Creer/modifier des utilisateurs"),
    ("users:manage",        "users",        "manage", "Changer les roles, activer/desactiver"),
    ("users:delete",        "users",        "delete", "Supprimer un utilisateur (soft-delete)"),
    ("sessions:read",       "sessions",     "read",   "Voir les sessions actives du tenant"),
    ("sessions:revoke",     "sessions",     "revoke", "Revoquer des sessions d'autres utilisateurs"),
    ("devices:read",        "devices",      "read",   "Lister les devices enroles du tenant"),
    ("devices:revoke",      "devices",      "revoke", "Revoquer un device"),
    ("audit:read",          "audit",        "read",   "Consulter les logs d'audit du tenant"),
    ("audit:verify",        "audit",        "verify", "Verifier les signatures HMAC"),
    ("billing:read",        "billing",      "read",   "Consulter les factures"),
    ("billing:manage",      "billing",      "manage", "Modifier les informations de facturation"),
    ("config:read",         "config",       "read",   "Lire la configuration tenant"),
    ("config:write",        "config",       "write",  "Modifier la configuration tenant"),
    ("reports:read",        "reports",      "read",   "Acceder aux rapports et analytics"),
    ("reports:export",      "reports",      "export", "Exporter les donnees (CSV, PDF)"),
]

# Matrice role → scopes (CaroCorp §6.3)
# platform_ops a des scopes cross-tenant en lecture seule (marques *)
ROLE_SCOPES = {
    "super_admin": [s[0] for s in SCOPES],  # Tous les 25 scopes
    "platform_ops": [
        "sessions:read", "devices:read", "audit:read",
        "audit:verify", "config:read",
    ],
    "tenant_admin": [
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
    ],
    "manager": [
        "reservations:read", "reservations:write", "reservations:delete",
        "stock:read", "stock:write", "stock:adjust",
        "deposits:read", "deposits:write",
        "users:read",
        "sessions:read",
        "devices:read",
        "config:read",
        "reports:read", "reports:export",
    ],
    "staff": [
        "reservations:read", "reservations:write",
        "stock:read", "stock:write",
        "deposits:read",
        "reports:read",
    ],
    "viewer": [
        "reservations:read",
        "stock:read",
        "deposits:read",
        "reports:read",
    ],
}


def upgrade() -> None:
    # ── auth_roles ────────────────────────────────────────────────────────
    op.create_table(
        "auth_roles",
        sa.Column("name", sa.String(50), primary_key=True),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── auth_scopes ───────────────────────────────────────────────────────
    op.create_table(
        "auth_scopes",
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("resource", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── auth_role_scopes ──────────────────────────────────────────────────
    op.create_table(
        "auth_role_scopes",
        sa.Column("role_name", sa.String(50), sa.ForeignKey("auth_roles.name", ondelete="CASCADE"), primary_key=True),
        sa.Column("scope_name", sa.String(100), sa.ForeignKey("auth_scopes.name", ondelete="CASCADE"), primary_key=True),
    )

    # ── user_roles ────────────────────────────────────────────────────────
    op.create_table(
        "user_roles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("role_name", sa.String(50), sa.ForeignKey("auth_roles.name", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(200), nullable=True),
    )

    # Contrainte unique partielle : 1 role actif par user par tenant
    # create_unique_constraint ne supporte pas postgresql_where → index partiel unique
    op.create_index(
        "uq_user_roles_active_per_tenant",
        "user_roles",
        ["user_id", "tenant_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # Index partiels
    op.create_index(
        "idx_user_roles_tenant_active",
        "user_roles",
        ["tenant_id", "role_name"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "idx_user_roles_user_active",
        "user_roles",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # ── user_sessions ─────────────────────────────────────────────────────
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.String(128), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(200), nullable=True),
        sa.Column("mfa_verified", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_index("idx_user_sessions_tenant_user", "user_sessions", ["tenant_id", "user_id"])
    op.create_index("idx_user_sessions_device", "user_sessions", ["device_id"])
    op.create_index(
        "idx_user_sessions_user_active",
        "user_sessions",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # ── Seed data ─────────────────────────────────────────────────────────
    roles_table = sa.table(
        "auth_roles",
        sa.column("name", sa.String),
        sa.column("level", sa.SmallInteger),
        sa.column("is_system", sa.Boolean),
        sa.column("mfa_required", sa.Boolean),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(roles_table, [
        {"name": r[0], "level": r[1], "is_system": r[2], "mfa_required": r[3], "description": r[4]}
        for r in ROLES
    ])

    scopes_table = sa.table(
        "auth_scopes",
        sa.column("name", sa.String),
        sa.column("resource", sa.String),
        sa.column("action", sa.String),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(scopes_table, [
        {"name": s[0], "resource": s[1], "action": s[2], "description": s[3]}
        for s in SCOPES
    ])

    role_scopes_table = sa.table(
        "auth_role_scopes",
        sa.column("role_name", sa.String),
        sa.column("scope_name", sa.String),
    )
    rows = []
    for role_name, scope_names in ROLE_SCOPES.items():
        for scope_name in scope_names:
            rows.append({"role_name": role_name, "scope_name": scope_name})
    op.bulk_insert(role_scopes_table, rows)


def downgrade() -> None:
    op.drop_table("user_sessions")
    op.drop_table("user_roles")
    op.drop_table("auth_role_scopes")
    op.drop_table("auth_scopes")
    op.drop_table("auth_roles")
