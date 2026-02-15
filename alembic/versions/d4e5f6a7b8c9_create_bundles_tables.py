"""create_bundles_tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-13 23:45:00.000000

Create product_bundles and bundle_items tables.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # product_bundles
    op.create_table(
        'product_bundles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('short_description', sa.String(500), nullable=True),
        sa.Column('bundle_price', sa.BigInteger(), nullable=False),
        sa.Column('cleaning_fee', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('featured', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_bundle_tenant_slug'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_bundle_tenant_name'),
        sa.CheckConstraint('bundle_price >= 0', name='check_bundle_price_positive'),
        sa.CheckConstraint('cleaning_fee >= 0', name='check_bundle_cleaning_fee_positive'),
        sa.CheckConstraint('display_order >= 0', name='check_bundle_display_order'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bundles_tenant_id', 'product_bundles', ['tenant_id'])
    op.create_index('ix_bundles_tenant_slug', 'product_bundles', ['tenant_id', 'slug'])

    # bundle_items
    op.create_table(
        'bundle_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('bundle_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['bundle_id'], ['product_bundles.id'], name='fk_bundle_item_bundle'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], name='fk_bundle_item_product'),
        sa.UniqueConstraint('bundle_id', 'product_id', name='uq_bundle_item_product'),
        sa.CheckConstraint('quantity > 0', name='check_bundle_item_quantity_positive'),
        sa.CheckConstraint('display_order >= 0', name='check_bundle_item_display_order'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bundle_items_bundle_id', 'bundle_items', ['bundle_id'])
    op.create_index('ix_bundle_items_product_id', 'bundle_items', ['product_id'])
    op.create_index('ix_bundle_items_tenant_id', 'bundle_items', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_bundle_items_tenant_id', table_name='bundle_items')
    op.drop_index('ix_bundle_items_product_id', table_name='bundle_items')
    op.drop_index('ix_bundle_items_bundle_id', table_name='bundle_items')
    op.drop_table('bundle_items')
    op.drop_index('ix_bundles_tenant_slug', table_name='product_bundles')
    op.drop_index('ix_bundles_tenant_id', table_name='product_bundles')
    op.drop_table('product_bundles')
