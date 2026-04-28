"""add message to relances

Revision ID: w4x5y6z7a8b9
Revises: v3w4x5y6z7a8
Create Date: 2026-02-22 00:00:00.000000

Stratégie expand/contract :
- Expand : ADD COLUMN message TEXT NULL (non destructif)
- Rollback safe : colonne nullable, pas de données perdues
"""
from alembic import op
import sqlalchemy as sa

revision = 'w4x5y6z7a8b9'
down_revision = 'v3w4x5y6z7a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'relances',
        sa.Column('message', sa.Text(), nullable=True, comment='Message personnalisé (optionnel)')
    )


def downgrade() -> None:
    op.drop_column('relances', 'message')
