"""merge heads: delivery_dates + notifications_link

Revision ID: a9b0c1d2e3f4
Revises: e1f2g3h4i5j6, r5s6t7u8v9w0
Create Date: 2026-03-07

Strategy: MERGE — résolution des deux branches parallèles.
"""
from alembic import op

revision = "a9b0c1d2e3f4"
down_revision = ("e1f2g3h4i5j6", "r5s6t7u8v9w0")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
