"""add_mfa_devices_table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-13 23:00:00.000000

Add mfa_devices table for TOTP MFA support.
Stores encrypted TOTP secrets and bcrypt-hashed recovery codes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mfa_devices',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('encrypted_secret', sa.LargeBinary(), nullable=False,
                   comment='AES-256-GCM encrypted TOTP secret'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='false',
                   comment='True once initial TOTP verification succeeds'),
        sa.Column('recovery_codes_hash', sa.Text(), nullable=True,
                   comment='JSON list of bcrypt-hashed recovery codes'),
        sa.Column('last_totp_window', sa.Integer(), nullable=True,
                   comment='Last accepted TOTP time window (anti-replay)'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mfa_devices_user_id', 'mfa_devices', ['user_id'])
    op.create_index('ix_mfa_devices_tenant_id', 'mfa_devices', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_mfa_devices_tenant_id', table_name='mfa_devices')
    op.drop_index('ix_mfa_devices_user_id', table_name='mfa_devices')
    op.drop_table('mfa_devices')
