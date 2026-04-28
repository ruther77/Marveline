"""add advance payment tracking to reservations

Revision ID: z7a8b9c0d1e2
Revises: y6z7a8b9c0d1
Create Date: 2026-02-22

Option B — tracking acompte sans split de facture.
Ajoute 3 colonnes nullable sur reservations :
- advance_payment_amount_cents : montant acompte 40% (calculé à la confirmation)
- balance_due_date : date d'échéance du solde (event_date - BALANCE_DUE_DAYS_BEFORE_EVENT)
- advance_paid_at : horodatage encaissement acompte (NULL jusqu'à encaissement)
"""
from alembic import op
import sqlalchemy as sa

revision = 'z7a8b9c0d1e2'
down_revision = 'y6z7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'reservations',
        sa.Column(
            'advance_payment_amount_cents',
            sa.BigInteger(),
            nullable=True,
            comment='Montant acompte 40% en centimes (calculé à la confirmation)'
        )
    )
    op.add_column(
        'reservations',
        sa.Column(
            'balance_due_date',
            sa.Date(),
            nullable=True,
            comment='Date échéance solde (event_date - BALANCE_DUE_DAYS_BEFORE_EVENT)'
        )
    )
    op.add_column(
        'reservations',
        sa.Column(
            'advance_paid_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Horodatage encaissement acompte (NULL si non encaissé)'
        )
    )


def downgrade() -> None:
    op.drop_column('reservations', 'advance_paid_at')
    op.drop_column('reservations', 'balance_due_date')
    op.drop_column('reservations', 'advance_payment_amount_cents')
