"""create tenant_settings table + add cgv columns

Revision ID: v3w4x5y6z7a8
Revises: u2v3w4x5y6z7
Create Date: 2026-02-23

Strategy: EXPAND — création table tenant_settings + 5 colonnes CGV.
Rollback: DROP TABLE tenant_settings (supprime tout en cascade).
Note: la migration archive/v3w4x5y6z7a8_add_tenant_settings_table.py a été
      fusionnée ici pour éviter le conflit de revision ID.
"""
from alembic import op
import sqlalchemy as sa

revision = "v3w4x5y6z7a8"
down_revision = "u2v3w4x5y6z7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(200), nullable=True),
        sa.Column("company_email", sa.String(200), nullable=True),
        sa.Column("company_phone", sa.String(50), nullable=True),
        sa.Column("company_address", sa.String(500), nullable=True),
        sa.Column("vat_rate", sa.Float(), nullable=False, server_default="0.20"),
        sa.Column("hourly_rate_weekday", sa.Float(), nullable=False, server_default="30.0"),
        sa.Column("hourly_rate_weekend", sa.Float(), nullable=False, server_default="60.0"),
        sa.Column("deposit_rate", sa.Float(), nullable=False, server_default="0.30"),
        sa.Column("default_currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("advance_rate", sa.Float(), nullable=False, server_default="0.40"),
        sa.Column("deposit_multiplier", sa.Float(), nullable=False, server_default="3.0"),
        sa.Column("cancellation_threshold_days", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("cancellation_early_penalty_rate", sa.Float(), nullable=False, server_default="0.40"),
        sa.Column("cancellation_late_penalty_rate", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_settings_tenant_id"),
    )
    op.create_index("ix_tenant_settings_tenant_id", "tenant_settings", ["tenant_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tenant_settings_tenant_id", table_name="tenant_settings")
    op.drop_table("tenant_settings")
