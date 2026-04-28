"""add supplier_orders, supplier_order_lines, supplier_order_receipts

Revision ID: y6z7a8b9c0d1
Revises: x5y6z7a8b9c0
Create Date: 2026-02-23

Strategy: EXPAND — nouvelles tables uniquement, aucune colonne modifiée.
Rollback: DROP TABLE supplier_order_receipts, supplier_order_lines, supplier_orders
"""
from alembic import op
import sqlalchemy as sa

revision = "y6z7a8b9c0d1"
down_revision = "x5y6z7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- supplier_orders ---
    op.create_table(
        "supplier_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("order_date", sa.Date(), nullable=True),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_supplier_orders_tenant_supplier",
        "supplier_orders",
        ["tenant_id", "supplier_id"],
    )
    op.create_index(
        "ix_supplier_orders_tenant_status",
        "supplier_orders",
        ["tenant_id", "status"],
    )

    # --- supplier_order_lines ---
    op.create_table(
        "supplier_order_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("qty_ordered", sa.Integer(), nullable=False),
        sa.Column("unit_cost_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("qty_received", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["supplier_orders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_supplier_order_lines_order_id", "supplier_order_lines", ["order_id"]
    )

    # --- supplier_order_receipts ---
    op.create_table(
        "supplier_order_receipts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column(
            "received_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column("received_by", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("lines_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["supplier_orders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["received_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_supplier_order_receipts_order_id",
        "supplier_order_receipts",
        ["order_id"],
    )


def downgrade() -> None:
    op.drop_table("supplier_order_receipts")
    op.drop_table("supplier_order_lines")
    op.drop_table("supplier_orders")
