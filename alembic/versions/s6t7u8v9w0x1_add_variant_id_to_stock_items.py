"""add variant_id to stock_items

Revision ID: s6t7u8v9w0x1
Revises: f46e3c95d103
Create Date: 2026-03-07

Migration expand-only :
  1. Ajoute stock_items.variant_id FK nullable vers product_variants
  2. Data : crée variante "Standard" pour les produits sans variante active
             + lie immédiatement leurs stock_items
  3. Data : lie les stock_items des produits à exactement 1 variante active
  4. Les produits avec >1 variante active → variant_id reste NULL
     (liaison manuelle via UI stock)
"""
from alembic import op
import sqlalchemy as sa

revision = 's6t7u8v9w0x1'
down_revision = 'f46e3c95d103'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. Colonne nullable + index composite
    # -------------------------------------------------------------------------
    op.add_column(
        'stock_items',
        sa.Column(
            'variant_id',
            sa.Integer(),
            sa.ForeignKey('product_variants.id', ondelete='RESTRICT'),
            nullable=True,
            comment='Variante physique trackée (NULL = non encore assignée)',
        ),
    )

    op.create_index(
        'ix_stock_item_product_variant_status',
        'stock_items',
        ['tenant_id', 'product_id', 'variant_id', 'status'],
    )

    # -------------------------------------------------------------------------
    # 2. Créer variante "Standard" pour les produits sans aucune variante active
    #    + lier leurs stock_items dans la même CTE atomique
    # -------------------------------------------------------------------------
    op.execute("""
        WITH inserted AS (
            INSERT INTO product_variants (
                tenant_id, product_id, label, sku,
                stock_quantity, available_quantity, deposit_amount,
                is_active, created_at, updated_at
            )
            SELECT
                p.tenant_id,
                p.id,
                'Standard',
                LEFT(COALESCE(p.sku, 'PROD'), 40) || '-STD-' || CAST(p.id AS TEXT),
                COALESCE(p.stock_quantity, 0),
                COALESCE(p.available_quantity, 0),
                COALESCE(p.deposit_amount, 0),
                TRUE,
                NOW(),
                NOW()
            FROM products p
            WHERE p.is_active = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM product_variants pv
                  WHERE pv.product_id = p.id
                    AND pv.is_active = TRUE
              )
            RETURNING id, product_id
        )
        UPDATE stock_items si
        SET variant_id = ins.id
        FROM inserted ins
        WHERE si.product_id = ins.product_id
          AND si.variant_id IS NULL
    """)

    # -------------------------------------------------------------------------
    # 3. Produits avec exactement 1 variante active → lier automatiquement
    # -------------------------------------------------------------------------
    op.execute("""
        UPDATE stock_items si
        SET variant_id = (
            SELECT pv.id
            FROM product_variants pv
            WHERE pv.product_id = si.product_id
              AND pv.is_active = TRUE
            LIMIT 1
        )
        WHERE si.variant_id IS NULL
          AND (
              SELECT COUNT(*)
              FROM product_variants pv
              WHERE pv.product_id = si.product_id
                AND pv.is_active = TRUE
          ) = 1
    """)

    # Les produits avec >1 variante active conservent variant_id = NULL.
    # Liaison manuelle requise via l'UI Stock → StockItemEditPage.


def downgrade() -> None:
    op.drop_index('ix_stock_item_product_variant_status', table_name='stock_items')
    op.drop_column('stock_items', 'variant_id')
    # Les variantes "Standard" créées au upgrade() sont conservées (expand-only).
