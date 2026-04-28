"""add assigned_user_id to reservations

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-02-22

Stratégie expand/contract : ajout de colonne nullable, pas de destructive.
Rollback: safe — DROP COLUMN
"""
from alembic import op
import sqlalchemy as sa

revision = 'b9c0d1e2f3a4'
down_revision = 'a8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'reservations',
        sa.Column('assigned_user_id', sa.Integer(), nullable=True,
                  comment='Utilisateur affecté à cette réservation (équipe terrain)'),
    )
    op.create_foreign_key(
        'fk_reservations_assigned_user_id',
        'reservations', 'users',
        ['assigned_user_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_reservations_assigned_user_id',
        'reservations',
        ['assigned_user_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_reservations_assigned_user_id', table_name='reservations')
    op.drop_constraint('fk_reservations_assigned_user_id', 'reservations', type_='foreignkey')
    op.drop_column('reservations', 'assigned_user_id')
