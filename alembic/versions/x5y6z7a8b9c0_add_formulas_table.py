"""add formulas and formula_items tables

Revision ID: x5y6z7a8b9c0
Revises: w4x5y6z7a8b9
Create Date: 2026-02-23

Strategy: EXPAND — nouvelles tables, aucun impact sur l'existant.
Rollback: DROP TABLE formula_items, formulas
"""
from alembic import op
import sqlalchemy as sa

revision = "x5y6z7a8b9c0"
down_revision = "w4x5y6z7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "formulas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("formula_type", sa.String(20), nullable=False, server_default="classic"),
        sa.Column("price_per_person_cents", sa.BigInteger(), nullable=False),
        sa.Column("featured", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_formulas_tenant_id", "formulas", ["tenant_id"])
    op.create_index(
        "ix_formulas_tenant_slug",
        "formulas",
        ["tenant_id", "slug"],
        unique=True,
    )

    op.create_table(
        "formula_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("formula_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity_per_person", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["formula_id"], ["formulas.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_formula_items_formula_id", "formula_items", ["formula_id"])


def downgrade() -> None:
    op.drop_table("formula_items")
    op.drop_index("ix_formulas_tenant_slug", "formulas")
    op.drop_index("ix_formulas_tenant_id", "formulas")
    op.drop_table("formulas")
