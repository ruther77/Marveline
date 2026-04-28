"""Add suppliers, stock_inventaire_sessions, stock_adjustments tables + supplier_id on products.

Revision ID: r4s5t6u7v8w9
Revises: q3r4s5t6u7v8
Create Date: 2026-02-20 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "r4s5t6u7v8w9"
down_revision = "q3r4s5t6u7v8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- suppliers ----
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_suppliers_tenant_id", "suppliers", ["tenant_id", "id"])

    # ---- supplier_id FK on products ----
    op.add_column(
        "products",
        sa.Column("supplier_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_products_supplier_id",
        "products", "suppliers",
        ["supplier_id"], ["id"],
        ondelete="SET NULL",
    )

    # ---- stock_inventaire_sessions ----
    op.create_table(
        "stock_inventaire_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("variances_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_inv_sessions_tenant", "stock_inventaire_sessions", ["tenant_id", "id"])

    # ---- stock_adjustments ----
    op.create_table(
        "stock_adjustments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_adjustments_tenant", "stock_adjustments", ["tenant_id", "id"])
    op.create_index("ix_stock_adjustments_product", "stock_adjustments", ["tenant_id", "product_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_adjustments_product", table_name="stock_adjustments")
    op.drop_index("ix_stock_adjustments_tenant", table_name="stock_adjustments")
    op.drop_table("stock_adjustments")

    op.drop_index("ix_stock_inv_sessions_tenant", table_name="stock_inventaire_sessions")
    op.drop_table("stock_inventaire_sessions")

    op.drop_constraint("fk_products_supplier_id", "products", type_="foreignkey")
    op.drop_column("products", "supplier_id")

    op.drop_index("ix_suppliers_tenant_id", table_name="suppliers")
    op.drop_table("suppliers")
