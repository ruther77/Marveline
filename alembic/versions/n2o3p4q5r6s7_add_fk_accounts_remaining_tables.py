"""Add FK constraints to accounts.id for remaining tables after IAM v2.

Tables: reservation_pre_check_items, reservation_extensions,
        stock_adjustments, stock_inventaire_sessions,
        supplier_order_receipts, inventory_movements.

These columns had their FK to users.id dropped by iam_v2_drop_legacy
but never got a replacement FK to accounts.id.

Revision ID: n2o3p4q5r6s7
Revises: m1n2o3p4q5r6
Create Date: 2026-03-12
"""
from alembic import op

revision = "n2o3p4q5r6s7"
down_revision = "m1n2o3p4q5r6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # reservation_pre_check_items.checked_by → accounts.id SET NULL
    op.create_foreign_key(
        "reservation_pre_check_items_checked_by_fkey",
        "reservation_pre_check_items",
        "accounts",
        ["checked_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # reservation_extensions.created_by → accounts.id RESTRICT
    op.create_foreign_key(
        "reservation_extensions_created_by_fkey",
        "reservation_extensions",
        "accounts",
        ["created_by"],
        ["id"],
        ondelete="RESTRICT",
    )

    # stock_inventaire_sessions.created_by → accounts.id RESTRICT
    op.create_foreign_key(
        "stock_inventaire_sessions_created_by_fkey",
        "stock_inventaire_sessions",
        "accounts",
        ["created_by"],
        ["id"],
        ondelete="RESTRICT",
    )

    # stock_adjustments.created_by → accounts.id RESTRICT
    op.create_foreign_key(
        "stock_adjustments_created_by_fkey",
        "stock_adjustments",
        "accounts",
        ["created_by"],
        ["id"],
        ondelete="RESTRICT",
    )

    # supplier_order_receipts.received_by → accounts.id RESTRICT
    op.create_foreign_key(
        "supplier_order_receipts_received_by_fkey",
        "supplier_order_receipts",
        "accounts",
        ["received_by"],
        ["id"],
        ondelete="RESTRICT",
    )

    # inventory_movements.handled_by_user_id → accounts.id (NO ACTION default)
    op.create_foreign_key(
        "inventory_movements_handled_by_user_id_fkey",
        "inventory_movements",
        "accounts",
        ["handled_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "inventory_movements_handled_by_user_id_fkey",
        "inventory_movements",
        type_="foreignkey",
    )
    op.drop_constraint(
        "supplier_order_receipts_received_by_fkey",
        "supplier_order_receipts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "stock_adjustments_created_by_fkey",
        "stock_adjustments",
        type_="foreignkey",
    )
    op.drop_constraint(
        "stock_inventaire_sessions_created_by_fkey",
        "stock_inventaire_sessions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "reservation_extensions_created_by_fkey",
        "reservation_extensions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "reservation_pre_check_items_checked_by_fkey",
        "reservation_pre_check_items",
        type_="foreignkey",
    )
