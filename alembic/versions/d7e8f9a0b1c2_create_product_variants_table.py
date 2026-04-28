"""create product_variants table

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-02-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_variants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False, comment="Produit parent"),
        sa.Column("color", sa.String(50), nullable=False, comment="Couleur de la variante (ex: ivoire, bordeaux)"),
        sa.Column("sku", sa.String(50), nullable=False, comment="SKU unique de la variante par tenant"),
        sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0", comment="Quantité totale en stock"),
        sa.Column("available_quantity", sa.Integer(), nullable=False, server_default="0", comment="Quantité disponible à la location"),
        # TenantMixin
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        # SoftDeleteMixin
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        # TimestampMixin
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # PK
        sa.PrimaryKeyConstraint("id"),
        # FK produit
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        # Unicité SKU par tenant
        sa.UniqueConstraint("tenant_id", "sku", name="uq_product_variant_tenant_sku"),
        # Unicité couleur par produit par tenant
        sa.UniqueConstraint("tenant_id", "product_id", "color", name="uq_product_variant_tenant_product_color"),
        # Contraintes stock
        sa.CheckConstraint("available_quantity <= stock_quantity", name="check_variant_available_lte_stock"),
        sa.CheckConstraint("stock_quantity >= 0", name="check_variant_stock_positive"),
    )
    op.create_index("ix_product_variants_tenant_id", "product_variants", ["tenant_id"])
    op.create_index("ix_product_variants_product_id", "product_variants", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_product_variants_product_id", table_name="product_variants")
    op.drop_index("ix_product_variants_tenant_id", table_name="product_variants")
    op.drop_table("product_variants")
