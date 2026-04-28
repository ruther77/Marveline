"""add supplier_order_receipt_lines table (Option B granulaire)

Revision ID: bb22cc33dd44
Revises: aa11bb22cc33
Create Date: 2026-02-24

Expand-only : ajout de la table supplier_order_receipt_lines pour
tracer le détail granulaire des réceptions (conforme / endommagé / manquant).
La colonne lines_json de supplier_order_receipts est conservée en parallèle
(stratégie expand/contract).
"""
from alembic import op
import sqlalchemy as sa

revision = "bb22cc33dd44"
down_revision = "aa11bb22cc33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_order_receipt_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column(
            "receipt_id",
            sa.Integer(),
            sa.ForeignKey("supplier_order_receipts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_line_id",
            sa.Integer(),
            sa.ForeignKey("supplier_order_lines.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("qty_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qty_damaged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qty_missing", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "damage_type_id",
            sa.Integer(),
            sa.ForeignKey("damage_types.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("qty_received >= 0", name="ck_receipt_line_qty_received_nn"),
        sa.CheckConstraint("qty_damaged >= 0", name="ck_receipt_line_qty_damaged_nn"),
        sa.CheckConstraint("qty_missing >= 0", name="ck_receipt_line_qty_missing_nn"),
    )
    op.create_index(
        "ix_supplier_order_receipt_lines_tenant_id",
        "supplier_order_receipt_lines",
        ["tenant_id"],
    )
    op.create_index(
        "ix_supplier_order_receipt_lines_receipt_id",
        "supplier_order_receipt_lines",
        ["receipt_id"],
    )
    op.create_index(
        "ix_supplier_order_receipt_lines_tenant_order",
        "supplier_order_receipt_lines",
        ["tenant_id", "order_line_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_order_receipt_lines_tenant_order",
        table_name="supplier_order_receipt_lines",
    )
    op.drop_index(
        "ix_supplier_order_receipt_lines_receipt_id",
        table_name="supplier_order_receipt_lines",
    )
    op.drop_index(
        "ix_supplier_order_receipt_lines_tenant_id",
        table_name="supplier_order_receipt_lines",
    )
    op.drop_table("supplier_order_receipt_lines")
