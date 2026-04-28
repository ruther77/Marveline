"""Add stock_items table.

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-02-18

"""
from typing import Union
import sqlalchemy as sa
from alembic import op

revision: str = 'h4i5j6k7l8m9'
down_revision: Union[str, None] = 'g3h4i5j6k7l8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'stock_items',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('serial_number', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='available'),
        sa.Column('current_reservation_id', sa.BigInteger(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['current_reservation_id'], ['reservations.id'], ondelete='SET NULL'),
        sa.CheckConstraint(
            "status IN ('available', 'reserved', 'on_location', 'damaged', 'in_repair', 'retired')",
            name='check_stock_item_status_valid'
        ),
    )
    op.create_index('ix_stock_items_tenant_product_status', 'stock_items', ['tenant_id', 'product_id', 'status'])
    op.create_index('ix_stock_items_tenant_reservation', 'stock_items', ['tenant_id', 'current_reservation_id'])

    # Data migration : générer des stock_items depuis product.available_quantity
    conn = op.get_bind()
    products = conn.execute(
        sa.text("SELECT id, tenant_id, available_quantity FROM products WHERE available_quantity > 0 AND is_active = true")
    ).fetchall()
    for product in products:
        for _ in range(product.available_quantity):
            conn.execute(
                sa.text(
                    "INSERT INTO stock_items (tenant_id, product_id, status) "
                    "VALUES (:tenant_id, :product_id, 'available')"
                ),
                {"tenant_id": product.tenant_id, "product_id": product.id}
            )


def downgrade() -> None:
    op.drop_index('ix_stock_items_tenant_reservation', table_name='stock_items')
    op.drop_index('ix_stock_items_tenant_product_status', table_name='stock_items')
    op.drop_table('stock_items')
