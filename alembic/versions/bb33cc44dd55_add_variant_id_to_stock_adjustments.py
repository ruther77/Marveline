"""Add variant_id to stock_adjustments table.

Revision ID: bb33cc44dd55
Revises: aa00bb11cc22
Create Date: 2026-03-04
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "bb33cc44dd55"
down_revision: Union[str, None] = "aa00bb11cc22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stock_adjustments",
        sa.Column(
            "variant_id",
            sa.Integer(),
            sa.ForeignKey("product_variants.id", ondelete="RESTRICT"),
            nullable=True,
            comment="Variante concernée (NULL = ajustement produit global)",
        ),
    )
    op.create_index(
        "ix_stock_adjustments_variant_id",
        "stock_adjustments",
        ["variant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_stock_adjustments_variant_id", table_name="stock_adjustments")
    op.drop_column("stock_adjustments", "variant_id")
