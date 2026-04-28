"""add product collections table

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-02-22

Stratégie expand/contract : création de nouvelles tables uniquement.
Rollback: DROP TABLE (aucune donnée métier existante).
"""
from alembic import op
import sqlalchemy as sa

revision = 'c0d1e2f3a4b5'
down_revision = 'b9c0d1e2f3a4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'product_collections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_product_collections_tenant_id', 'product_collections', ['tenant_id'])
    op.create_index('ix_product_collections_tenant_id_id',
                    'product_collections', ['tenant_id', 'id'])

    # Table d'association product ↔ collection
    op.create_table(
        'product_collection_items',
        sa.Column('collection_id', sa.Integer(),
                  sa.ForeignKey('product_collections.id', ondelete='CASCADE'),
                  nullable=False, primary_key=True),
        sa.Column('product_id', sa.Integer(),
                  sa.ForeignKey('products.id', ondelete='CASCADE'),
                  nullable=False, primary_key=True),
    )
    op.create_index('ix_product_collection_items_product_id',
                    'product_collection_items', ['product_id'])


def downgrade() -> None:
    op.drop_table('product_collection_items')
    op.drop_table('product_collections')
