"""add password_reset_tokens table (NC-05 spec §04-AUTH-FLOWS §4.4).

Revision ID: a4b5c6d7e8f9
Revises: e8f9a0b1c2d3
Create Date: 2026-03-01

Remplace le stockage Redis des tokens de reset (GETDEL) par une table PostgreSQL.

Spec §4.4 :
    - token_hash : SHA-256 hex (64 chars) — jamais le token brut
    - expires_at : TTL 1h (now + 3600s)
    - used       : BOOLEAN — single-use (SELECT FOR UPDATE dans consume())
    - tenant_id  : NOT NULL — isolation multi-tenant (invariant A1)

Stratégie expand/contract :
    Cette migration est en expand uniquement.
    Les anciens tokens Redis expireront naturellement (TTL 30 min max).
    Aucune migration de données nécessaire.
"""
import sqlalchemy as sa
from alembic import op


revision = "a4b5c6d7e8f9"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "token_hash",
            sa.String(64),
            nullable=False,
            comment="SHA-256 hex du token brut (jamais le token en clair)",
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Expiration du token (TTL 1h — spec §4.4)",
        ),
        sa.Column(
            "used",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="True une fois consommé (single-use)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Index unique sur token_hash (lookup rapide par hash, pas d'énumération)
    op.create_index(
        "ix_prt_token_hash",
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )

    # Index sur tenant_id seul (convention multi-tenant)
    op.create_index(
        "ix_prt_tenant_id",
        "password_reset_tokens",
        ["tenant_id"],
    )

    # Index composite tenant_id + user_id (cleanup, audit)
    op.create_index(
        "ix_prt_tenant_user",
        "password_reset_tokens",
        ["tenant_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_prt_tenant_user", table_name="password_reset_tokens")
    op.drop_index("ix_prt_tenant_id", table_name="password_reset_tokens")
    op.drop_index("ix_prt_token_hash", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
