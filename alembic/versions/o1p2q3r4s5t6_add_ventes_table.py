"""Add ventes tables (ventes, vente_lines, vente_payments).

Revision ID: o1p2q3r4s5t6
Revises: n0p1q2r3s4t5
Create Date: 2026-02-20
"""
from alembic import op
import sqlalchemy as sa

revision = "o1p2q3r4s5t6"
down_revision = "n0p1q2r3s4t5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ventes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("reference", sa.String(50), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("subtotal_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tva_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("paid_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("deposit_pct", sa.Integer(), nullable=True),
        sa.Column("payment_due_date", sa.Date(), nullable=True),
        sa.Column("invoice_id", sa.Integer(), nullable=True),
        sa.Column("reservation_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "reference", name="uq_vente_tenant_reference"),
        sa.CheckConstraint(
            "status IN ('draft','pending','deposit_paid','fully_paid','overdue','refunded')",
            name="check_vente_status_valid"
        ),
        sa.CheckConstraint("total_cents >= 0", name="check_vente_total_positive"),
        sa.CheckConstraint("paid_cents >= 0", name="check_vente_paid_positive"),
    )
    op.create_index("ix_ventes_tenant_composite", "ventes", ["tenant_id", "id"])
    op.create_index("ix_ventes_tenant_customer", "ventes", ["tenant_id", "customer_id"])
    op.create_index("ix_ventes_tenant_status", "ventes", ["tenant_id", "status"])

    op.create_table(
        "vente_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("vente_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price_cents", sa.BigInteger(), nullable=False),
        sa.Column("subtotal_cents", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["vente_id"], ["ventes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.CheckConstraint("quantity > 0", name="check_vente_line_qty_positive"),
        sa.CheckConstraint("unit_price_cents >= 0", name="check_vente_line_price_positive"),
    )
    op.create_index("ix_vente_lines_tenant_vente", "vente_lines", ["tenant_id", "vente_id"])

    op.create_table(
        "vente_payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("vente_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("is_deposit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["vente_id"], ["ventes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("amount_cents > 0", name="check_vente_payment_amount_positive"),
    )
    op.create_index("ix_vente_payments_tenant_vente", "vente_payments", ["tenant_id", "vente_id"])


def downgrade() -> None:
    op.drop_table("vente_payments")
    op.drop_table("vente_lines")
    op.drop_table("ventes")
