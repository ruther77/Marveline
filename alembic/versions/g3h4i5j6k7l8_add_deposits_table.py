"""Add deposits table.

Revision ID: g3h4i5j6k7l8
Revises: f2g3h4i5j6k7
Create Date: 2026-02-18

"""
from typing import Union
import sqlalchemy as sa
from alembic import op

revision: str = 'g3h4i5j6k7l8'
down_revision: Union[str, None] = 'f2g3h4i5j6k7'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        'deposits',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('reservation_id', sa.BigInteger(), nullable=False),
        sa.Column('amount_cents', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='held'),
        sa.Column('retained_amount_cents', sa.BigInteger(), nullable=True),
        sa.Column('collection_date', sa.Date(), nullable=True),
        sa.Column('release_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ondelete='RESTRICT',
                                name='fk_deposits_reservation_id'),
        sa.CheckConstraint('amount_cents > 0', name='check_deposit_amount_positive'),
        sa.CheckConstraint(
            "status IN ('held', 'released', 'retained')",
            name='check_deposit_status_valid'
        ),
        sa.CheckConstraint(
            'retained_amount_cents IS NULL OR retained_amount_cents > 0',
            name='check_deposit_retained_positive'
        ),
    )
    op.create_index('ix_deposits_tenant_reservation', 'deposits', ['tenant_id', 'reservation_id'])


def downgrade() -> None:
    op.drop_index('ix_deposits_tenant_reservation', table_name='deposits')
    op.drop_table('deposits')
