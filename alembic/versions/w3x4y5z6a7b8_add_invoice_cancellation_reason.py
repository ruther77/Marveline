"""add cancellation_reason to invoices

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-04-26

Ajoute :
  - cancellation_reason : raison obligatoire fournie par l'opérateur lors
    de l'annulation d'une facture (E — audit cancel_invoice 2026-04-26).
"""
from alembic import op
import sqlalchemy as sa

revision = 'w3x4y5z6a7b8'
down_revision = 'v2w3x4y5z6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'invoices',
        sa.Column(
            'cancellation_reason', sa.Text(), nullable=True,
            comment="Raison d'annulation (obligatoire dès qu'on annule).",
        ),
    )


def downgrade() -> None:
    op.drop_column('invoices', 'cancellation_reason')
