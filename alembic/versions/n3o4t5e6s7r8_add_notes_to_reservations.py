"""add notes column to reservations

Revision ID: n3o4t5e6s7r8
Revises: b2print3conf4ts
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = 'n3o4t5e6s7r8'
down_revision = 'a1b2prix0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('reservations', sa.Column('notes', sa.Text(), nullable=True, comment='Notes libres sur la réservation'))


def downgrade() -> None:
    op.drop_column('reservations', 'notes')
