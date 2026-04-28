"""add_supplier_id_to_products

Revision ID: t1u2v3w4x5y6
Revises: t0u1v2w3x4y5
Create Date: 2026-02-22 00:00:00.000000

Strategy: expand-only
- Ajoute colonne supplier_id nullable (FK vers suppliers) sur products
- Rollback: drop la colonne
"""
from alembic import op
import sqlalchemy as sa

revision = 't1u2v3w4x5y6'
down_revision = 't0u1v2w3x4y5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column(
            'supplier_id',
            sa.Integer(),
            sa.ForeignKey('suppliers.id', ondelete='SET NULL'),
            nullable=True,
            comment="FK optionnelle vers le fournisseur principal du produit"
        )
    )
    op.create_index(
        'ix_products_tenant_id_supplier_id',
        'products',
        ['tenant_id', 'supplier_id']
    )


def downgrade() -> None:
    op.drop_index('ix_products_tenant_id_supplier_id', table_name='products')
    op.drop_column('products', 'supplier_id')
