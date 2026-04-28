"""add devis delivery_status and coverage_items

Revision ID: dd55ee66ff77
Revises: cc33dd44ee55
Create Date: 2026-02-25

Expand : ajoute delivery_status sur devis_modules + table devis_coverage_items
"""
from alembic import op
import sqlalchemy as sa

revision = "dd55ee66ff77"
down_revision = "dd44ee55ff66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Colonne delivery_status sur devis_modules
    op.add_column(
        "devis_modules",
        sa.Column(
            "delivery_status",
            sa.String(20),
            nullable=False,
            server_default="a_cadrer",
        ),
    )
    op.create_check_constraint(
        "check_devis_module_delivery_status_valid",
        "devis_modules",
        "delivery_status IN ('a_cadrer','en_cours','livre')",
    )

    # 2. Table devis_coverage_items
    op.create_table(
        "devis_coverage_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("devis_id", sa.Integer(), sa.ForeignKey("devis.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="a_cadrer"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('a_cadrer','en_cours','livre')",
            name="check_devis_coverage_item_status_valid",
        ),
    )
    op.create_index(
        "ix_devis_coverage_items_tenant_devis",
        "devis_coverage_items",
        ["tenant_id", "devis_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_devis_coverage_items_tenant_devis", table_name="devis_coverage_items")
    op.drop_table("devis_coverage_items")
    op.drop_constraint("check_devis_module_delivery_status_valid", "devis_modules", type_="check")
    op.drop_column("devis_modules", "delivery_status")
