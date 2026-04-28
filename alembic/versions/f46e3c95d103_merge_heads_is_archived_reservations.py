"""merge heads: is_archived_reservations + previous head

Revision ID: f46e3c95d103
Revises: b6c7d8e9f0a1, z1a2b3c4d5e6
Create Date: 2026-03-07

Merge des deux branches : head principal + is_archived sur reservations.
"""
from alembic import op

revision = "f46e3c95d103"
down_revision = ("b6c7d8e9f0a1", "z1a2b3c4d5e6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
