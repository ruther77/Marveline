"""merge heads: inventory_movement_damages + supplier_order_receipt_lines

Revision ID: cc33dd44ee55
Revises: bb22cc33dd44, e159e1c66a61
Create Date: 2026-02-24

Merge de deux branches parallèles :
- bb22cc33dd44: supplier_order_receipt_lines (Option B granulaire)
- e159e1c66a61: merge heads fk_devis_timeline (branche principale)
"""
from alembic import op

revision = "cc33dd44ee55"
down_revision = ("bb22cc33dd44", "e159e1c66a61")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
