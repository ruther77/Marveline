"""Drop obsolete unique constraint on invoices.reservation_id.

The constraint invoices_reservation_id_key (UNIQUE on reservation_id alone)
prevents multiple invoice types (deposit, balance, credit) for the same
reservation. The correct constraint uq_invoice_tenant_reservation_type
(tenant_id, reservation_id, invoice_type) already exists.

Revision ID: z0a1b2c3d4e5
Revises: 2f430578169e
Create Date: 2026-03-04
"""
from alembic import op

revision = "z0a1b2c3d4e5"
down_revision = "2f430578169e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("invoices_reservation_id_key", "invoices", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("invoices_reservation_id_key", "invoices", ["reservation_id"])
