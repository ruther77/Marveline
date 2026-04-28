"""fix timestamps deposits payments invoice_charges damage_types

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-02-18 00:00:00.000000

"""
from typing import Union
from alembic import op
import sqlalchemy as sa


revision: str = 'i5j6k7l8m9n0'
down_revision: Union[str, None] = 'a7163c18990a'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Backfill NULL timestamps with NOW() before making columns NOT NULL
    op.execute("UPDATE deposits SET created_at = NOW() WHERE created_at IS NULL")
    op.execute("UPDATE deposits SET updated_at = NOW() WHERE updated_at IS NULL")
    op.execute("UPDATE damage_types SET created_at = NOW() WHERE created_at IS NULL")
    op.execute("UPDATE damage_types SET updated_at = NOW() WHERE updated_at IS NULL")

    for table in ('deposits', 'payments', 'invoice_charges', 'damage_types'):
        op.alter_column(
            table, 'created_at',
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            nullable=False,
            server_default=sa.text('now()'),
        )
        op.alter_column(
            table, 'updated_at',
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            nullable=False,
            server_default=sa.text('now()'),
        )


def downgrade() -> None:
    for table in ('deposits', 'payments', 'invoice_charges', 'damage_types'):
        op.alter_column(
            table, 'created_at',
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=None,
        )
        op.alter_column(
            table, 'updated_at',
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=None,
        )
