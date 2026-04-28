"""add signature_url and signed_at to devis

Revision ID: x6y7z8a9b0c1
Revises: ff00ee11dd22
Create Date: 2026-03-01 00:00:00.000000

Strategy: expand — ADD COLUMN nullable, aucune migration de données.
Rollback: DROP COLUMN (safe, nullable).
"""
from alembic import op
import sqlalchemy as sa

revision = 'x6y7z8a9b0c1'
down_revision = 'ff00ee11dd22'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'devis',
        sa.Column('signature_url', sa.Text(), nullable=True,
                  comment='Données de signature électronique (base64 PNG)'),
    )
    op.add_column(
        'devis',
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True,
                  comment='Date et heure de la signature électronique'),
    )


def downgrade() -> None:
    op.drop_column('devis', 'signed_at')
    op.drop_column('devis', 'signature_url')
