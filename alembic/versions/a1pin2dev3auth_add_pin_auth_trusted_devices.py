"""Add PIN auth + trusted_devices table.

PIN authentication for restaurant servers (complement to password).
Trusted devices store registered tablets for PIN-only login.

Revision ID: a1pin2dev3auth
Revises: o2p3q4r5s6t7
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1pin2dev3auth'
down_revision = 'o2p3q4r5s6t7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add pin_hash to accounts (nullable — null if PIN not set)
    op.add_column('accounts', sa.Column(
        'pin_hash',
        sa.String(255),
        nullable=True,
        comment='Argon2id hash du PIN 4-6 chiffres (null si non configuré)',
    ))

    # 2. Create trusted_devices table
    op.create_table(
        'trusted_devices',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('account_id', sa.BigInteger(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('device_id', sa.String(256), nullable=False, comment='Fingerprint unique du device (navigator.userAgent + screen + crypto.randomUUID)'),
        sa.Column('device_name', sa.String(100), nullable=True, comment='Nom lisible (ex: Tablette salle 1)'),
        sa.Column('registered_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True, comment='Non null = device révoqué'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Indexes
    op.create_index('idx_trusted_devices_account', 'trusted_devices', ['account_id'])
    op.create_index('idx_trusted_devices_tenant', 'trusted_devices', ['tenant_id'])
    op.create_index('idx_trusted_devices_device_id', 'trusted_devices', ['device_id'])
    op.create_unique_constraint('uq_trusted_devices_account_device', 'trusted_devices', ['account_id', 'device_id'])


def downgrade() -> None:
    op.drop_table('trusted_devices')
    op.drop_column('accounts', 'pin_hash')
