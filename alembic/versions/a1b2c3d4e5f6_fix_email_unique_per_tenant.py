"""fix_email_unique_per_tenant

Revision ID: a1b2c3d4e5f6
Revises: 0bf9c446f8ef
Create Date: 2026-02-13 22:00:00.000000

Drop global unique constraint on users.email, add composite unique
constraint (tenant_id, email) so different tenants can have the same email.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '0bf9c446f8ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the global unique index on email
    op.drop_index('ix_users_email', table_name='users')
    # Re-create a non-unique index on email (for query performance)
    op.create_index('ix_users_email', 'users', ['email'], unique=False)
    # Add composite unique constraint (tenant_id, email)
    op.create_unique_constraint('uq_users_tenant_email', 'users', ['tenant_id', 'email'])


def downgrade() -> None:
    # Drop composite unique constraint
    op.drop_constraint('uq_users_tenant_email', 'users', type_='unique')
    # Drop non-unique index
    op.drop_index('ix_users_email', table_name='users')
    # Re-create global unique index on email
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
