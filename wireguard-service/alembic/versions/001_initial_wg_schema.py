"""Initial WireGuard schema

Revision ID: 001_initial_wg
Revises:
Create Date: 2026-02-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_wg"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Créer le schema wg
    op.execute("CREATE SCHEMA IF NOT EXISTS wg")

    # Table wg_peers
    op.create_table(
        "wg_peers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("public_key", sa.String(44), nullable=False),
        sa.Column("encrypted_private_key", sa.Text(), nullable=False),
        sa.Column("preshared_key", sa.String(44), nullable=True),
        sa.Column("assigned_ip", sa.String(18), nullable=False),
        sa.Column("allowed_ips", sa.String(255), nullable=False, server_default="0.0.0.0/0"),
        sa.Column("persistent_keepalive", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("dns", sa.String(255), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("peer_type", sa.String(50), nullable=False, server_default="permanent"),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("last_handshake_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="wg",
    )

    op.create_index("ix_wg_peers_tenant_id", "wg_peers", ["tenant_id"], schema="wg")
    op.create_index("ix_wg_peers_tenant_id_id", "wg_peers", ["tenant_id", "id"], schema="wg")
    op.create_index(
        "ix_wg_peers_tenant_public_key", "wg_peers",
        ["tenant_id", "public_key"], unique=True, schema="wg",
    )

    # Table wg_ip_pools
    op.create_table(
        "wg_ip_pools",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("subnet", sa.String(18), nullable=False),
        sa.Column("gateway_ip", sa.String(15), nullable=False),
        sa.Column("next_ip", sa.String(15), nullable=False),
        sa.Column("subnet_mask", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="wg",
    )

    op.create_index("ix_wg_ip_pools_tenant_id", "wg_ip_pools", ["tenant_id"], schema="wg")
    op.create_index("ix_wg_ip_pools_tenant_id_id", "wg_ip_pools", ["tenant_id", "id"], schema="wg")
    op.create_index(
        "ix_wg_ip_pools_tenant_subnet", "wg_ip_pools",
        ["tenant_id", "subnet"], unique=True, schema="wg",
    )

    # Table wg_audit_logs
    op.create_table(
        "wg_audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("peer_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="wg",
    )

    op.create_index("ix_wg_audit_logs_tenant_id", "wg_audit_logs", ["tenant_id"], schema="wg")
    op.create_index("ix_wg_audit_logs_tenant_id_id", "wg_audit_logs", ["tenant_id", "id"], schema="wg")
    op.create_index("ix_wg_audit_logs_peer_id", "wg_audit_logs", ["peer_id"], schema="wg")
    op.create_index("ix_wg_audit_logs_action", "wg_audit_logs", ["action"], schema="wg")
    op.create_index("ix_wg_audit_logs_created_at", "wg_audit_logs", ["created_at"], schema="wg")


def downgrade() -> None:
    op.drop_table("wg_audit_logs", schema="wg")
    op.drop_table("wg_ip_pools", schema="wg")
    op.drop_table("wg_peers", schema="wg")
    op.execute("DROP SCHEMA IF EXISTS wg CASCADE")
