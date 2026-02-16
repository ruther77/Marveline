"""create_inventory_movements_tables

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-02-15 19:00:00.000000

Create inventory_movements and movement_items tables for stock movement tracking.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── inventory_movements ──────────────────────────────────────────
    op.create_table(
        'inventory_movements',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=True),
        sa.Column('movement_type', sa.String(20), nullable=False),
        sa.Column('scheduled_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actual_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='scheduled'),
        sa.Column('delivery_method', sa.String(20), nullable=True),
        sa.Column('delivery_address', sa.Text(), nullable=True),
        sa.Column('delivery_notes', sa.Text(), nullable=True),
        sa.Column('handled_by_user_id', sa.Integer(), nullable=True),
        sa.Column('inspection_status', sa.String(20), nullable=True),
        sa.Column('inspection_notes', sa.Text(), nullable=True),
        sa.Column('damage_fee', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Constraints
        sa.ForeignKeyConstraint(['handled_by_user_id'], ['users.id'], name='fk_movement_handled_by_user'),
        sa.CheckConstraint(
            "movement_type IN ('departure', 'return')",
            name='check_movement_type_valid',
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'in_transit', 'completed', 'late', 'cancelled')",
            name='check_movement_status_valid',
        ),
        sa.CheckConstraint(
            "delivery_method IS NULL OR delivery_method IN ('delivery', 'pickup', 'shipping')",
            name='check_delivery_method_valid',
        ),
        sa.CheckConstraint(
            "inspection_status IS NULL OR inspection_status IN ('pending', 'ok', 'damaged', 'missing')",
            name='check_inspection_status_valid',
        ),
        sa.CheckConstraint(
            'damage_fee >= 0',
            name='check_damage_fee_positive',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_inventory_movements_tenant_id', 'inventory_movements', ['tenant_id'])
    op.create_index('ix_inventory_movement_tenant_status', 'inventory_movements', ['tenant_id', 'status'])
    op.create_index('ix_inventory_movement_tenant_event', 'inventory_movements', ['tenant_id', 'event_id'])
    op.create_index('ix_inventory_movement_scheduled_date', 'inventory_movements', ['tenant_id', 'scheduled_date'])

    # ── movement_items ───────────────────────────────────────────────
    op.create_table(
        'movement_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('movement_id', sa.Integer(), nullable=False),
        sa.Column('event_item_id', sa.Integer(), nullable=True),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('product_variation_id', sa.Integer(), nullable=True),
        sa.Column('quantity_expected', sa.Integer(), nullable=False),
        sa.Column('quantity_actual', sa.Integer(), nullable=True),
        sa.Column('condition', sa.String(20), nullable=True),
        sa.Column('condition_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Constraints
        sa.ForeignKeyConstraint(
            ['movement_id'], ['inventory_movements.id'],
            name='fk_item_movement',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['product_id'], ['products.id'],
            name='fk_item_product',
        ),
        sa.CheckConstraint(
            'quantity_expected > 0',
            name='check_item_quantity_expected_positive',
        ),
        sa.CheckConstraint(
            'quantity_actual IS NULL OR quantity_actual >= 0',
            name='check_item_quantity_actual_valid',
        ),
        sa.CheckConstraint(
            "condition IS NULL OR condition IN ('perfect', 'good', 'damaged', 'missing')",
            name='check_item_condition_valid',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_movement_items_tenant_id', 'movement_items', ['tenant_id'])
    op.create_index('ix_movement_item_tenant_movement', 'movement_items', ['tenant_id', 'movement_id'])
    op.create_index('ix_movement_item_product', 'movement_items', ['product_id'])


def downgrade() -> None:
    op.drop_index('ix_movement_item_product', table_name='movement_items')
    op.drop_index('ix_movement_item_tenant_movement', table_name='movement_items')
    op.drop_index('ix_movement_items_tenant_id', table_name='movement_items')
    op.drop_table('movement_items')

    op.drop_index('ix_inventory_movement_scheduled_date', table_name='inventory_movements')
    op.drop_index('ix_inventory_movement_tenant_event', table_name='inventory_movements')
    op.drop_index('ix_inventory_movement_tenant_status', table_name='inventory_movements')
    op.drop_index('ix_inventory_movements_tenant_id', table_name='inventory_movements')
    op.drop_table('inventory_movements')
