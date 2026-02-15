"""add_mfa_unique_constraint_tenant_user

Revision ID: b03b473d5966
Revises: d4e5f6a7b8c9
Create Date: 2026-02-15 12:43:03.808485

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b03b473d5966'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint on (tenant_id, user_id) to mfa_devices table.

    Ensures one MFA device per user per tenant (enforce business rule).
    """
    op.create_unique_constraint(
        'uq_mfa_device_tenant_user',
        'mfa_devices',
        ['tenant_id', 'user_id']
    )


def downgrade() -> None:
    """Remove unique constraint on (tenant_id, user_id) from mfa_devices table."""
    op.drop_constraint(
        'uq_mfa_device_tenant_user',
        'mfa_devices',
        type_='unique'
    )
