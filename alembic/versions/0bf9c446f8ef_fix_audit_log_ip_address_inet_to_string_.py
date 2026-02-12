"""fix_audit_log_ip_address_inet_to_string_for_tests

Revision ID: 0bf9c446f8ef
Revises: bd66c5700a41
Create Date: 2026-02-12 18:25:37.755745

Change audit_logs.ip_address type from INET to String(45) for TestClient compatibility
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET


# revision identifiers, used by Alembic.
revision: str = '0bf9c446f8ef'
down_revision: Union[str, None] = 'bd66c5700a41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change ip_address from INET to String(45) for test environment compatibility."""
    op.alter_column(
        'audit_logs',
        'ip_address',
        type_=sa.String(45),
        existing_type=INET,
        existing_nullable=True,
        postgresql_using='ip_address::text'
    )


def downgrade() -> None:
    """Revert ip_address from String(45) to INET (may fail if non-IP data exists)."""
    op.alter_column(
        'audit_logs',
        'ip_address',
        type_=INET,
        existing_type=sa.String(45),
        existing_nullable=True,
        postgresql_using='ip_address::inet'
    )
