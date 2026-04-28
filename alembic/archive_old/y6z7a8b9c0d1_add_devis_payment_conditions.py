"""add conditions_paiement and message_accompagnement to devis

Revision ID: y6z7a8b9c0d1
Revises: x5y6z7a8b9c0
Create Date: 2026-02-22 00:00:00.000000

Strategy: expand — ADD COLUMN nullable, no data migration required.
Rollback: drop columns (safe, nullable).
"""
from alembic import op
import sqlalchemy as sa

revision = 'y6z7a8b9c0d1'
down_revision = 'x5y6z7a8b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('devis', sa.Column(
        'conditions_paiement',
        sa.String(50),
        nullable=True,
        comment="Conditions de paiement (30_acompte, 50_50, comptant, fin_evenement)"
    ))
    op.add_column('devis', sa.Column(
        'message_accompagnement',
        sa.Text(),
        nullable=True,
        comment="Message d'accompagnement envoyé avec le devis"
    ))


def downgrade() -> None:
    op.drop_column('devis', 'message_accompagnement')
    op.drop_column('devis', 'conditions_paiement')
