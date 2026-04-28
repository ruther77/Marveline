"""Add tenants table — tenant lifecycle (§S-13.1)

Revision ID: c1d2e3f4a5b6
Revises: ff00ee11dd22
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "c1d2e3f4a5b6"
down_revision = "ff00ee11dd22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("domain", sa.String(200), nullable=False),
        sa.Column("contact_email", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="provisioning"),
        sa.Column("plan", sa.String(50), nullable=False, server_default="standard"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offboarding_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provisioned_by", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("data_retention_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("max_sessions_per_user", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("domain"),
    )
    op.create_index("idx_tenants_status", "tenants", ["status"])
    op.create_index("idx_tenants_domain", "tenants", ["domain"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_tenants_domain", table_name="tenants")
    op.drop_index("idx_tenants_status", table_name="tenants")
    op.drop_table("tenants")
