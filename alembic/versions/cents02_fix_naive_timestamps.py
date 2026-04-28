"""Fix naive timestamps: signed_at and audit_logs.created_at → timestamptz.

Revision ID: cents02
Revises: cents01
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa

revision = "cents02"
down_revision = "merge_cents01_cus01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "reservations", "signed_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        existing_nullable=True,
        postgresql_using="signed_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "audit_logs", "created_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "reservations", "signed_at",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "audit_logs", "created_at",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
