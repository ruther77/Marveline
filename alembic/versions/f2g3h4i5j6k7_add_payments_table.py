"""Add payments table.

Revision ID: f2g3h4i5j6k7
Revises: e1f2a3b4c5d6
Create Date: 2026-02-18

"""
from typing import Union
import sqlalchemy as sa
from alembic import op

revision: str = 'f2g3h4i5j6k7'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        'payments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('invoice_id', sa.BigInteger(), nullable=False),
        sa.Column('amount_cents', sa.BigInteger(), nullable=False),
        sa.Column('payment_method', sa.String(20), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='RESTRICT',
                                name='fk_payments_invoice_id'),
        sa.CheckConstraint('amount_cents > 0', name='check_payment_amount_positive'),
        sa.CheckConstraint(
            "payment_method IN ('cash', 'card', 'transfer', 'check')",
            name='check_payment_method_valid'
        ),
    )
    op.create_index('ix_payments_tenant_invoice', 'payments', ['tenant_id', 'invoice_id'])


def downgrade() -> None:
    op.drop_index('ix_payments_tenant_invoice', table_name='payments')
    op.drop_table('payments')
