"""Add invoice_credit_notes table.

Revision ID: p2q3r4s5t6u7
Revises: o1p2q3r4s5t6
Create Date: 2026-02-20 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "p2q3r4s5t6u7"
down_revision = "o1p2q3r4s5t6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_credit_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("original_invoice_id", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["original_invoice_id"], ["invoices.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "status IN ('draft','issued','applied')",
            name="check_credit_note_status_valid"
        ),
        sa.CheckConstraint("amount_cents > 0", name="check_credit_note_amount_positive"),
        sa.UniqueConstraint("tenant_id", "invoice_number", name="uq_credit_note_tenant_number"),
    )
    op.create_index("ix_credit_notes_tenant_composite", "invoice_credit_notes", ["tenant_id", "id"])
    op.create_index("ix_credit_notes_tenant_invoice", "invoice_credit_notes", ["tenant_id", "original_invoice_id"])


def downgrade() -> None:
    op.drop_table("invoice_credit_notes")
