"""add TVA fields to invoices

Revision ID: a1b2c3d4e5f6
Revises: z7a8b9c0d1e2
Create Date: 2026-02-22

Strategy: expand/contract — phase 1/1 (add nullable columns, no backfill required)
Rollback: safe — DROP COLUMN
Impact: no data loss — existing invoices get NULL for TVA fields (pre-TVA invoices)

Adds 3 nullable columns to invoices:
- tva_rate         : Float  — taux TVA capturé au moment de la création
- tva_amount_cents : BigInt — montant TVA en centimes
- total_ttc_cents  : BigInt — total TTC = total_amount_ht + tva_amount_cents
"""
from alembic import op
import sqlalchemy as sa

revision = 'a8b9c0d1e2f3'
down_revision = 'z7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'invoices',
        sa.Column(
            'tva_rate',
            sa.Float(),
            nullable=True,
            comment='Taux TVA appliqué (ex: 0.20 = 20%) — capturé à la création'
        )
    )
    op.add_column(
        'invoices',
        sa.Column(
            'tva_amount_cents',
            sa.BigInteger(),
            nullable=True,
            comment='Montant TVA en centimes (= total_amount * tva_rate)'
        )
    )
    op.add_column(
        'invoices',
        sa.Column(
            'total_ttc_cents',
            sa.BigInteger(),
            nullable=True,
            comment='Total TTC en centimes (= total_amount_ht + tva_amount_cents)'
        )
    )


def downgrade() -> None:
    op.drop_column('invoices', 'total_ttc_cents')
    op.drop_column('invoices', 'tva_amount_cents')
    op.drop_column('invoices', 'tva_rate')
