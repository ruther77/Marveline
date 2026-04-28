"""add variant_id to bundle_items

Revision ID: b6c7d8e9f0a1
Revises: a9b0c1d2e3f4
Create Date: 2026-03-07 10:00:00.000000

Expand-only migration — ajout nullable variant_id sur bundle_items.
Remplace la contrainte unique (bundle_id, product_id) par deux index partiels :
  - uq_bundle_item_no_variant  : (bundle_id, product_id) WHERE variant_id IS NULL
  - uq_bundle_item_with_variant: (bundle_id, product_id, variant_id) WHERE variant_id IS NOT NULL
Compatible PostgreSQL 12+.
"""
from alembic import op
import sqlalchemy as sa

revision = 'b6c7d8e9f0a1'
down_revision = 'a9b0c1d2e3f4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Ajouter la colonne variant_id nullable
    op.add_column(
        'bundle_items',
        sa.Column(
            'variant_id',
            sa.Integer(),
            sa.ForeignKey('product_variants.id', name='fk_bundle_item_variant', ondelete='RESTRICT'),
            nullable=True,
            comment='FK vers product_variants (optionnel)',
        ),
    )
    op.create_index('ix_bundle_items_variant_id', 'bundle_items', ['variant_id'])

    # 2. Supprimer l'ancienne contrainte unique (bundle_id, product_id)
    op.drop_constraint('uq_bundle_item_product', 'bundle_items', type_='unique')

    # 3. Deux index partiels uniques — couvrent produit sans variant et produit avec variant
    op.create_index(
        'uq_bundle_item_no_variant',
        'bundle_items',
        ['bundle_id', 'product_id'],
        unique=True,
        postgresql_where=sa.text('variant_id IS NULL'),
    )
    op.create_index(
        'uq_bundle_item_with_variant',
        'bundle_items',
        ['bundle_id', 'product_id', 'variant_id'],
        unique=True,
        postgresql_where=sa.text('variant_id IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_bundle_item_with_variant', table_name='bundle_items')
    op.drop_index('uq_bundle_item_no_variant', table_name='bundle_items')
    op.create_unique_constraint('uq_bundle_item_product', 'bundle_items', ['bundle_id', 'product_id'])
    op.drop_index('ix_bundle_items_variant_id', table_name='bundle_items')
    op.drop_constraint('fk_bundle_item_variant', 'bundle_items', type_='foreignkey')
    op.drop_column('bundle_items', 'variant_id')
