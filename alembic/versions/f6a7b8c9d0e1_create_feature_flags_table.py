"""create_feature_flags_table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-15 16:00:00.000000

Create feature_flags table for feature management with tenant targeting.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'feature_flags',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('target_tenants', ARRAY(sa.Integer()), nullable=True),
        sa.Column('rollout_pct', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            'rollout_pct >= 0 AND rollout_pct <= 100',
            name='ck_feature_flags_rollout_pct_range'
        ),
        sa.CheckConstraint(
            "name ~ '^[a-z][a-z0-9_]*$'",
            name='ck_feature_flags_name_format'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_feature_flags_name', 'feature_flags', ['name'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_feature_flags_name', table_name='feature_flags')
    op.drop_table('feature_flags')
