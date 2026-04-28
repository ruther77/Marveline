"""Add deposit_amount to product_variants + merge heads + auto-create default variants.

Revision ID: aa00bb11cc22
Revises: ab12cd34ef56, c1d2e3f4a5b6, c9d0e1f2a3b4, cc33dd44ee55, q4r5s6t7u8v9, q6r7s8t9u0v1, y7z8a9b0c1d2
Create Date: 2026-03-04
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "aa00bb11cc22"
down_revision: Union[str, None] = (
    "ab12cd34ef56",
    "c1d2e3f4a5b6",
    "c9d0e1f2a3b4",
    "cc33dd44ee55",
    "q4r5s6t7u8v9",
    "q6r7s8t9u0v1",
    "y7z8a9b0c1d2",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add deposit_amount column to product_variants
    op.add_column(
        "product_variants",
        sa.Column(
            "deposit_amount",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Montant caution par unité en centimes",
        ),
    )

    # 2. Data migration: copy deposit_amount from parent product to existing variants
    op.execute(
        """
        UPDATE product_variants pv
        SET deposit_amount = p.deposit_amount
        FROM products p
        WHERE pv.product_id = p.id
        AND p.deposit_amount > 0
        """
    )

    # 3. Auto-create a default "Standard" variant for products that have no variants
    # This ensures every product has at least 1 variant (architectural decision)
    op.execute(
        """
        INSERT INTO product_variants (
            tenant_id, product_id, label, sku, color,
            stock_quantity, available_quantity, deposit_amount,
            price_per_day, is_active, created_at, updated_at
        )
        SELECT
            p.tenant_id,
            p.id,
            'Standard',
            p.sku || '-STD',
            NULL,
            p.stock_quantity,
            p.available_quantity,
            p.deposit_amount,
            p.price_per_day,
            TRUE,
            NOW(),
            NOW()
        FROM products p
        WHERE p.is_active = TRUE
        AND NOT EXISTS (
            SELECT 1 FROM product_variants pv
            WHERE pv.product_id = p.id AND pv.is_active = TRUE
        )
        """
    )

    # Remove server_default after data migration
    op.alter_column("product_variants", "deposit_amount", server_default=None)


def downgrade() -> None:
    # Remove auto-created default variants (those with label='Standard' and sku ending '-STD')
    op.execute(
        """
        DELETE FROM product_variants
        WHERE label = 'Standard' AND sku LIKE '%-STD'
        """
    )

    op.drop_column("product_variants", "deposit_amount")
