"""add oauth fields to users

Revision ID: e9f0a1b2c3d4
Revises: d2e3f4a5b6c7
Create Date: 2026-03-03 00:00:00.000000

Stratégie : expand-only (colonnes nullable → zéro downtime, rollback sûr).
"""
from alembic import op
import sqlalchemy as sa

revision = 'e9f0a1b2c3d4'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'oauth_provider',
        sa.String(50),
        nullable=True,
        comment='Provider OAuth lié (google, github, facebook)',
    ))
    op.add_column('users', sa.Column(
        'oauth_id',
        sa.String(255),
        nullable=True,
        comment='ID unique chez le provider OAuth (toujours str)',
    ))
    # Index partiel unique : ne couvre que les lignes où oauth_provider IS NOT NULL
    op.create_index(
        'uq_user_oauth',
        'users',
        ['tenant_id', 'oauth_provider', 'oauth_id'],
        unique=True,
        postgresql_where=sa.text('oauth_provider IS NOT NULL'),
    )
    # Index de recherche rapide par (tenant, provider, oauth_id)
    op.create_index(
        'ix_users_oauth_lookup',
        'users',
        ['tenant_id', 'oauth_provider', 'oauth_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_users_oauth_lookup', table_name='users')
    op.drop_index('uq_user_oauth', table_name='users')
    op.drop_column('users', 'oauth_id')
    op.drop_column('users', 'oauth_provider')
