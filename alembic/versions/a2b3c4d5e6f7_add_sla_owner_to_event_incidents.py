"""add sla_hours and owner_id to event_incidents

Revision ID: a2b3c4d5e6f7
Revises: c9d0e1f2a3b4
Create Date: 2026-02-23

Strategy: expand — colonnes nullable + default pour rétrocompatibilité.
Rollback: contract migration supprime les colonnes.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a2b3c4d5e6f7'
down_revision = '906dc9836bab'
branch_labels = None
depends_on = None

# SLA par défaut en heures par sévérité (fallback si owner ne précise pas)
# low=72h, medium=24h, high=4h, critical=1h
# La valeur DEFAULT 24 correspond à medium — sera écrasée par le service.

def upgrade() -> None:
    op.add_column(
        'event_incidents',
        sa.Column('sla_hours', sa.Integer(), nullable=False, server_default='24'),
    )
    op.add_column(
        'event_incidents',
        sa.Column(
            'owner_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_event_incidents_owner_id',
        'event_incidents',
        ['owner_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_event_incidents_owner_id', table_name='event_incidents')
    op.drop_column('event_incidents', 'owner_id')
    op.drop_column('event_incidents', 'sla_hours')
