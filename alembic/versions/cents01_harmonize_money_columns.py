"""Harmonize money column names: add _cents suffix.

All money columns in centimes get explicit _cents suffix.
Also removes unused deposit_rate from tenant_settings.

Revision ID: cents01
Revises: merge_logi05_salle01
Create Date: 2026-04-02
"""

import sqlalchemy as sa
from alembic import op

revision = "cents01"
down_revision = "merge_logi05_salle01"
branch_labels = None
depends_on = None

# (table, old_name, new_name)
RENAMES = [
    # products
    ("products", "price_per_day", "price_per_day_cents"),
    ("products", "deposit_amount", "deposit_amount_cents"),
    ("products", "cleaning_fee", "cleaning_fee_cents"),
    # product_variants
    ("product_variants", "price_per_day", "price_per_day_cents"),
    ("product_variants", "deposit_amount", "deposit_amount_cents"),
    # product_bundles
    ("product_bundles", "bundle_price", "bundle_price_cents"),
    ("product_bundles", "cleaning_fee", "cleaning_fee_cents"),
    # reservations
    ("reservations", "total_amount", "total_amount_cents"),
    ("reservations", "deposit_amount", "deposit_amount_cents"),
    # reservation_lines
    ("reservation_lines", "unit_price", "unit_price_cents"),
    ("reservation_lines", "subtotal", "subtotal_cents"),
    # invoices
    ("invoices", "total_amount", "total_amount_cents"),
    ("invoices", "paid_amount", "paid_amount_cents"),
    # inventory_movements
    ("inventory_movements", "damage_fee", "damage_fee_cents"),
]


def upgrade() -> None:
    for table, old, new in RENAMES:
        op.alter_column(table, old, new_column_name=new)

    # Supprimer deposit_rate inutilisé (deposit_multiplier est utilisé)
    op.drop_column("tenant_settings", "deposit_rate")


def downgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column("deposit_rate", sa.Float(), nullable=False, server_default="0.3"),
    )
    for table, old, new in reversed(RENAMES):
        op.alter_column(table, new, new_column_name=old)
