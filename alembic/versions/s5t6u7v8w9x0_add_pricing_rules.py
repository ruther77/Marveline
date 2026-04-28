"""Add pricing_rules and pricing_tiers tables.

Revision ID: s5t6u7v8w9x0
Revises: r4s5t6u7v8w9
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa

revision = "s5t6u7v8w9x0"
down_revision = "r4s5t6u7v8w9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pricing_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("rule_type", sa.String(30), nullable=False),
        sa.Column("applies_to", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("discount_pct", sa.Integer(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pricing_rules_tenant_id", "pricing_rules", ["tenant_id"])
    op.create_index("ix_pricing_rules_tenant_active", "pricing_rules", ["tenant_id", "active"])

    op.create_table(
        "pricing_tiers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("min_qty", sa.Integer(), nullable=False),
        sa.Column("max_qty", sa.Integer(), nullable=True),
        sa.Column("unit_price_cents", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["pricing_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pricing_tiers_rule_id", "pricing_tiers", ["rule_id"])
    op.create_index("ix_pricing_tiers_tenant_id", "pricing_tiers", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("pricing_tiers")
    op.drop_table("pricing_rules")
