"""add invoice_type and tva fields to invoices

Revision ID: y7z8a9b0c1d2
Revises: x6y7z8a9b0c1
Create Date: 2026-03-01

Strategy: EXPAND
- invoice_type : VARCHAR(10) ajouté nullable avec default 'full', backfill, puis NOT NULL
- tva_rate, tva_amount_cents, total_ttc_cents : nullable, expand direct
- Contrainte CHECK + UNIQUE en fin de migration

Rollback: DROP COLUMN + contraintes
"""
from alembic import op
import sqlalchemy as sa

revision = 'y7z8a9b0c1d2'
down_revision = 'x6y7z8a9b0c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Étape 1 — colonnes nullable
    op.add_column('invoices', sa.Column('invoice_type', sa.String(10), nullable=True,
                  comment="Type : full (100%), advance (40%), balance (60%)"))
    op.add_column('invoices', sa.Column('tva_rate', sa.Float(), nullable=True,
                  comment="Taux TVA appliqué (ex: 0.20 = 20%)"))
    op.add_column('invoices', sa.Column('tva_amount_cents', sa.BigInteger(), nullable=True,
                  comment="Montant TVA en centimes"))
    op.add_column('invoices', sa.Column('total_ttc_cents', sa.BigInteger(), nullable=True,
                  comment="Total TTC en centimes"))

    # Étape 2 — backfill invoice_type
    op.execute("UPDATE invoices SET invoice_type = 'full' WHERE invoice_type IS NULL")

    # Étape 3 — NOT NULL sur invoice_type
    op.alter_column('invoices', 'invoice_type', nullable=False,
                    existing_type=sa.String(10))

    # Étape 4 — contrainte CHECK
    op.create_check_constraint(
        'check_invoice_type_valid',
        'invoices',
        "invoice_type IN ('full', 'advance', 'balance')",
    )

    # Étape 5 — contrainte UNIQUE (tenant_id, reservation_id, invoice_type)
    op.create_unique_constraint(
        'uq_invoice_tenant_reservation_type',
        'invoices',
        ['tenant_id', 'reservation_id', 'invoice_type'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_invoice_tenant_reservation_type', 'invoices', type_='unique')
    op.drop_constraint('check_invoice_type_valid', 'invoices', type_='check')
    op.drop_column('invoices', 'total_ttc_cents')
    op.drop_column('invoices', 'tva_amount_cents')
    op.drop_column('invoices', 'tva_rate')
    op.drop_column('invoices', 'invoice_type')
