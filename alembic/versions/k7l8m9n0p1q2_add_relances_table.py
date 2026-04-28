"""add relances table

Revision ID: k7l8m9n0p1q2
Revises: j6k7l8m9n0p1
Create Date: 2026-02-20

B8-C : Table relances — relances planifiées liées aux factures.
Stratégie expand/contract : création pure, pas de modification de colonne existante.
Rollback : DROP TABLE relances.
"""
from typing import Union
import sqlalchemy as sa
from alembic import op


revision: str = 'k7l8m9n0p1q2'
down_revision: Union[str, None] = 'j6k7l8m9n0p1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'relances',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('scheduled_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('sent_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='scheduled'),
        sa.Column('channel', sa.String(20), nullable=False, server_default='email'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            "status IN ('scheduled', 'sent', 'cancelled')",
            name='check_relance_status_valid'
        ),
        sa.CheckConstraint(
            "channel IN ('email', 'sms', 'push')",
            name='check_relance_channel_valid'
        ),
    )
    op.create_index('ix_relances_tenant_id', 'relances', ['tenant_id', 'id'])
    op.create_index('ix_relances_tenant_invoice', 'relances', ['tenant_id', 'invoice_id'])
    op.create_index('ix_relances_tenant_status', 'relances', ['tenant_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_relances_tenant_status', table_name='relances')
    op.drop_index('ix_relances_tenant_invoice', table_name='relances')
    op.drop_index('ix_relances_tenant_id', table_name='relances')
    op.drop_table('relances')
