"""create product_collections table

Revision ID: ee77ff88gg99
Revises: dd66ee77ff88
Create Date: 2026-03-04 21:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "ee77ff88gg99"
down_revision = "dd66ee77ff88"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_collections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("tenant_id", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_product_collections_tenant_id", "product_collections", ["tenant_id"])

    op.create_table(
        "product_collection_items",
        sa.Column("collection_id", sa.Integer, sa.ForeignKey("product_collections.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("product_collection_items")
    op.drop_table("product_collections")
