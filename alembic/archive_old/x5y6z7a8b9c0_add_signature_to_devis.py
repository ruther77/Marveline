"""add signature_url and signed_at to devis

Revision ID: x5y6z7a8b9c0
Revises: w4x5y6z7a8b9
Create Date: 2026-02-22 00:00:00.000000

Strategy: expand — ADD COLUMN nullable, no data migration required.
Rollback: drop columns (safe, nullable).
"""
from alembic import op
import sqlalchemy as sa

revision = 'x5y6z7a8b9c0'
down_revision = 'w4x5y6z7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'devis',
        sa.Column('signature_url', sa.String(500), nullable=True,
                  comment='URL du fichier de signature électronique')
    )
    op.add_column(
        'devis',
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True,
                  comment='Date et heure de la signature électronique')
    )


def downgrade() -> None:
    op.drop_column('devis', 'signed_at')
    op.drop_column('devis', 'signature_url')
