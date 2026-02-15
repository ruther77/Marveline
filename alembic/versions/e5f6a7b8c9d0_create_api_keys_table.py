"""create_api_keys_table

Revision ID: e5f6a7b8c9d0
Revises: ec425e374f7c
Create Date: 2026-02-15 10:00:00.000000

Create api_keys table for M2M authentication.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'ec425e374f7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('key_prefix', sa.String(12), nullable=False),
        sa.Column('key_hash', sa.String(128), nullable=False),
        sa.Column('scopes', ARRAY(sa.String(50)), nullable=False),
        sa.Column('rate_limit', sa.Integer(), nullable=True, server_default='1000'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_ip', sa.String(45), nullable=True),
        sa.Column('usage_count', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'key_prefix', name='uq_api_keys_tenant_prefix'),
        sa.UniqueConstraint('key_hash', name='uq_api_keys_key_hash'),
        sa.CheckConstraint('array_length(scopes, 1) > 0', name='ck_api_keys_scopes_not_empty'),
        sa.CheckConstraint('rate_limit IS NULL OR rate_limit > 0', name='ck_api_keys_rate_limit_positive'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'])
    op.create_index(
        'ix_api_keys_tenant_active',
        'api_keys',
        ['tenant_id', 'is_active'],
        postgresql_where=sa.text('is_active = TRUE'),
    )
    op.create_index('ix_api_keys_tenant_id', 'api_keys', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_api_keys_tenant_id', table_name='api_keys')
    op.drop_index('ix_api_keys_tenant_active', table_name='api_keys')
    op.drop_index('ix_api_keys_key_hash', table_name='api_keys')
    op.drop_table('api_keys')
